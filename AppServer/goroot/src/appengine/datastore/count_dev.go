// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"os"

	"appengine"
)


// Count returns the number of results for the query.
func (q *Query) Count(c appengine.Context) (int, os.Error) {
	// TODO: Drop this and just use the implementation in count_prod.go
	// once the dev_appserver implements the datastore_v3.Count RPC method.
	if q.err != nil {
		return 0, q.err
	}
	i := 0
	for t := q.Run(c); ; {
		_, _, err := t.next()
		if err == Done {
			break
		}
		if err != nil {
			return 0, err
		}
		i++
	}
	return i, nil
}
