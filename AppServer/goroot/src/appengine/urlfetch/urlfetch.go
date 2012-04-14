// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

// The urlfetch package provides an http.RoundTripper implementation
// for fetching URLs via App Engine's urlfetch service.
package urlfetch

import (
	"fmt"
	"http"
	"io/ioutil"
	"os"
	"strconv"

	"appengine"
	"appengine_internal"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/urlfetch"
)

// Transport is an implementation of http.RoundTripper for
// App Engine. Users should generally create an http.Client using
// this transport and use the Client rather than using this transport
// directly.
type Transport struct {
	Context                       appengine.Context
	DeadlineSeconds               float64 // zero means App Engine's default
	AllowInvalidServerCertificate bool
}

// Verify statically that *Transport implements http.RoundTripper.
var _ http.RoundTripper = (*Transport)(nil)

// Client returns an *http.Client using a default urlfetch Transport.
func Client(context appengine.Context) *http.Client {
	return &http.Client{
		Transport: &Transport{
			Context: context,
		},
	}
}

// ErrFetch represents an error fetching a URL.
type ErrFetch struct {
	Message string
}

func (e *ErrFetch) String() string {
	return fmt.Sprintf("urlfetch error: %s", e.Message)
}

// ErrInvalidFetchRequest represents an invalid fetch request.
type ErrInvalidFetchRequest struct {
	Message string
	Error   os.Error
}

func (e *ErrInvalidFetchRequest) String() string {
	return fmt.Sprintf("urlfetch invalid input error: %s: %v", e.Message, e.Error)
}

type bodyReader struct {
	content   []byte
	truncated bool
	closed    bool
}

// ErrTruncatedBody is the error returned after the final Read() from a
// response's Body if the body has been truncated by App Engine's proxy.
//
// ErrTruncatedBody is only returned once. Subsequent reads will
// return os.EOF.
var ErrTruncatedBody = os.NewError("urlfetch: truncated body")

func statusCodeToText(code int) string {
	if t := http.StatusText(code); t != "" {
		return t
	}
	return strconv.Itoa(code)
}

func (br *bodyReader) Read(p []byte) (n int, err os.Error) {
	if br.closed {
		return 0, os.EOF
	}
	n = copy(p, br.content)
	if n > 0 {
		br.content = br.content[n:]
		return
	}
	if br.truncated {
		br.closed = true
		return 0, ErrTruncatedBody
	}
	return 0, os.EOF
}

func (br *bodyReader) Close() os.Error {
	br.closed = true
	br.content = nil
	return nil
}

// A map of the URL Fetch-accepted methods that take a request body.
var methodAcceptsRequestBody = map[string]bool{
	"POST": true,
	"PUT":  true,
}

// RoundTrip issues a single HTTP request and returns its response. Per the
// http.RoundTripper interface, RoundTrip only returns an error if there
// was a problem with the request being malformed
// (ErrInvalidFetchRequest) or the URL Fetch proxy fails (ErrFetch).
// Note that HTTP response codes such as 5xx, 403, 404, etc are not
// errors as far as the transport is concerned and will be returned
// with err set to nil.
func (t *Transport) RoundTrip(req *http.Request) (res *http.Response, err os.Error) {
	methNum, ok := pb.URLFetchRequest_RequestMethod_value[req.Method]
	if !ok {
		return nil, &ErrInvalidFetchRequest{"Unsupported method: " + req.Method, nil}
	}

	method := pb.URLFetchRequest_RequestMethod(methNum)

	freq := &pb.URLFetchRequest{
		Method:                        &method,
		Url:                           proto.String(req.URL.String()),
		FollowRedirects:               proto.Bool(false), // http.Client's responsibility
		MustValidateServerCertificate: proto.Bool(!t.AllowInvalidServerCertificate),
	}

	if t.DeadlineSeconds != 0 {
		freq.Deadline = proto.Float64(t.DeadlineSeconds)
	}

	for k, vals := range req.Header {
		for _, val := range vals {
			freq.Header = append(freq.Header, &pb.URLFetchRequest_Header{
				Key:   proto.String(k),
				Value: proto.String(val),
			})
		}
	}
	if methodAcceptsRequestBody[req.Method] {
		freq.Payload, err = ioutil.ReadAll(req.Body)
		if err != nil {
			return nil, &ErrInvalidFetchRequest{"Failed to read body", err}
		}
	}

	fres := &pb.URLFetchResponse{}
	if err := t.Context.Call("urlfetch", "Fetch", freq, fres); err != nil {
		return nil, &ErrFetch{err.String()}
	}

	res = &http.Response{}
	res.StatusCode = int(*fres.StatusCode)
	res.Status = fmt.Sprintf("%d %s", res.StatusCode, statusCodeToText(res.StatusCode))
	res.Header = http.Header(make(map[string][]string))
	res.RequestMethod = req.Method

	// Faked:
	res.ProtoMajor = 1
	res.ProtoMinor = 1
	res.Proto = "HTTP/1.1"
	res.Close = true

	for _, h := range fres.Header {
		hkey := http.CanonicalHeaderKey(*h.Key)
		hval := *h.Value
		if hkey == "Content-Length" {
			// Will get filled in below for all but HEAD requests.
			if req.Method == "HEAD" {
				res.ContentLength, _ = strconv.Atoi64(hval)
			}
			continue
		}
		res.Header.Add(hkey, hval)
	}

	if req.Method != "HEAD" {
		res.ContentLength = int64(len(fres.Content))
	}

	truncated := proto.GetBool(fres.ContentWasTruncated)
	res.Body = &bodyReader{content: fres.Content, truncated: truncated}
	return
}

func init() {
	appengine_internal.RegisterErrorCodeMap("urlfetch", pb.URLFetchServiceError_ErrorCode_name)
}
