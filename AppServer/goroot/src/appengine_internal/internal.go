// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
The appengine_internal package supports Go programs for Google App Engine.

Such programs do not call the this package directly. Instead, the program
consists of one or more packages that register HTTP handlers in their init
function. The App Engine framework will provide a main package that calls this
package correctly to serve HTTP.

The specifics of the generated main package and of this appengine_internal
package will differ when running on a development App Server on a local machine
and when running on an actual App Engine App Server in production, but this is
a private implementation detail. The API is the same in both cases; just write
packages that register HTTP handlers during init.

	package hello

	import (
		"http"
		"io"
	)

	func handleHello(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, "Hello, App Engine")
	}

	func init() {
		http.HandleFunc("/hello", handleHello)
	}
*/
package appengine_internal

import (
	"flag"
	"fmt"
	"http"
	"io"
	"log"
	"strings"
)

var (
	addrHTTP = flag.String("addr_http", "", "net:laddr to listen on for HTTP requests.")
	addrAPI  = flag.String("addr_api", "", "net:raddr to dial for API requests.")
)

type ServeHTTPFunc func(netw, addr string)

var serveHTTPFunc ServeHTTPFunc

func RegisterHTTPFunc(f ServeHTTPFunc) {
	serveHTTPFunc = f
}

// errorCodeMaps is a map of service name to the error code map for the service.
var errorCodeMaps = make(map[string]map[int32]string)

// RegisterErrorCodeMap is called from API implementations to register their
// error code map. This should only be called from init functions.
func RegisterErrorCodeMap(service string, m map[int32]string) {
	errorCodeMaps[service] = m
}

// APIError is the type returned by appengine.Context's Call method
// when an API call fails in an API-specific way. This may be, for instance,
// a taskqueue API call failing with TaskQueueServiceError::UNKNOWN_QUEUE.
type APIError struct {
	Service string
	Detail  string
	Code    int32 // API-specific error code
}

func (e *APIError) String() string {
	if e.Code == 0 {
		return e.Detail
	}
	s := fmt.Sprintf("API error %d", e.Code)
	if m, ok := errorCodeMaps[e.Service]; ok {
		s += " (" + e.Service + ": " + m[e.Code] + ")"
	}
	if e.Detail != "" {
		s += ": " + e.Detail
	}
	return s
}

// CallError is the type returned by appengine.Context's Call method when an
// API call fails in a generic way, such as APIResponse::CAPABILITY_DISABLED.
type CallError struct {
	Detail string
	Code   int32
}

func (e *CallError) String() string {
	if e.Code == 0 {
		return e.Detail
	}
	return fmt.Sprintf("Call error %d: %s", e.Code, e.Detail)
}

// handleHealthCheck handles health check HTTP requests from the App Server.
func handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	io.WriteString(w, "OK")
}

// parseAddr parses a composite address of the form "net:addr".
func parseAddr(compAddr string) (net, addr string) {
	parts := strings.Split(compAddr, ":", 2)
	if len(parts) != 2 {
		log.Fatalf("appengine: bad composite address %q", compAddr)
	}
	return parts[0], parts[1]
}

// Main is designed so that the complete generated main.main package is:
//
//	package main
//
//	import (
//		"path/to/appengine_internal"
//		_ "myapp/package0"
//		_ "myapp/package1"
//	)
//
//	func main() {
//		appengine_internal.Main()
//	}
//
// The "myapp/packageX" packages are expected to register http handlers
// in their init functions.
func Main() {
	// Check flags.
	flag.Parse()
	if *addrHTTP == "" || *addrAPI == "" {
		log.Fatal("appengine_internal.Main should not be called directly. It should only be called from the App Engine App Server.")
	}
	httpNet, httpAddr := parseAddr(*addrHTTP)
	apiNet, apiAddr := parseAddr(*addrAPI)

	// Forward App Engine API calls to the appserver.
	initAPI(apiNet, apiAddr)

	// Serve HTTP requests forwarded from the appserver to us.
	http.HandleFunc("/_appengine_delegate_health_check", handleHealthCheck)
	if serveHTTPFunc == nil {
		log.Fatal("appengine: no ServeHTTPFunc registered.")
	}
	serveHTTPFunc(httpNet, httpAddr)
}
