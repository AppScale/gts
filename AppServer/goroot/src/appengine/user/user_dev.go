// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package user

import (
	"http"

	"appengine"
)

const (
	hEmail             = "X-AppEngine-Inbound-User-Email"
	hFederatedIdentity = "X-AppEngine-Inbound-User-Federated-Identity"
	hFederatedProvider = "X-AppEngine-Inbound-User-Federated-Provider"
	hId                = "X-AppEngine-Inbound-User-Id"
	hIsAdmin           = "X-AppEngine-Inbound-User-Is-Admin"
)

func current(c appengine.Context) *User {
	hdr := c.Request().(http.Header)
	return &User{
		Email:             hdr.Get(hEmail),
		Id:                hdr.Get(hId),
		FederatedIdentity: hdr.Get(hFederatedIdentity),
		FederatedProvider: hdr.Get(hFederatedProvider),
	}
}

func isAdmin(c appengine.Context) bool {
	return c.Request().(http.Header).Get(hIsAdmin) == "1"
}
