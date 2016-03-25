// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"fmt"
	"reflect"
	"time"

	"appengine"

	pb "appengine_internal/datastore"
)

var (
	typeOfBlobKey   = reflect.TypeOf(appengine.BlobKey(""))
	typeOfByteSlice = reflect.TypeOf([]byte(nil))
	typeOfTime      = reflect.TypeOf(time.Time{})
)

// typeMismatchReason returns a string explaining why the property p could not
// be stored in an entity field of type v.Type().
func typeMismatchReason(p Property, v reflect.Value) string {
	entityType := "empty"
	switch p.Value.(type) {
	case int64:
		entityType = "int"
	case bool:
		entityType = "bool"
	case string:
		entityType = "string"
	case float64:
		entityType = "float"
	case *Key:
		entityType = "*datastore.Key"
	case time.Time:
		entityType = "time.Time"
	case appengine.BlobKey:
		entityType = "appengine.BlobKey"
	case []byte:
		entityType = "[]byte"
	}
	return fmt.Sprintf("type mismatch: %s versus %v", entityType, v.Type())
}

type propertyLoader struct {
	// m holds the number of times a substruct field like "Foo.Bar.Baz" has
	// been seen so far. The map is constructed lazily.
	m map[string]int
}

func (l *propertyLoader) load(codec *structCodec, structValue reflect.Value, p Property, requireSlice bool) string {
	var v reflect.Value
	// Traverse a struct's struct-typed fields.
	for name := p.Name; ; {
		decoder, ok := codec.byName[name]
		if !ok {
			return "no such struct field"
		}
		v = structValue.Field(decoder.index)
		if !v.IsValid() {
			return "no such struct field"
		}
		if !v.CanSet() {
			return "cannot set struct field"
		}

		if decoder.substructCodec == nil {
			break
		}

		if v.Kind() == reflect.Slice {
			if l.m == nil {
				l.m = make(map[string]int)
			}
			index := l.m[p.Name]
			l.m[p.Name] = index + 1
			for v.Len() <= index {
				v.Set(reflect.Append(v, reflect.New(v.Type().Elem()).Elem()))
			}
			structValue = v.Index(index)
			requireSlice = false
		} else {
			structValue = v
		}
		// Strip the "I." from "I.X".
		name = name[len(codec.byIndex[decoder.index].name):]
		codec = decoder.substructCodec
	}

	var slice reflect.Value
	if v.Kind() == reflect.Slice && v.Type() != typeOfByteSlice {
		slice = v
		v = reflect.New(v.Type().Elem()).Elem()
	} else if requireSlice {
		return "multiple-valued property requires a slice field type"
	}

	// Convert indexValues to a Go value with a meaning derived from the
	// destination type.
	pValue := p.Value
	if iv, ok := pValue.(indexValue); ok {
		meaning := pb.Property_NO_MEANING
		switch v.Type() {
		case typeOfBlobKey:
			meaning = pb.Property_BLOBKEY
		case typeOfByteSlice:
			meaning = pb.Property_BLOB
		case typeOfTime:
			meaning = pb.Property_GD_WHEN
		}
		var err error
		pValue, err = propValue(iv.value, meaning)
		if err != nil {
			return err.Error()
		}
	}

	switch v.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		x, ok := pValue.(int64)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		if v.OverflowInt(x) {
			return fmt.Sprintf("value %v overflows struct field of type %v", x, v.Type())
		}
		v.SetInt(x)
	case reflect.Bool:
		x, ok := pValue.(bool)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		v.SetBool(x)
	case reflect.String:
		if x, ok := pValue.(appengine.BlobKey); ok {
			v.SetString(string(x))
			break
		}
		x, ok := pValue.(string)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		v.SetString(x)
	case reflect.Float32, reflect.Float64:
		x, ok := pValue.(float64)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		if v.OverflowFloat(x) {
			return fmt.Sprintf("value %v overflows struct field of type %v", x, v.Type())
		}
		v.SetFloat(x)
	case reflect.Ptr:
		x, ok := pValue.(*Key)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		if _, ok := v.Interface().(*Key); !ok {
			return typeMismatchReason(p, v)
		}
		v.Set(reflect.ValueOf(x))
	case reflect.Struct:
		x, ok := pValue.(time.Time)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		if _, ok := v.Interface().(time.Time); !ok {
			return typeMismatchReason(p, v)
		}
		v.Set(reflect.ValueOf(x))
	case reflect.Slice:
		x, ok := pValue.([]byte)
		if !ok && pValue != nil {
			return typeMismatchReason(p, v)
		}
		if _, ok := v.Interface().([]byte); !ok {
			return typeMismatchReason(p, v)
		}
		v.Set(reflect.ValueOf(x))
	default:
		return typeMismatchReason(p, v)
	}
	if slice.IsValid() {
		slice.Set(reflect.Append(slice, v))
	}
	return ""
}

// loadEntity loads an EntityProto into PropertyLoadSaver or struct pointer.
func loadEntity(dst interface{}, src *pb.EntityProto) (err error) {
	c := make(chan Property, 32)
	errc := make(chan error, 1)
	defer func() {
		if err == nil {
			err = <-errc
		}
	}()
	go protoToProperties(c, errc, src)
	if e, ok := dst.(PropertyLoadSaver); ok {
		return e.Load(c)
	}
	return LoadStruct(dst, c)
}

func (s structPLS) Load(c <-chan Property) error {
	var fieldName, reason string
	var l propertyLoader
	for p := range c {
		if errStr := l.load(s.codec, s.v, p, p.Multiple); errStr != "" {
			// We don't return early, as we try to load as many properties as possible.
			// It is valid to load an entity into a struct that cannot fully represent it.
			// That case returns an error, but the caller is free to ignore it.
			fieldName, reason = p.Name, errStr
		}
	}
	if reason != "" {
		return &ErrFieldMismatch{
			StructType: s.v.Type(),
			FieldName:  fieldName,
			Reason:     reason,
		}
	}
	return nil
}

func protoToProperties(dst chan<- Property, errc chan<- error, src *pb.EntityProto) {
	defer close(dst)
	props, rawProps := src.Property, src.RawProperty
	for {
		var (
			x       *pb.Property
			noIndex bool
		)
		if len(props) > 0 {
			x, props = props[0], props[1:]
		} else if len(rawProps) > 0 {
			x, rawProps = rawProps[0], rawProps[1:]
			noIndex = true
		} else {
			break
		}

		var value interface{}
		if x.Meaning != nil && *x.Meaning == pb.Property_INDEX_VALUE {
			value = indexValue{x.Value}
		} else {
			var err error
			value, err = propValue(x.Value, x.GetMeaning())
			if err != nil {
				errc <- err
				return
			}
		}
		dst <- Property{
			Name:     x.GetName(),
			Value:    value,
			NoIndex:  noIndex,
			Multiple: x.GetMultiple(),
		}
	}
	errc <- nil
}

// propValue returns a Go value that combines the raw PropertyValue with a
// meaning. For example, an Int64Value with GD_WHEN becomes a time.Time.
func propValue(v *pb.PropertyValue, m pb.Property_Meaning) (interface{}, error) {
	switch {
	case v.Int64Value != nil:
		if m == pb.Property_GD_WHEN {
			return fromUnixMicro(*v.Int64Value), nil
		} else {
			return *v.Int64Value, nil
		}
	case v.BooleanValue != nil:
		return *v.BooleanValue, nil
	case v.StringValue != nil:
		if m == pb.Property_BLOB {
			return []byte(*v.StringValue), nil
		} else if m == pb.Property_BLOBKEY {
			return appengine.BlobKey(*v.StringValue), nil
		} else {
			return *v.StringValue, nil
		}
	case v.DoubleValue != nil:
		return *v.DoubleValue, nil
	case v.Referencevalue != nil:
		key, err := referenceValueToKey(v.Referencevalue)
		if err != nil {
			return nil, err
		}
		return key, nil
	}
	return nil, nil
}

// indexValue is a Property value that is created when entities are loaded from
// an index, such as from a projection query.
//
// Such Property values do not contain all of the metadata required to be
// faithfully represented as a Go value, and are instead represented as an
// opaque indexValue. Load the properties into a concrete struct type (e.g. by
// passing a struct pointer to Iterator.Next) to reconstruct actual Go values
// of type int, string, time.Time, etc.
type indexValue struct {
	value *pb.PropertyValue
}
