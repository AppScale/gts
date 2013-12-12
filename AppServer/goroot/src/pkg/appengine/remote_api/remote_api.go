// Copyright 2012 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package remote_api implements the /_ah/remote_api endpoint.
This endpoint is used by offline tools such as the bulk loader.
*/
package remote_api

import (
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"strconv"

	"appengine"
	"appengine/user"
	"appengine_internal"
	pb "appengine_internal/remote_api"
	"code.google.com/p/goprotobuf/proto"
)

func init() {
	http.HandleFunc("/_ah/remote_api", handle)
}

func handle(w http.ResponseWriter, req *http.Request) {
	c := appengine.NewContext(req)

	if !user.IsAdmin(c) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusUnauthorized)
		io.WriteString(w, "You must be logged in as an administrator to access this.\n")
		return
	}
	if req.Header.Get("X-Appcfg-Api-Version") == "" {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusForbidden)
		io.WriteString(w, "This request did not contain a necessary header.\n")
		return
	}

	if req.Method != "POST" {
		// Response must be YAML.
		rtok := req.FormValue("rtok")
		if rtok == "" {
			rtok = "0"
		}
		w.Header().Set("Content-Type", "text/yaml; charset=utf-8")
		fmt.Fprintf(w, `{app_id: %q, rtok: %q}`, c.FullyQualifiedAppID(), rtok)
		return
	}

	defer req.Body.Close()
	body, err := ioutil.ReadAll(req.Body)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		c.Errorf("Failed reading body: %v", err)
		return
	}
	remReq := &pb.Request{}
	if err := proto.Unmarshal(body, remReq); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		c.Errorf("Bad body: %v", err)
		return
	}

	// Only allow datastore_v3 for now, or AllocateIds for datastore_v4.
	service, method := *remReq.ServiceName, *remReq.Method
	ok := service == "datastore_v3" || (service == "datastore_v4" && method == "AllocateIds")
	if !ok {
		w.WriteHeader(http.StatusBadRequest)
		c.Errorf("Unsupported RPC /%s.%s", service, method)
		return
	}

	rawReq := &rawMessage{remReq.Request}
	rawRes := &rawMessage{}
	err = c.Call(service, method, rawReq, rawRes, nil)

	remRes := &pb.Response{}
	if err == nil {
		remRes.Response = rawRes.buf
	} else if ae, ok := err.(*appengine_internal.APIError); ok {
		remRes.ApplicationError = &pb.ApplicationError{
			Code:   &ae.Code,
			Detail: &ae.Detail,
		}
	} else {
		// This shouldn't normally happen.
		c.Errorf("appengine/remote_api: Unexpected error of type %T: %v", err, err)
		remRes.ApplicationError = &pb.ApplicationError{
			Code:   proto.Int32(0),
			Detail: proto.String(err.Error()),
		}
	}
	out, err := proto.Marshal(remRes)
	if err != nil {
		// This should not be possible.
		w.WriteHeader(500)
		c.Errorf("proto.Marshal: %v", err)
		return
	}

	c.Infof("Spooling %d bytes of response to /%s.%s", len(out), service, method)
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Length", strconv.Itoa(len(out)))
	w.Write(out)
}

// rawMessage is a protocol buffer type that is already serialised.
// This allows the remote_api code here to handle messages
// without having to know the real type.
type rawMessage struct {
	buf []byte
}

func (rm *rawMessage) Marshal() ([]byte, error) {
	return rm.buf, nil
}

func (rm *rawMessage) Unmarshal(buf []byte) error {
	rm.buf = make([]byte, len(buf))
	copy(rm.buf, buf)
	return nil
}

// Methods to satisfy proto.Message.
func (rm *rawMessage) Reset()         { rm.buf = nil }
func (rm *rawMessage) String() string { return strconv.Quote(string(rm.buf)) }
func (*rawMessage) ProtoMessage()     {}
