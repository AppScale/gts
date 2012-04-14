// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"fmt"
	"os"
	"reflect"

	"appengine"
	"appengine_internal"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/datastore"
)

// Slice fields over 100 elements long will not be loaded or saved.
const maxSliceFieldLen = 100

// []byte fields more than 1 megabyte long will not be loaded or saved.
const maxBlobLen = 1 << 20

// Time is the number of microseconds since the Unix epoch,
// January 1, 1970 00:00:00 UTC.
//
// It is a distinct type so that loading and saving fields of type Time are
// displayed correctly in App Engine tools like the Admin Console.
type Time int64

// SecondsToTime converts an int64 number of seconds since to Unix epoch
// to a Time value.
func SecondsToTime(n int64) Time {
	return Time(n * 1e6)
}

// Map is a map representation of an entity's fields. It is more flexible than
// but not as strongly typed as a struct representation.
type Map map[string]interface{}

var (
	// ErrInvalidEntityType is returned when an entity is passed that isn't
	// a struct pointer or a Map.
	ErrInvalidEntityType = os.NewError("datastore: invalid entity type was not a struct pointer or a Map")
	// ErrInvalidKey is returned when an invalid key is presented.
	ErrInvalidKey = os.NewError("datastore: invalid key")
	// ErrNoSuchEntity is returned when no entity was found for a given key.
	ErrNoSuchEntity = os.NewError("datastore: no such entity")
)

// ErrFieldMismatch is returned when a field is to be loaded into a different
// type than the one it was stored from, or when a field is missing or
// unexported in the destination struct.
// StructType is the type of the struct pointed to by the destination argument
// passed to Get or to Iterator.Next.
type ErrFieldMismatch struct {
	Key        *Key
	StructType reflect.Type
	FieldName  string
	Reason     string
}

// String returns a string representation of the error.
func (e *ErrFieldMismatch) String() string {
	return fmt.Sprintf("datastore: cannot load field %q from key %q into a %q: %s",
		e.FieldName, e.Key, e.StructType, e.Reason)
}

// protoToKey converts a Reference proto to a *Key.
func protoToKey(r *pb.Reference) (k *Key, err os.Error) {
	appID := proto.GetString(r.App)
	for _, e := range r.Path.Element {
		k = &Key{
			kind:     proto.GetString(e.Type),
			stringID: proto.GetString(e.Name),
			intID:    proto.GetInt64(e.Id),
			parent:   k,
			appID:    appID,
		}
		if !k.valid() {
			return nil, ErrInvalidKey
		}
	}
	return
}

// keyToProto converts a *Key to a Reference proto.
func keyToProto(defaultAppID string, k *Key) *pb.Reference {
	appID := k.appID
	if appID == "" {
		appID = defaultAppID
	}
	n := 0
	for i := k; i != nil; i = i.parent {
		n++
	}
	e := make([]*pb.Path_Element, n)
	for i := k; i != nil; i = i.parent {
		n--
		e[n] = &pb.Path_Element{
			Type: &i.kind,
		}
		// Both Name and Id are optional proto fields, but the App Server expects
		// that exactly one of those fields are set.
		if i.stringID != "" {
			e[n].Name = &i.stringID
		} else {
			e[n].Id = &i.intID
		}
	}
	return &pb.Reference{
		App: proto.String(appID),
		Path: &pb.Path{
			Element: e,
		},
	}
}

// It's unfortunate that the two semantically equivalent concepts pb.Reference
// and pb.PropertyValue_ReferenceValue aren't the same type. For example, the
// two have different protobuf field numbers.

// referenceValueToKey is the same as protoToKey except the input is a
// PropertyValue_ReferenceValue instead of a Reference.
func referenceValueToKey(r *pb.PropertyValue_ReferenceValue) (k *Key, err os.Error) {
	appID := proto.GetString(r.App)
	for _, e := range r.Pathelement {
		k = &Key{
			kind:     proto.GetString(e.Type),
			stringID: proto.GetString(e.Name),
			intID:    proto.GetInt64(e.Id),
			parent:   k,
			appID:    appID,
		}
		if !k.valid() {
			return nil, ErrInvalidKey
		}
	}
	return
}

// keyToReferenceValue is the same as keyToProto except the output is a
// PropertyValue_ReferenceValue instead of a Reference.
func keyToReferenceValue(defaultAppID string, k *Key) *pb.PropertyValue_ReferenceValue {
	ref := keyToProto(defaultAppID, k)
	pe := make([]*pb.PropertyValue_ReferenceValue_PathElement, len(ref.Path.Element))
	for i, e := range ref.Path.Element {
		pe[i] = &pb.PropertyValue_ReferenceValue_PathElement{
			Type: e.Type,
			Id:   e.Id,
			Name: e.Name,
		}
	}
	return &pb.PropertyValue_ReferenceValue{
		App:         ref.App,
		Pathelement: pe,
	}
}

// asStructValue converts a pointer-to-struct to a reflect.Value.
func asStructValue(x interface{}) (reflect.Value, os.Error) {
	pv := reflect.ValueOf(x)
	if pv.Kind() != reflect.Ptr || pv.Elem().Kind() != reflect.Struct {
		return reflect.Value{}, ErrInvalidEntityType
	}
	return pv.Elem(), nil
}

// Get loads the entity stored for k into dst, which may be either a struct
// pointer or a Map. If there is no such entity for the key, Get returns
// ErrNoSuchEntity.
//
// The values of dst's unmatched struct fields or Map entries are not modified.
// In particular, it is recommended to pass either a pointer to a zero valued
// struct or an empty Map on each Get call.
//
// ErrFieldMismatch is returned when a field is to be loaded into a different
// type than the one it was stored from, or when a field is missing or
// unexported in the destination struct. ErrFieldMismatch is only returned if
// dst is a struct pointer.
func Get(c appengine.Context, k *Key, dst interface{}) os.Error {
	if !k.valid() {
		return ErrInvalidKey
	}
	req := &pb.GetRequest{
		Key: []*pb.Reference{
			keyToProto(c.AppID(), k),
		},
	}
	res := &pb.GetResponse{}
	err := c.Call("datastore_v3", "Get", req, res)
	if err != nil {
		return err
	}
	if len(res.Entity) == 0 || res.Entity[0].Entity == nil {
		return ErrNoSuchEntity
	}
	if m, ok := dst.(Map); ok {
		return loadMap(m, k, res.Entity[0].Entity)
	}
	sv, err := asStructValue(dst)
	if err != nil {
		return err
	}
	return loadStruct(sv, k, res.Entity[0].Entity)
}

// Put saves the entity src into the datastore with key k. src may be either a
// struct pointer or a Map; if the former then any unexported fields of that
// struct will be skipped.
// If k is an incomplete key, the returned key will be a unique key
// generated by the datastore.
func Put(c appengine.Context, k *Key, src interface{}) (*Key, os.Error) {
	if !k.valid() {
		return nil, ErrInvalidKey
	}
	var e *pb.EntityProto
	if m, ok := src.(Map); ok {
		var err os.Error
		e, err = saveMap(c.AppID(), k, m)
		if err != nil {
			return nil, err
		}
	} else {
		sv, err := asStructValue(src)
		if err != nil {
			return nil, err
		}
		e, err = saveStruct(c.AppID(), k, sv)
		if err != nil {
			return nil, err
		}
	}
	req := &pb.PutRequest{
		Entity: []*pb.EntityProto{e},
	}
	res := &pb.PutResponse{}
	err := c.Call("datastore_v3", "Put", req, res)
	if err != nil {
		return nil, err
	}
	if len(res.Key) == 0 {
		return nil, os.NewError("datastore: internal error: server did not return a key")
	}
	key, err := protoToKey(res.Key[0])
	if err != nil || key.Incomplete() {
		return nil, os.NewError("datastore: internal error: server returned an invalid key")
	}
	return key, nil
}

// Delete deletes the entity for the given key.
func Delete(c appengine.Context, k *Key) os.Error {
	if !k.valid() {
		return ErrInvalidKey
	}
	req := &pb.DeleteRequest{
		Key: []*pb.Reference{
			keyToProto(c.AppID(), k),
		},
	}
	res := &pb.DeleteResponse{}
	return c.Call("datastore_v3", "Delete", req, res)
}

func init() {
	appengine_internal.RegisterErrorCodeMap("datastore_v3", pb.Error_ErrorCode_name)
}
