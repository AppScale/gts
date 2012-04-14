// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"bytes"
	"strconv"
)

// Key represents the datastore key for a stored entity, and is immutable.
type Key struct {
	kind     string
	stringID string
	intID    int64
	parent   *Key
	appID    string
}

// Kind returns the key's kind (also known as entity type).
func (k *Key) Kind() string {
	return k.kind
}

// StringID returns the key's string ID (also known as an entity name or key
// name), which may be "".
func (k *Key) StringID() string {
	return k.stringID
}

// IntID returns the key's integer ID, which may be 0.
func (k *Key) IntID() int64 {
	return k.intID
}

// Parent returns the key's parent key, which may be nil.
func (k *Key) Parent() *Key {
	return k.parent
}

// AppID returns the key's application ID.
// An empty value means the ID of the running App Engine application.
func (k *Key) AppID() string {
	return k.appID
}

// Incomplete returns whether the key does not refer to a stored entity.
// In particular, whether the key has a zero StringID and a zero IntID.
func (k *Key) Incomplete() bool {
	return k.stringID == "" && k.intID == 0
}

// valid returns whether the key is valid.
func (k *Key) valid() bool {
	if k == nil {
		return false
	}
	for ; k != nil; k = k.parent {
		if k.kind == "" {
			return false
		}
		if k.stringID != "" && k.intID != 0 {
			return false
		}
		if k.parent != nil {
			if k.parent.Incomplete() {
				return false
			}
			if k.parent.appID != k.appID {
				return false
			}
		}
	}
	return true
}

// Eq returns whether two keys are equal.
func (k *Key) Eq(o *Key) bool {
	for k != nil && o != nil {
		if k.kind != o.kind || k.stringID != o.stringID || k.intID != o.intID || k.appID != o.appID {
			return false
		}
		k, o = k.parent, o.parent
	}
	return k == o
}

// root returns the furthest ancestor of a key, which may be itself.
func (k *Key) root() *Key {
	for k.parent != nil {
		k = k.parent
	}
	return k
}

// marshal marshals the key's string representation to the buffer.
func (k *Key) marshal(b *bytes.Buffer) {
	if k.parent != nil {
		k.parent.marshal(b)
	}
	b.WriteByte('/')
	b.WriteString(k.kind)
	b.WriteByte(',')
	if k.stringID != "" {
		b.WriteString(k.stringID)
	} else {
		b.WriteString(strconv.Itoa64(k.intID))
	}
}

// String returns a string representation of the key.
func (k *Key) String() string {
	if k == nil {
		return ""
	}
	b := bytes.NewBuffer(make([]byte, 0, 512))
	k.marshal(b)
	return b.String()
}

// NewIncompleteKey creates a new incomplete key.
// kind cannot be empty.
func NewIncompleteKey(kind string) *Key {
	return &Key{
		kind: kind,
	}
}

// NewKey creates a new key.
// kind cannot be empty.
// Either one or both of stringID and intID must be zero. If both are zero,
// the key returned is incomplete.
// parent must either be a complete key or nil.
func NewKey(kind, stringID string, intID int64, parent *Key) *Key {
	return &Key{
		kind:     kind,
		stringID: stringID,
		intID:    intID,
		parent:   parent,
	}
}
