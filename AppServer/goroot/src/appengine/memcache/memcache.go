// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

// The memcache package provides a client for App Engine's distributed in-
// memory key-value store for small chunks of arbitrary data.
//
// The fundamental operations get and set items, keyed by a string.
//
//	item0, err := memcache.Get(c, "key")
//	if err != nil && err != memcache.ErrCacheMiss {
//		return err
//	}
//	if err == nil {
//		fmt.Fprintf(w, "memcache hit: Key=%q Val=[% x]\n", item0.Key, item0.Value)
//	} else {
//		fmt.Fprintf(w, "memcache miss\n")
//	}
//
// and
//
//	item1 := &memcache.Item{
//		Key:   "foo",
//		Value: []byte("bar"),
//	}
//	if err := memcache.Set(c, item1); err != nil {
//		return err
//	}
package memcache

import (
	"bytes"
	"gob"
	"json"
	"os"

	"appengine"
	"appengine_internal"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/memcache"
)

var (
	// ErrCacheMiss means that a Get failed because the item wasn't present.
	ErrCacheMiss = os.NewError("memcache: cache miss")
	// ErrCASConflict means that a CompareAndSwap call failed due to the
	// cached value being modified between the Get and the CompareAndSwap.
	// If the cached value was simply evicted rather than replaced,
	// ErrNotStored will be returned instead.
	ErrCASConflict = os.NewError("memcache: compare-and-swap conflict")
	// ErrNotStored means that a conditional write operation (i.e. Add or
	// CompareAndSwap) failed because the condition was not satisfied.
	ErrNotStored = os.NewError("memcache: item not stored")
	// ErrServer means that a server error occurred.
	ErrServerError = os.NewError("memcache: server error")
)

// Item is the unit of memcache gets and sets.
type Item struct {
	// Key is the Item's key (250 bytes maximum).
	Key string
	// Value is the Item's value.
	Value []byte
	// Object is the Item's value for use with a Codec.
	Object interface{}
	// Flags are server-opaque flags whose semantics are entirely up to the
	// App Engine app.
	Flags uint32
	// Expiration is the cache expiration time, in seconds: either a relative
	// time from now (up to 1 month), or an absolute Unix epoch time.
	// Zero means the Item has no expiration time.
	Expiration int32
	// casID is a client-opaque value used for compare-and-swap operations.
	// Zero means that compare-and-swap is not used.
	casID uint64
}

// protoToItem converts a protocol buffer item to a Go struct.
func protoToItem(p *pb.MemcacheGetResponse_Item) *Item {
	return &Item{
		Key:        string(p.Key),
		Value:      p.Value,
		Flags:      proto.GetUint32(p.Flags),
		Expiration: proto.GetInt32(p.ExpiresInSeconds),
		casID:      proto.GetUint64(p.CasId),
	}
}

// Get gets the item for the given key. ErrCacheMiss is returned for a memcache
// cache miss. The key must be at most 250 bytes in length.
func Get(c appengine.Context, key string) (*Item, os.Error) {
	m, err := GetMulti(c, []string{key})
	if err != nil {
		return nil, err
	}
	if _, ok := m[key]; !ok {
		return nil, ErrCacheMiss
	}
	return m[key], nil
}

// GetMulti is a batch version of Get. The returned map from keys to items may
// have fewer elements than the input slice, due to memcache cache misses.
// Each key must be at most 250 bytes in length.
func GetMulti(c appengine.Context, key []string) (map[string]*Item, os.Error) {
	keyAsBytes := make([][]byte, len(key))
	for i, k := range key {
		keyAsBytes[i] = []byte(k)
	}
	req := &pb.MemcacheGetRequest{
		Key:    keyAsBytes,
		ForCas: proto.Bool(true),
	}
	res := &pb.MemcacheGetResponse{}
	if err := c.Call("memcache", "Get", req, res); err != nil {
		return nil, err
	}
	m := make(map[string]*Item, len(res.Item))
	for _, p := range res.Item {
		t := protoToItem(p)
		m[t.Key] = t
	}
	return m, nil
}

// set sets the given items using the given conflict resolution policy.
// The returned slice will have the same length as the input slice.
// If value is not nil, each element should correspond to an item.
func set(c appengine.Context, item []*Item, value [][]byte, policy int32) []os.Error {
	req := &pb.MemcacheSetRequest{
		Item: make([]*pb.MemcacheSetRequest_Item, len(item)),
	}
	for i, t := range item {
		p := &pb.MemcacheSetRequest_Item{
			Key: []byte(t.Key),
		}
		if value == nil {
			p.Value = t.Value
		} else {
			p.Value = value[i]
		}
		if t.Flags != 0 {
			p.Flags = proto.Uint32(t.Flags)
		}
		if t.Expiration != 0 {
			// In the .proto file, MemcacheSetRequest_Item uses a fixed32 (i.e. unsigned)
			// for expiration time, while MemcacheGetRequest_Item uses int32 (i.e. signed).
			// Throughout this .go file, we use int32.
			p.ExpirationTime = proto.Uint32(uint32(t.Expiration))
		}
		if t.casID != 0 {
			p.CasId = proto.Uint64(t.casID)
			p.ForCas = proto.Bool(true)
		}
		p.SetPolicy = pb.NewMemcacheSetRequest_SetPolicy(policy)
		req.Item[i] = p
	}
	res := &pb.MemcacheSetResponse{}
	e := make([]os.Error, len(item))
	if err := c.Call("memcache", "Set", req, res); err != nil {
		for i := range e {
			e[i] = err
		}
		return e
	}
	if len(e) != len(res.SetStatus) {
		for i := range e {
			e[i] = ErrServerError
		}
		return e
	}
	for i := range e {
		switch res.SetStatus[i] {
		case pb.MemcacheSetResponse_STORED:
			e[i] = nil
		case pb.MemcacheSetResponse_NOT_STORED:
			e[i] = ErrNotStored
		case pb.MemcacheSetResponse_EXISTS:
			e[i] = ErrCASConflict
		default:
			e[i] = ErrServerError
		}
	}
	return e
}

// Set writes the given item, unconditionally.
func Set(c appengine.Context, item *Item) os.Error {
	return set(c, []*Item{item}, nil, pb.MemcacheSetRequest_SET)[0]
}

// SetMulti is a batch version of Set.
// The returned slice will have the same length as the input slice.
func SetMulti(c appengine.Context, item []*Item) []os.Error {
	return set(c, item, nil, pb.MemcacheSetRequest_SET)
}

// Add writes the given item, if no value already exists for its key.
// ErrNotStored is returned if that condition is not met.
func Add(c appengine.Context, item *Item) os.Error {
	return set(c, []*Item{item}, nil, pb.MemcacheSetRequest_ADD)[0]
}

// AddMulti is a batch version of Add.
// The returned slice will have the same length as the input slice.
func AddMulti(c appengine.Context, item []*Item) []os.Error {
	return set(c, item, nil, pb.MemcacheSetRequest_ADD)
}

// CompareAndSwap writes the given item that was previously returned by Get,
// if the value was neither modified or evicted between the Get and the
// CompareAndSwap calls. The item's Key should not change between calls but
// all other item fields may differ.
// ErrCASConflict is returned if the value was modified in between the calls.
// ErrNotStored is returned if the value was evicted in between the calls.
func CompareAndSwap(c appengine.Context, item *Item) os.Error {
	return set(c, []*Item{item}, nil, pb.MemcacheSetRequest_CAS)[0]
}

// CompareAndSwapMulti is a batch version of CompareAndSwap.
// The returned slice will have the same length as the input slice.
func CompareAndSwapMulti(c appengine.Context, item []*Item) []os.Error {
	return set(c, item, nil, pb.MemcacheSetRequest_CAS)
}

// Codec represents a symmetric pair of functions that implement a codec.
// Items stored into or retrieved from memcache using a Codec have their
// values marshaled or unmarshaled.
type Codec struct {
	Marshal   func(interface{}) ([]byte, os.Error)
	Unmarshal func([]byte, interface{}) os.Error
}

func (cd Codec) Get(c appengine.Context, key string, v interface{}) (*Item, os.Error) {
	i, err := Get(c, key)
	if err != nil {
		return nil, err
	}
	if err := cd.Unmarshal(i.Value, v); err != nil {
		return nil, err
	}
	return i, nil
}

func (cd Codec) set(c appengine.Context, item *Item, policy int32) os.Error {
	value, err := cd.Marshal(item.Object)
	if err != nil {
		return err
	}

	return set(c, []*Item{item}, [][]byte{value}, policy)[0]
}

func (cd Codec) Set(c appengine.Context, item *Item) os.Error {
	return cd.set(c, item, pb.MemcacheSetRequest_SET)
}

func (cd Codec) Add(c appengine.Context, item *Item) os.Error {
	return cd.set(c, item, pb.MemcacheSetRequest_ADD)
}

var (
	// Gob is a Codec that uses the gob package.
	Gob = Codec{gobMarshal, gobUnmarshal}
	// JSON is a Codec that uses the json package.
	JSON = Codec{json.Marshal, json.Unmarshal}
)

func gobMarshal(v interface{}) ([]byte, os.Error) {
	var buf bytes.Buffer
	if err := gob.NewEncoder(&buf).Encode(v); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func gobUnmarshal(data []byte, v interface{}) os.Error {
	return gob.NewDecoder(bytes.NewBuffer(data)).Decode(v)
}

func init() {
	appengine_internal.RegisterErrorCodeMap("memcache", pb.MemcacheServiceError_ErrorCode_name)
}
