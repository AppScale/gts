// Copyright 2013 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package aetest provides an appengine.Context for use in tests.

An example test file:

	package foo_test

	import (
		"testing"

		"appengine/memcache"
		"appengine/aetest"
	)

	func TestFoo(t *testing.T) {
		c, err := aetest.NewContext(nil)
		if err != nil {
			t.Fatal(err)
		}
		defer c.Close()

		it := &memcache.Item{
			Key:   "some-key",
			Value: []byte("some-value"),
		}
		err = memcache.Set(c, it)
		if err != nil {
			t.Fatalf("Set err: %v", err)
		}
		it, err = memcache.Get(c, "some-key")
		if err != nil {
			t.Fatalf("Get err: %v; want no error", err)
		}
		if g, w := string(it.Value), "some-value" ; g != w {
			t.Errorf("retrieved Item.Value = %q, want %q", g, w)
		}
	}

The environment variable APPENGINE_DEV_APPSERVER specifies the location of the
dev_appserver.py executable to use. If unset, the system PATH is consulted.
*/
package aetest

import (
	"bufio"
	"bytes"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"time"

	"appengine"
	"appengine_internal"
	"code.google.com/p/goprotobuf/proto"

	basepb "appengine_internal/base"
	remoteapipb "appengine_internal/remote_api"
)

// Context is an appengine.Context that sends all App Engine API calls to an
// instance of the API server.
type Context interface {
	appengine.Context

	// Close kills the child api_server.py process,
	// releasing its resources.
	io.Closer
}

// NewContext launches an instance of api_server.py and returns a Context
// that delegates all App Engine API calls to that instance.
// If opts is nil the default values are used.
func NewContext(opts *Options) (Context, error) {
	req, _ := http.NewRequest("GET", "/", nil)
	c := &context{
		appID:   opts.appID(),
		req:     req,
		session: newSessionID(),
	}
	if err := c.startChild(); err != nil {
		return nil, err
	}
	return c, nil
}

func newSessionID() string {
	var buf [16]byte
	io.ReadFull(rand.Reader, buf[:])
	return fmt.Sprintf("%x", buf[:])
}

// TODO: option to pass flags to api_server.py

// Options is used to specify options when creating a Context.
type Options struct {
	// AppID specifies the App ID to use during tests.
	// By default, "testapp".
	AppID string
}

func (o *Options) appID() string {
	if o == nil || o.AppID == "" {
		return "testapp"
	}
	return o.AppID
}

// context implements appengine.Context by running an api_server.py
// process as a child and proxying all Context calls to the child.
type context struct {
	appID    string
	req      *http.Request
	child    *exec.Cmd
	apiURL   string // base URL of API HTTP server
	adminURL string // base URL of admin HTTP server
	appDir   string
	session  string
}

func (c *context) AppID() string               { return c.appID }
func (c *context) Request() interface{}        { return c.req }
func (c *context) FullyQualifiedAppID() string { return "dev~" + c.appID }

func (c *context) logf(level, format string, args ...interface{}) {
	log.Printf(level+": "+format, args...)
}

func (c *context) Debugf(format string, args ...interface{})    { c.logf("DEBUG", format, args...) }
func (c *context) Infof(format string, args ...interface{})     { c.logf("INFO", format, args...) }
func (c *context) Warningf(format string, args ...interface{})  { c.logf("WARNING", format, args...) }
func (c *context) Errorf(format string, args ...interface{})    { c.logf("ERROR", format, args...) }
func (c *context) Criticalf(format string, args ...interface{}) { c.logf("CRITICAL", format, args...) }

// Call is an implementation of appengine.Context's Call that delegates
// to a child api_server.py instance.
func (c *context) Call(service, method string, in, out appengine_internal.ProtoMessage, opts *appengine_internal.CallOptions) error {
	if service == "__go__" && (method == "GetNamespace" || method == "GetDefaultNamespace") {
		out.(*basepb.StringProto).Value = proto.String("")
		return nil
	}
	data, err := proto.Marshal(in)
	if err != nil {
		return err
	}
	req, err := proto.Marshal(&remoteapipb.Request{
		ServiceName: proto.String(service),
		Method:      proto.String(method),
		Request:     data,
		RequestId:   proto.String(c.session),
	})
	if err != nil {
		return err
	}
	res, err := http.Post(c.apiURL, "application/octet-stream", bytes.NewReader(req))
	if err != nil {
		return err
	}
	defer res.Body.Close()
	body, err := ioutil.ReadAll(res.Body)
	if res.StatusCode != 200 {
		return fmt.Errorf("got status %d; body: %q", res.StatusCode, body)
	}
	if err != nil {
		return err
	}
	resp := &remoteapipb.Response{}
	err = proto.Unmarshal(body, resp)
	if err != nil {
		return err
	}
	if e := resp.GetApplicationError(); e != nil {
		return fmt.Errorf("remote_api error (%v): %v", *e.Code, *e.Detail)
	}
	return proto.Unmarshal(resp.Response, out)
}

// Close kills the child api_server.py process, releasing its resources.
// Close is not part of the appengine.Context interface.
func (c *context) Close() (err error) {
	if c.child == nil {
		return nil
	}
	defer func() {
		c.child = nil
		err1 := os.RemoveAll(c.appDir)
		if err == nil {
			err = err1
		}
	}()

	if p := c.child.Process; p != nil {
		errc := make(chan error, 1)
		go func() {
			errc <- c.child.Wait()
		}()

		// Call the quit handler on the admin server.
		res, err := http.Get(c.adminURL + "/quit")
		if err != nil {
			p.Kill()
			return fmt.Errorf("unable to call /quit handler: %v", err)
		}
		res.Body.Close()

		select {
		case <-time.After(15 * time.Second):
			p.Kill()
			return errors.New("timeout killing child process")
		case err = <-errc:
			// Do nothing.
		}
	}
	return
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func findPython() (path string, err error) {
	for _, name := range []string{"python2.7", "python"} {
		path, err = exec.LookPath(name)
		if err == nil {
			return
		}
	}
	return
}

func findDevAppserver() (string, error) {
	if p := os.Getenv("APPENGINE_DEV_APPSERVER"); p != "" {
		if fileExists(p) {
			return p, nil
		}
		return "", fmt.Errorf("invalid APPENGINE_DEV_APPSERVER environment variable; path %q doesn't exist", p)
	}
	return exec.LookPath("dev_appserver.py")
}

var apiServerAddrRE = regexp.MustCompile(`Starting API server at: (\S+)`)
var adminServerAddrRE = regexp.MustCompile(`Starting admin server at: (\S+)`)

func (c *context) startChild() (err error) {
	python, err := findPython()
	if err != nil {
		return fmt.Errorf("Could not find python interpreter: %v", err)
	}
	devAppserver, err := findDevAppserver()
	if err != nil {
		return fmt.Errorf("Could not find dev_appserver.py: %v", err)
	}

	c.appDir, err = ioutil.TempDir("", "appengine-aetest")
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			os.RemoveAll(c.appDir)
		}
	}()
	err = ioutil.WriteFile(filepath.Join(c.appDir, "app.yaml"), []byte(c.appYAML()), 0644)
	if err != nil {
		return err
	}
	err = ioutil.WriteFile(filepath.Join(c.appDir, "stubapp.go"), []byte(appSource), 0644)
	if err != nil {
		return err
	}

	c.child = exec.Command(
		python,
		devAppserver,
		"--port=0",
		"--api_port=0",
		"--admin_port=0",
		"--skip_sdk_update_check=true",
		"--clear_datastore=true",
		c.appDir,
	)
	c.child.Stdout = os.Stdout
	var stderr io.Reader
	stderr, err = c.child.StderrPipe()
	if err != nil {
		return err
	}
	stderr = io.TeeReader(stderr, os.Stderr)
	if err = c.child.Start(); err != nil {
		return err
	}

	// Wait until we have read the URL of the API server.
	errc := make(chan error, 1)
	apic := make(chan string)
	adminc := make(chan string)
	go func() {
		s := bufio.NewScanner(stderr)
		for s.Scan() {
			if match := apiServerAddrRE.FindSubmatch(s.Bytes()); match != nil {
				apic <- string(match[1])
			}
			if match := adminServerAddrRE.FindSubmatch(s.Bytes()); match != nil {
				adminc <- string(match[1])
			}
		}
		if err = s.Err(); err != nil {
			errc <- err
		}
	}()

	for c.apiURL == "" || c.adminURL == "" {
		select {
		case c.apiURL = <-apic:
		case c.adminURL = <-adminc:
		case <-time.After(15 * time.Second):
			if p := c.child.Process; p != nil {
				p.Kill()
			}
			return errors.New("timeout starting child process")
		case err := <-errc:
			return fmt.Errorf("error reading child process stderr: %v", err)
		}
	}
	return nil
}

func (c *context) appYAML() string {
	return fmt.Sprintf(appYAMLTemplate, c.appID)
}

const appYAMLTemplate = `
application: %s
version: 1
runtime: go
api_version: go1

handlers:
- url: /.*
  script: _go_app
`

const appSource = `
package nihilist

func init() {}
`
