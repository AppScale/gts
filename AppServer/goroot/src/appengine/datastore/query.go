// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package datastore

import (
	"fmt"
	"math"
	"os"
	"reflect"
	"strings"

	"appengine"
	"goprotobuf.googlecode.com/hg/proto"

	pb "appengine_internal/datastore"
)

type operator int

const (
	lessThan operator = iota
	lessEq
	equal
	greaterEq
	greaterThan
)

var operatorToProto = map[operator]*pb.Query_Filter_Operator{
	lessThan:    pb.NewQuery_Filter_Operator(pb.Query_Filter_LESS_THAN),
	lessEq:      pb.NewQuery_Filter_Operator(pb.Query_Filter_LESS_THAN_OR_EQUAL),
	equal:       pb.NewQuery_Filter_Operator(pb.Query_Filter_EQUAL),
	greaterEq:   pb.NewQuery_Filter_Operator(pb.Query_Filter_GREATER_THAN_OR_EQUAL),
	greaterThan: pb.NewQuery_Filter_Operator(pb.Query_Filter_GREATER_THAN),
}

// filter is a conditional filter on query results.
type filter struct {
	FieldName string
	Op        operator
	Value     interface{}
}

type sortDirection int

const (
	ascending sortDirection = iota
	descending
)

var sortDirectionToProto = map[sortDirection]*pb.Query_Order_Direction{
	ascending:  pb.NewQuery_Order_Direction(pb.Query_Order_ASCENDING),
	descending: pb.NewQuery_Order_Direction(pb.Query_Order_DESCENDING),
}

// order is a sort order on query results.
type order struct {
	FieldName string
	Direction sortDirection
}

// NewQuery creates a new Query for a specific entity kind.
// The kind must be non-empty.
func NewQuery(kind string) *Query {
	q := &Query{kind: kind}
	if kind == "" {
		q.err = os.NewError("datastore: empty kind")
	}
	return q
}

// Query represents a datastore query.
type Query struct {
	kind   string
	filter []filter
	order  []order

	keysOnly bool
	limit    int
	offset   int

	err os.Error
}

// Filter adds a field-based filter to the Query.
// The filterStr argument must be a field name followed by optional space,
// followed by an operator, one of ">", "<", ">=", "<=", or "=".
// Fields are compared against the provided value using the operator.
// Multiple filters are AND'ed together.
// The Query is updated in place and returned for ease of chaining.
func (q *Query) Filter(filterStr string, value interface{}) *Query {
	filterStr = strings.TrimSpace(filterStr)
	if len(filterStr) < 1 {
		q.err = os.NewError("datastore: invalid filter: " + filterStr)
		return q
	}
	f := filter{
		FieldName: strings.TrimRight(filterStr, " ><="),
		Value:     value,
	}
	switch op := strings.TrimSpace(filterStr[len(f.FieldName):]); op {
	case "<=":
		f.Op = lessEq
	case ">=":
		f.Op = greaterEq
	case "<":
		f.Op = lessThan
	case ">":
		f.Op = greaterThan
	case "=":
		f.Op = equal
	default:
		q.err = fmt.Errorf("datastore: invalid operator %q in filter %q", op, filterStr)
		return q
	}
	q.filter = append(q.filter, f)
	return q
}

// Order adds a field-based sort to the query.
// Orders are applied in the order they are added.
// The default order is ascending; to sort in descending
// order prefix the fieldName with a minus sign (-).
func (q *Query) Order(fieldName string) *Query {
	fieldName = strings.TrimSpace(fieldName)
	o := order{Direction: ascending, FieldName: fieldName}
	if strings.HasPrefix(fieldName, "-") {
		o.Direction = descending
		o.FieldName = strings.TrimSpace(fieldName[1:])
	}
	if len(fieldName) == 0 {
		q.err = os.NewError("datastore: invalid order: " + fieldName)
		return q
	}
	q.order = append(q.order, o)
	return q
}

// KeysOnly configures the query to return just keys,
// instead of keys and entities.
func (q *Query) KeysOnly() *Query {
	q.keysOnly = true
	return q
}

// Limit sets the maximum number of keys/entities to return.
func (q *Query) Limit(limit int) *Query {
	if limit < 0 {
		q.err = os.NewError("datastore: negative query limit")
		return q
	}
	if limit > math.MaxInt32 {
		q.err = os.NewError("datastore: query limit overflow")
		return q
	}
	q.limit = limit
	return q
}

// Offset sets how many keys to skip over before returning results.
func (q *Query) Offset(offset int) *Query {
	if offset < 0 {
		q.err = os.NewError("datastore: negative query offset")
		return q
	}
	if offset > math.MaxInt32 {
		q.err = os.NewError("datastore: query offset overflow")
		return q
	}
	q.offset = offset
	return q
}

// toProto converts the query to a protocol buffer.
func (q *Query) toProto(appID string) (*pb.Query, os.Error) {
	if q.kind == "" {
		return nil, os.NewError("datastore: empty query kind")
	}
	x := &pb.Query{
		App:  proto.String(appID),
		Kind: proto.String(q.kind),
	}
	if q.keysOnly {
		x.KeysOnly = proto.Bool(true)
		x.RequirePerfectPlan = proto.Bool(true)
	}
	for _, qf := range q.filter {
		if qf.FieldName == "" {
			return nil, os.NewError("datastore: empty query filter field name")
		}
		p, errStr := valueToProto(appID, qf.FieldName, reflect.ValueOf(qf.Value), false)
		if errStr != "" {
			return nil, os.NewError("datastore: bad query filter value type: " + errStr)
		}
		xf := &pb.Query_Filter{
			Op:       operatorToProto[qf.Op],
			Property: []*pb.Property{p},
		}
		if xf.Op == nil {
			return nil, os.NewError("datastore: unknown query filter operator")
		}
		x.Filter = append(x.Filter, xf)
	}
	for _, qo := range q.order {
		if qo.FieldName == "" {
			return nil, os.NewError("datastore: empty query order field name")
		}
		xo := &pb.Query_Order{
			Property:  proto.String(qo.FieldName),
			Direction: sortDirectionToProto[qo.Direction],
		}
		if xo.Direction == nil {
			return nil, os.NewError("datastore: unknown query order direction")
		}
		x.Order = append(x.Order, xo)
	}
	if q.limit != 0 {
		x.Limit = proto.Int(q.limit)
	}
	if q.offset != 0 {
		x.Offset = proto.Int(q.offset)
	}
	return x, nil
}

// Run runs the query in the given context.
func (q *Query) Run(c appengine.Context) *Iterator {
	if q.err != nil {
		return &Iterator{err: q.err}
	}
	req, err := q.toProto(c.AppID())
	return &Iterator{
		c:        c,
		keysOnly: q.keysOnly,
		offset:   q.offset,
		req:      req,
		err:      err,
	}
}

// GetAll runs the query in the given context and appends the result to the
// provided destination slice.
// The dst must be a pointer to a slice of structs, struct pointers, or maps.
// GetAll appends to that slice and returns a corresponding slice of keys.
// If q is a ``keys-only'' query, GetAll ignores dst and only returns the keys.
func (q *Query) GetAll(c appengine.Context, dst interface{}) ([]*Key, os.Error) {
	var ds reflect.Value
	var et reflect.Type
	var ptr bool
	if !q.keysOnly {
		ds = reflect.ValueOf(dst)
		if ds.Kind() != reflect.Ptr || ds.Elem().Kind() != reflect.Slice {
			return nil, os.NewError("datastore: GetAll destination is not pointer to slice")
		}
		if ds.IsNil() {
			return nil, os.NewError("datastore: GetAll destination is nil pointer to slice")
		}
		ds = ds.Elem()

		et = ds.Type().Elem()
		if et.Kind() == reflect.Ptr {
			ptr = true
			et = et.Elem()
		}
	}

	var keys []*Key
	for t := q.Run(c); ; {
		k, e, err := t.next()
		if err == Done {
			break
		}
		if err != nil {
			return keys, err
		}
		if !q.keysOnly {
			ev := reflect.New(et)
			d := ev.Interface()
			if _, err = loadEntity(d, k, e); err != nil {
				return keys, err
			}
			if !ptr {
				ev = ev.Elem()
			}
			ds.Set(reflect.Append(ds, ev))
		}
		keys = append(keys, k)
	}
	return keys, nil
}

// Iterator is the result of running a query.
type Iterator struct {
	c        appengine.Context
	keysOnly bool
	offset   int
	req      *pb.Query
	res      *pb.QueryResult
	err      os.Error
}

// Done is returned when a query iteration has completed.
var Done = os.NewError("datastore: query has no more results")

// Next returns the key of the next result. When there are no more results,
// Done is returned as the error.
// If the query is not keys only, it also loads the entity
// stored for that key into the struct pointer or map dst, with the same
// semantics and possible errors as for the Get function.
// If the query is keys only, it is valid to pass a nil interface{} for dst.
func (t *Iterator) Next(dst interface{}) (*Key, os.Error) {
	k, e, err := t.next()
	if err != nil || t.keysOnly {
		return k, err
	}
	return loadEntity(dst, k, e)
}

func (t *Iterator) next() (*Key, *pb.EntityProto, os.Error) {
	if t.err != nil {
		return nil, nil, t.err
	}

	// Issue an RPC if necessary.
	call := false
	if t.res == nil {
		call = true
		t.res = &pb.QueryResult{}
	} else if len(t.res.Result) == 0 {
		if !proto.GetBool(t.res.MoreResults) {
			t.err = Done
			return nil, nil, t.err
		}
		call = true
		t.res.Reset()
	}
	if call {
		if t.offset != 0 {
			if t.offset < 0 || t.offset > math.MaxInt32 {
				t.err = os.NewError("datastore: query offset overflow")
				return nil, nil, t.err
			}
			if t.req.Offset == nil {
				t.req.Offset = new(int32)
			}
			*t.req.Offset = int32(t.offset)
		}
		t.err = t.c.Call("datastore_v3", "RunQuery", t.req, t.res)
		if t.err != nil {
			return nil, nil, t.err
		}
	}
	if len(t.res.Result) == 0 {
		t.err = Done
		return nil, nil, t.err
	}
	t.offset++

	// Pop the EntityProto from the front of t.res.Result and
	// extract its key.
	var e *pb.EntityProto
	e, t.res.Result = t.res.Result[0], t.res.Result[1:]
	if e.Key == nil {
		return nil, nil, os.NewError("datastore: internal error: server did not return a key")
	}
	k, err := protoToKey(e.Key)
	if err != nil || k.Incomplete() {
		return nil, nil, os.NewError("datastore: internal error: server returned an invalid key")
	}
	if t.keysOnly {
		return k, nil, nil
	}
	return k, e, nil
}

// loadEntity loads an EntityProto into a Map or struct.
func loadEntity(dst interface{}, k *Key, e *pb.EntityProto) (*Key, os.Error) {
	if m, ok := dst.(Map); ok {
		return k, loadMap(m, k, e)
	}
	sv, err := asStructValue(dst)
	if err != nil {
		return nil, err
	}
	return k, loadStruct(sv, k, e)
}
