// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
The datastore package provides a client for App Engine's datastore service.

Entities are the unit of storage and are associated with a key. A key
consists of an optional parent key, a string application ID, a string kind
(also known as an entity type), and either a StringID or an IntID. A
StringID is also known as an entity name or key name.

It is valid to create a key with a zero StringID and a zero IntID; this is
called an incomplete key, and does not refer to any saved entity. Putting an
entity into the datastore under an incomplete key will cause a unique key
to be generated for that entity, with a non-zero IntID.

An entity's contents are a mapping from case-sensitive field names to values.
Valid value types are:
  - signed integers (int, int8, int16, int32 and int64),
  - bool,
  - string,
  - float32 and float64,
  - any type whose underlying type is one of the above predeclared types,
  - *Key,
  - appengine.BlobKey,
  - []byte (up to 1 megabyte in length),
  - slices of any of the above (up to 100 elements in length).

The Get and Put functions load and save an entity's contents to and from
structs or Maps. Structs are more strongly typed, Maps are more flexible. The
actual types passed do not have to match between calls or even across different
App Engine requests. It is valid to put a Map and get that same entity as a
struct, or put a struct of type T0 and get a struct of type T1. Conceptually,
an entity is saved from a struct as a map and is loaded into a struct or Map on
a field-by-field basis. When loading into a struct, an entity that cannot be
completely represented (such as a missing field) will result in an error but it
is up to the caller whether this error is fatal, recoverable or ignorable.

Example code:

	type Entity struct {
		Value string
	}

	func handle(w http.ResponseWriter, r *http.Request) {
		c := appengine.NewContext(r)

		k := datastore.NewKey("Entity", "stringID", 0, nil)
		e := new(Entity)
		if err := datastore.Get(c, k, e); err != nil {
			serveError(w, err)
			return
		}

		old := e.Value
		e.Value = r.URL.Path

		if _, err := datastore.Put(c, k, e); err != nil {
			serveError(w, err)
			return
		}

		w.SetHeader("Content-Type", "text/plain")
		fmt.Fprintf(w, "old=%q\nnew=%q\n", old, e.Value)
	}

To derive example code that saves and loads a Map instead of a struct, replace
e := new(Entity) and e.Value with e := make(datastore.Map) and e["Value"].

Queries are created using datastore.NewQuery and are configured
by calling its methods. Running a query yields an iterator of
results: either an iterator of keys or of (key, entity) pairs. Once
initialized, query values can be re-used, and it is safe to call
Query.Run from concurrent goroutines.

Example code:

	type Widget struct {
		Description string
		Price       int
	}

	func handle(w http.ResponseWriter, r *http.Request) {
		c := appengine.NewContext(r)
		q := datastore.NewQuery("Widget").
			Filter("Price <", 1000).
			Order("-Price")
		b := bytes.NewBuffer(nil)
		for t := q.Run(c); ; {
			var x Widget
			key, err := t.Next(&x)
			if err == datastore.Done {
				break
			}
			if err != nil {
				serveError(w, err)
				return
			}
			fmt.Fprintf(b, "Key=%v\nWidget=%#v\n\n", x, key)
		}
		w.SetHeader("Content-Type", "text/plain")
		io.Copy(w, b)
	}
*/
package datastore

// TODO: batch operations, transactions.
