// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package counter

import (
	"fmt"
	"http"
	"io"
	"os"
	"strconv"

	"appengine"
	"appengine/memcache"
)

func serveError(c appengine.Context, w http.ResponseWriter, err os.Error) {
	w.WriteHeader(http.StatusInternalServerError)
	w.Header().Set("Content-Type", "text/plain")
	io.WriteString(w, "Internal Server Error")
	c.Logf("%v", err)
}

func handle(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)

	item, err := memcache.Get(c, r.URL.Path)
	if err != nil && err != memcache.ErrCacheMiss {
		serveError(c, w, err)
		return
	}
	n := 0
	if err == nil {
		n, err = strconv.Atoi(string(item.Value))
		if err != nil {
			serveError(c, w, err)
			return
		}
	}
	n++
	item = &memcache.Item{
		Key:   r.URL.Path,
		Value: []byte(strconv.Itoa(n)),
	}
	err = memcache.Set(c, item)
	if err != nil {
		serveError(c, w, err)
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "%q has been visited %d times", r.URL.Path, n)
}

func init() {
	http.HandleFunc("/", handle)
}
