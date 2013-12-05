package appengine_internal

// This file implements hooks for applying datastore transactions.

import (
	"reflect"

	pb "appengine_internal/datastore"
)

var transactionSetters = make(map[reflect.Type]reflect.Value)

// RegisterTransactionSetter registers a function that sets transaction information
// in a protocol buffer message. f should be a function with two arguments,
// the first being a protocol buffer type, and the second being *datastore.Transaction.
func RegisterTransactionSetter(f interface{}) {
	v := reflect.ValueOf(f)
	transactionSetters[v.Type().In(0)] = v
}

// ApplyTransaction applies the transaction t to message pb
// by using the relevant setter passed to RegisterTransactionSetter.
func ApplyTransaction(pb ProtoMessage, t *pb.Transaction) {
	v := reflect.ValueOf(pb)
	if f, ok := transactionSetters[v.Type()]; ok {
		f.Call([]reflect.Value{v, reflect.ValueOf(t)})
	}
}
