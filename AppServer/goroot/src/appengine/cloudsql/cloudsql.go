// Copyright 2013 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package cloudsql exposes access to Google Cloud SQL databases.

This package is intended for MySQL drivers to make App Engine-specific connections.

Applications should use this package through database/sql:
Select a pure Go MySQL driver that supports this package, and use sql.Open
with protocol "cloudsql" and an address of the CloudSQL instance.
The exact format of the second argument to sql.Open is driver-dependent;
consult the driver's documentation for details.

Example:
	import "database/sql"
	import _ "<some mysql package>"

	db, err := sql.Open("mysql", "cloudsql:my-instance*dbname/user/passwd")
*/
package cloudsql

import (
	"net"
)

// Dial connects to the named Cloud SQL instance.
func Dial(instance string) (net.Conn, error) {
	return connect(instance)
}
