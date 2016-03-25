// Copyright 2013 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package init provides initialization that must happen before any App Engine
user code runs. It is imported in apps built by go-appengine-builder.
*/
package init

import (
	"errors"
	"net/http"
)

type failingTransport struct{}

func (failingTransport) RoundTrip(*http.Request) (*http.Response, error) {
	return nil, errors.New("http.DefaultTransport and http.DefaultClient are not available in App Engine. " +
		"See https://developers.google.com/appengine/docs/go/urlfetch/overview")
}

func init() {
	// http.DefaultTransport doesn't work in production so break it
	// explicitly so it fails the same way in both dev and prod
	// (and with a useful error message)
	http.DefaultTransport = failingTransport{}
}
