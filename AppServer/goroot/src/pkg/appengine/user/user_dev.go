// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package user

import (
	"net/http"

	"appengine"
)

const (
	hEmail             = "X-AppEngine-Internal-User-Email"
	hFederatedIdentity = "X-AppEngine-Internal-User-Federated-Identity"
	hFederatedProvider = "X-AppEngine-Internal-User-Federated-Provider"
	hID                = "X-AppEngine-Internal-User-Id"
	hIsAdmin           = "X-AppEngine-Internal-User-Is-Admin"
)

func current(c appengine.Context) *User {
	hdr := c.Request().(*http.Request).Header
	return &User{
		Email:             hdr.Get(hEmail),
		ID:                hdr.Get(hID),
		Admin:             hdr.Get(hIsAdmin) == "1",
		FederatedIdentity: hdr.Get(hFederatedIdentity),
		FederatedProvider: hdr.Get(hFederatedProvider),
	}
}

func isAdmin(c appengine.Context) bool {
	return c.Request().(*http.Request).Header.Get(hIsAdmin) == "1"
}
