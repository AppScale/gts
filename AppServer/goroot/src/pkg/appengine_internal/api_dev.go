// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package appengine_internal

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"

	basepb "appengine_internal/base"
	"appengine_internal/remote_api"
	rpb "appengine_internal/runtime_config"
	"code.google.com/p/goprotobuf/proto"
)

// IsDevAppServer returns whether the App Engine app is running in the
// development App Server.
func IsDevAppServer() bool {
	return true
}

// serveHTTP serves App Engine HTTP requests.
func serveHTTP() {
	// The development server reads the HTTP port that the server is listening to
	// from stdout. We listen on 127.0.0.1:0 to avoid firewall restrictions.
	conn, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		log.Fatal("appengine: couldn't listen to TCP socket: ", err)
	}
	port := conn.Addr().(*net.TCPAddr).Port

	fmt.Fprintln(os.Stdout, port)
	os.Stdout.Close()

	err = http.Serve(conn, http.HandlerFunc(handleFilteredHTTP))
	if err != nil {
		log.Fatal("appengine: ", err)
	}
}

func init() {
	// If the user's application has a transitive dependency on appengine_internal
	// then this init will be called before any user code. The user application
	// should also not be reading from stdin.
	c := readConfig(os.Stdin)
	instanceConfig.AppID = string(c.AppId)
	instanceConfig.APIHost = c.GetApiHost()
	instanceConfig.APIPort = int(*c.ApiPort)
	instanceConfig.VersionID = string(c.VersionId)
	instanceConfig.InstanceID = *c.InstanceId
	instanceConfig.Datacenter = *c.Datacenter

	apiAddress = fmt.Sprintf("http://%s:%d", instanceConfig.APIHost, instanceConfig.APIPort)
}

func handleFilteredHTTP(w http.ResponseWriter, r *http.Request) {
	// Patch up RemoteAddr so it looks reasonable.
	if addr := r.Header.Get("X-Appengine-Internal-Remote-Addr"); addr != "" {
		r.RemoteAddr = addr
	} else {
		// Should not normally reach here, but pick
		// a sensible default anyway.
		r.RemoteAddr = "127.0.0.1"
	}

	// Create a private copy of the Request that includes headers that are
	// private to the runtime and strip those headers from the request that the
	// user application sees.
	creq := *r
	r.Header = make(http.Header)
	for name, values := range creq.Header {
		if !strings.HasPrefix(name, "X-Appengine-Internal-") {
			r.Header[name] = values
		}
	}
	ctxsMu.Lock()
	ctxs[r] = &context{req: &creq}
	ctxsMu.Unlock()

	http.DefaultServeMux.ServeHTTP(w, r)

	ctxsMu.Lock()
	delete(ctxs, r)
	ctxsMu.Unlock()
}

var (
	apiAddress    string
	apiHTTPClient = &http.Client{
		Transport: &http.Transport{
			Proxy: http.ProxyFromEnvironment,
		},
	}

	ctxsMu sync.Mutex
	ctxs   = make(map[*http.Request]*context)

	instanceConfig struct {
		AppID      string
		VersionID  string
		InstanceID string
		Datacenter string
		APIHost    string
		APIPort    int
	}
)

func readConfig(r io.Reader) *rpb.Config {
	raw, err := ioutil.ReadAll(r)
	if err != nil {
		log.Fatal("appengine: could not read from stdin: ", err)
	}

	if len(raw) == 0 {
		// If there were zero bytes, assume this code is not being run as part of
		// a complete app under devappserver2, and generate some reasonable defaults.
		log.Print("appengine: not running under devappserver2; using some default configuration")
		return &rpb.Config{
			AppId:      []byte("dev~my-app"),
			VersionId:  []byte("1.2345"),
			ApiHost:    proto.String("localhost"),
			ApiPort:    proto.Int32(1),
			Datacenter: proto.String("us1"),
			InstanceId: proto.String("deadbeef"),
		}
	}

	b := make([]byte, base64.StdEncoding.DecodedLen(len(raw)))
	n, err := base64.StdEncoding.Decode(b, raw)
	if err != nil {
		log.Fatal("appengine: could not base64 decode stdin: ", err)
	}
	config := &rpb.Config{}

	err = proto.Unmarshal(b[:n], config)
	if err != nil {
		log.Fatal("appengine: could not decode runtime_config: ", err)
	}
	return config
}

func call(service, method string, data []byte, requestID string) ([]byte, error) {
	req := &remote_api.Request{
		ServiceName: &service,
		Method:      &method,
		Request:     data,
		RequestId:   &requestID,
	}

	buf, err := proto.Marshal(req)
	if err != nil {
		return nil, err
	}

	resp, err := apiHTTPClient.Post(apiAddress,
		"application/octet-stream", bytes.NewReader(buf))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	res := &remote_api.Response{}
	err = proto.Unmarshal(body, res)
	if err != nil {
		return nil, err
	}

	if ae := res.ApplicationError; ae != nil {
		// All Remote API application errors are API-level failures.
		return nil, &APIError{Service: service, Detail: *ae.Detail, Code: *ae.Code}
	}
	return res.Response, nil
}

// context represents the context of an in-flight HTTP request.
// It implements the appengine.Context interface.
type context struct {
	req *http.Request
}

func NewContext(req *http.Request) *context {
	ctxsMu.Lock()
	defer ctxsMu.Unlock()
	c := ctxs[req]

	if c == nil {
		// Someone passed in an http.Request that is not in-flight.
		// We panic here rather than panicking at a later point
		// so that backtraces will be more sensible.
		log.Panic("appengine: NewContext passed an unknown http.Request")
	}
	return c
}

func (c *context) Call(service, method string, in, out ProtoMessage, opts *CallOptions) error {
	if service == "__go__" {
		if method == "GetNamespace" {
			out.(*basepb.StringProto).Value = proto.String(c.req.Header.Get("X-AppEngine-Current-Namespace"))
			return nil
		}
		if method == "GetDefaultNamespace" {
			out.(*basepb.StringProto).Value = proto.String(c.req.Header.Get("X-AppEngine-Default-Namespace"))
			return nil
		}
	}
	if f, ok := apiOverrides[struct{ service, method string }{service, method}]; ok {
		return f(in, out, opts)
	}
	data, err := proto.Marshal(in)
	if err != nil {
		return err
	}

	requestID := c.req.Header.Get("X-Appengine-Internal-Request-Id")
	res, err := call(service, method, data, requestID)
	if err != nil {
		return err
	}
	return proto.Unmarshal(res, out)
}

func (c *context) Request() interface{} {
	return c.req
}

func (c *context) logf(level, format string, args ...interface{}) {
	log.Printf(level+": "+format, args...)
}

func (c *context) Debugf(format string, args ...interface{})    { c.logf("DEBUG", format, args...) }
func (c *context) Infof(format string, args ...interface{})     { c.logf("INFO", format, args...) }
func (c *context) Warningf(format string, args ...interface{})  { c.logf("WARNING", format, args...) }
func (c *context) Errorf(format string, args ...interface{})    { c.logf("ERROR", format, args...) }
func (c *context) Criticalf(format string, args ...interface{}) { c.logf("CRITICAL", format, args...) }

// FullyQualifiedAppID returns the fully-qualified application ID.
// This may contain a partition prefix (e.g. "s~" for High Replication apps),
// or a domain prefix (e.g. "example.com:").
func (c *context) FullyQualifiedAppID() string {
	return instanceConfig.AppID
}
