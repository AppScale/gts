// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

// The appengine package provides functionality that is common across
// App Engine APIs.
package appengine

import (
	"http"
	"os"

	"appengine_internal"
)

// IsDevAppServer returns whether the App Engine app is running in the
// development App Server.
func IsDevAppServer() bool {
	return appengine_internal.IsDevAppServer()
}

// Context represents the context of an in-flight HTTP request.
type Context interface {
	// Call implements App Engine API calls.
	// Developer-facing APIs wrap Call to provide a more friendly API.
	Call(service, method string, in, out interface{}) os.Error

	// Request returns environment-dependent request information.
	Request() interface{}

	// Logf formats its arguments according to the format, analogous to fmt.Printf,
	// and records the text as a log message.
	Logf(format string, args ...interface{})

	// AppID returns the application ID for the current application.
	AppID() string
}

// NewContext returns a new context for an in-flight HTTP request.
func NewContext(req *http.Request) Context {
	return appengine_internal.NewContext(req)
}

// BlobKey is a key for a blobstore blob.
//
// Conceptually, this type belongs in the blobstore package, but it lives in
// the appengine package to avoid a circular dependency: blobstore depends on
// datastore, and datastore needs to refer to the BlobKey type.
type BlobKey string
