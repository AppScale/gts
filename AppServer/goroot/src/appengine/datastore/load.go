// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"fmt"
	"os"
	"reflect"
	"unicode"
	"utf8"

	"appengine"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/datastore"
)

// typeMismatchReason returns a string explaining why the property p could not
// be stored in an entity field of type v.Type().
func typeMismatchReason(p *pb.Property, v reflect.Value) string {
	entityType := "empty"
	pv := p.Value
	switch {
	case pv.Int64Value != nil:
		entityType = "int"
	case pv.BooleanValue != nil:
		entityType = "bool"
	case pv.StringValue != nil:
		if p.Meaning != nil && *p.Meaning == pb.Property_BLOB {
			entityType = "[]byte"
		} else {
			entityType = "string"
		}
	case pv.DoubleValue != nil:
		entityType = "float"
	case pv.Referencevalue != nil:
		entityType = "*datastore.Key"
	}
	return fmt.Sprintf("type mismatch: %s versus %v", entityType, v.Type())
}

// unexported returns whether the field name is unexported.
func unexported(fieldName string) bool {
	firstRune, _ := utf8.DecodeRuneInString(fieldName)
	return !unicode.IsUpper(firstRune)
}

// loadStructField converts a Property into a field of an existing struct,
// or into an element of a slice-typed struct field.
// It returns an error message, or "" for success.
func loadStructField(sv reflect.Value, p *pb.Property) string {
	fieldName := proto.GetString(p.Name)
	v := sv.FieldByName(fieldName)
	if !v.IsValid() {
		return "no such struct field"
	}
	if unexported(fieldName) {
		return "unexported struct field"
	}
	var slice reflect.Value
	if proto.GetBool(p.Multiple) {
		if v.Kind() != reflect.Slice {
			return "multiple-valued property requires a slice field type"
		}
		if v.Len() > maxSliceFieldLen-1 {
			return "slice is too long"
		}
		slice = v
		v = reflect.New(v.Type().Elem()).Elem()
	}
	switch v.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		if p.Value.Int64Value == nil {
			return typeMismatchReason(p, v)
		}
		x := *p.Value.Int64Value
		if v.OverflowInt(x) {
			return fmt.Sprintf("value %v overflows struct field of type %v", x, v.Type())
		}
		v.SetInt(x)
	case reflect.Bool:
		if p.Value.BooleanValue == nil {
			return typeMismatchReason(p, v)
		}
		v.SetBool(*p.Value.BooleanValue)
	case reflect.String:
		if p.Value.StringValue == nil {
			return typeMismatchReason(p, v)
		}
		v.SetString(*p.Value.StringValue)
	case reflect.Float32, reflect.Float64:
		if p.Value.DoubleValue == nil {
			return typeMismatchReason(p, v)
		}
		x := *p.Value.DoubleValue
		if v.OverflowFloat(x) {
			return fmt.Sprintf("value %v overflows struct field of type %v", x, v.Type())
		}
		v.SetFloat(x)
	case reflect.Ptr:
		if _, ok := v.Interface().(*Key); !ok {
			return typeMismatchReason(p, v)
		}
		if p.Value.Referencevalue == nil {
			return typeMismatchReason(p, v)
		}
		k, err := referenceValueToKey(p.Value.Referencevalue)
		if err != nil {
			return "stored key was invalid"
		}
		v.Set(reflect.ValueOf(k))
	case reflect.Slice:
		if _, ok := v.Interface().([]byte); !ok {
			return typeMismatchReason(p, v)
		}
		if p.Value.StringValue == nil {
			return typeMismatchReason(p, v)
		}
		b := []byte(*p.Value.StringValue)
		v.Set(reflect.ValueOf(b))
	default:
		return typeMismatchReason(p, v)
	}
	if slice.IsValid() {
		slice.Set(reflect.Append(slice, v))
	}
	return ""
}

// loadStruct converts an EntityProto into an existing struct.
// It returns an error if the destination struct is unable to hold the entity.
func loadStruct(sv reflect.Value, k *Key, e *pb.EntityProto) os.Error {
	var fieldName, reason string
	for _, p := range e.Property {
		if errStr := loadStructField(sv, p); errStr != "" {
			fieldName, reason = proto.GetString(p.Name), errStr
		}
	}
	for _, p := range e.RawProperty {
		if errStr := loadStructField(sv, p); errStr != "" {
			fieldName, reason = proto.GetString(p.Name), errStr
		}
	}
	if reason != "" {
		return &ErrFieldMismatch{
			Key:        k,
			StructType: sv.Type(),
			FieldName:  fieldName,
			Reason:     reason,
		}
	}
	return nil
}

// loadMapEntry converts a Property into an entry of an existing Map,
// or into an element of a slice-valued Map entry.
func loadMapEntry(m Map, k *Key, p *pb.Property) os.Error {
	var (
		result    interface{}
		sliceType reflect.Type
	)
	switch {
	case p.Value.Int64Value != nil:
		if p.Meaning != nil && *p.Meaning == pb.Property_GD_WHEN {
			result = Time(*p.Value.Int64Value)
			sliceType = reflect.TypeOf([]Time(nil))
		} else {
			result = *p.Value.Int64Value
			sliceType = reflect.TypeOf([]int64(nil))
		}
	case p.Value.BooleanValue != nil:
		result = *p.Value.BooleanValue
		sliceType = reflect.TypeOf([]bool(nil))
	case p.Value.StringValue != nil:
		if p.Meaning != nil && *p.Meaning == pb.Property_BLOB {
			result = []byte(*p.Value.StringValue)
			sliceType = reflect.TypeOf([][]byte(nil))
		} else if p.Meaning != nil && *p.Meaning == pb.Property_BLOBKEY {
			result = appengine.BlobKey(*p.Value.StringValue)
			sliceType = reflect.TypeOf([]appengine.BlobKey(nil))
		} else {
			result = *p.Value.StringValue
			sliceType = reflect.TypeOf([]string(nil))
		}
	case p.Value.DoubleValue != nil:
		result = *p.Value.DoubleValue
		sliceType = reflect.TypeOf([]float64(nil))
	case p.Value.Referencevalue != nil:
		key, err := referenceValueToKey(p.Value.Referencevalue)
		if err != nil {
			return err
		}
		result = key
		sliceType = reflect.TypeOf([]*Key(nil))
	default:
		return nil
	}
	name := proto.GetString(p.Name)
	if proto.GetBool(p.Multiple) {
		var s reflect.Value
		if x := m[name]; x != nil {
			s = reflect.ValueOf(x)
		} else {
			s = reflect.MakeSlice(sliceType, 0, 0)
		}
		s = reflect.Append(s, reflect.ValueOf(result))
		m[name] = s.Interface()
	} else {
		m[name] = result
	}
	return nil
}

// loadMap converts an EntityProto into an existing Map.
func loadMap(m Map, k *Key, e *pb.EntityProto) (err os.Error) {
	for _, p := range e.Property {
		if err1 := loadMapEntry(m, k, p); err1 != nil {
			err = err1
		}
	}
	for _, p := range e.RawProperty {
		if err1 := loadMapEntry(m, k, p); err1 != nil {
			err = err1
		}
	}
	return err
}
