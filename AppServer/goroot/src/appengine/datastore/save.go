// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"fmt"
	"os"
	"reflect"

	"appengine"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/datastore"
)

const nilKeyErrStr = "nil key"

// valueToProto converts a named value to a newly allocated Property.
// The returned error string is empty on success.
func valueToProto(defaultAppID, name string, v reflect.Value, multiple bool) (p *pb.Property, errStr string) {
	var (
		pv          pb.PropertyValue
		unsupported bool
	)
	switch v.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		pv.Int64Value = proto.Int64(v.Int())
	case reflect.Bool:
		pv.BooleanValue = proto.Bool(v.Bool())
	case reflect.String:
		pv.StringValue = proto.String(v.String())
	case reflect.Float32, reflect.Float64:
		pv.DoubleValue = proto.Float64(v.Float())
	case reflect.Ptr:
		if k, ok := v.Interface().(*Key); ok {
			if k == nil {
				return nil, nilKeyErrStr
			}
			pv.Referencevalue = keyToReferenceValue(defaultAppID, k)
		} else {
			unsupported = true
		}
	case reflect.Slice:
		if b, ok := v.Interface().([]byte); ok {
			pv.StringValue = proto.String(string(b))
		} else {
			// nvToProto should already catch slice values.
			// If we get here, we have a slice of slice values.
			unsupported = true
		}
	default:
		unsupported = true
	}
	if unsupported {
		return nil, "unsupported datastore value type: " + v.Type().String()
	}
	p = &pb.Property{
		Name:     proto.String(name),
		Value:    &pv,
		Multiple: proto.Bool(multiple),
	}
	switch v.Interface().(type) {
	case []byte:
		p.Meaning = pb.NewProperty_Meaning(pb.Property_BLOB)
	case appengine.BlobKey:
		p.Meaning = pb.NewProperty_Meaning(pb.Property_BLOBKEY)
	case Time:
		p.Meaning = pb.NewProperty_Meaning(pb.Property_GD_WHEN)
	}
	return p, ""
}

// addProperty adds propProto to e, as either a Property or a RawProperty of e
// depending on whether or not the property should be indexed.
// In particular, []byte values are raw. All other values are indexed.
func addProperty(e *pb.EntityProto, propProto *pb.Property, propValue reflect.Value) {
	if _, ok := propValue.Interface().([]byte); ok {
		e.RawProperty = append(e.RawProperty, propProto)
	} else {
		e.Property = append(e.Property, propProto)
	}
}

// nameValue holds a string name and a reflect.Value.
type nameValue struct {
	name  string
	value reflect.Value
}

// nvToProto converts a slice of nameValues to a newly allocated EntityProto.
func nvToProto(defaultAppID string, key *Key, typeName string, nv []nameValue) (*pb.EntityProto, os.Error) {
	const errMsg = "datastore: cannot store field named %q from a %q: %s"
	e := &pb.EntityProto{
		Key: keyToProto(defaultAppID, key),
	}
	if key.Incomplete() {
		// EntityGroup is a required proto field.
		e.EntityGroup = &pb.Path{}
	} else {
		e.EntityGroup = keyToProto(defaultAppID, key.root()).Path
	}
	for _, x := range nv {
		_, isBlob := x.value.Interface().([]byte)
		if x.value.Kind() == reflect.Slice && !isBlob {
			// Save each element of the field as a multiple-valued property.
			if x.value.Len() > maxSliceFieldLen {
				return nil, fmt.Errorf(errMsg, x.name, typeName, "slice is too long")
			}
			for j := 0; j < x.value.Len(); j++ {
				elem := x.value.Index(j)
				property, errStr := valueToProto(defaultAppID, x.name, elem, true)
				if errStr == nilKeyErrStr {
					// Skip a nil *Key.
					continue
				}
				if errStr != "" {
					return nil, fmt.Errorf(errMsg, x.name, typeName, errStr)
				}
				addProperty(e, property, elem)
			}
			continue
		}
		// Save the field as a single-valued property.
		property, errStr := valueToProto(defaultAppID, x.name, x.value, false)
		if errStr == nilKeyErrStr {
			// Skip a nil *Key.
			continue
		}
		if errStr != "" {
			return nil, fmt.Errorf(errMsg, x.name, typeName, errStr)
		}
		addProperty(e, property, x.value)
	}
	return e, nil
}

// saveStruct converts an entity struct to a newly allocated EntityProto.
func saveStruct(defaultAppID string, key *Key, sv reflect.Value) (*pb.EntityProto, os.Error) {
	nv := make([]nameValue, sv.NumField())
	n, st := 0, sv.Type()
	for i := 0; i < sv.NumField(); i++ {
		name, value := st.Field(i).Name, sv.Field(i)
		if unexported(name) || !value.IsValid() {
			continue
		}
		nv[n] = nameValue{name, value}
		n++
	}
	return nvToProto(defaultAppID, key, st.Name(), nv[:n])
}

// saveMap converts an entity Map to a newly allocated EntityProto.
func saveMap(defaultAppID string, key *Key, m Map) (*pb.EntityProto, os.Error) {
	nv := make([]nameValue, len(m))
	n := 0
	for k, v := range m {
		nv[n] = nameValue{k, reflect.ValueOf(v)}
		n++
	}
	return nvToProto(defaultAppID, key, "datastore.Map", nv)
}
