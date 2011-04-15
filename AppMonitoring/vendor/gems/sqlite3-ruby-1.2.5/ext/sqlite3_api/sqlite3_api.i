%module "SQLite3::driver::native::API"
%include "typemaps.i"
%{
#include <sqlite3.h>
#include "ruby.h"

#ifndef RSTRING_PTR
#define RSTRING_PTR(s) (RSTRING(s)->ptr)
#endif
 
#ifndef RSTRING_LEN
#define RSTRING_LEN(s) (RSTRING(s)->len)
#endif

#ifndef STR2CSTR
#define STR2CSTR StringValueCStr
#endif

#define Init_API Init_sqlite3_api

struct CallbackData {
  VALUE proc;
  VALUE proc2;
  VALUE data;
};

typedef struct CallbackData CallbackData;
typedef void RUBY_BLOB;
typedef void RUBY_VALBLOB;

int Sqlite3_ruby_busy_handler(void* data,int value) {
  VALUE result;
  CallbackData *cb = (CallbackData*)data;
  result = rb_funcall(
    cb->proc, rb_intern("call"), 2, cb->data, INT2FIX(value) );
  return FIX2INT(result);
}

static void mark_CallbackData(void* ptr) {
    CallbackData* cb = (CallbackData*)ptr;
    if (cb->proc != Qnil)
        rb_gc_mark(cb->proc);
    if (cb->proc2 != Qnil)
        rb_gc_mark(cb->proc2);
    if (cb->data != Qnil)
        rb_gc_mark(cb->data);
}

int Sqlite3_ruby_authorizer(void* data,int type,
  const char* a,const char* b,const char* c,const char* d)
{
  VALUE result;
  CallbackData *cb = (CallbackData*)data;
  result = rb_funcall(
    cb->proc, rb_intern("call"), 6, cb->data, INT2FIX(type),
    ( a ? rb_str_new2(a) : Qnil ), ( b ? rb_str_new2(b) : Qnil ),
    ( c ? rb_str_new2(c) : Qnil ), ( d ? rb_str_new2(d) : Qnil ) );
  return FIX2INT(result);
}

void Sqlite3_ruby_trace(void* data, const char *sql) {
  CallbackData *cb = (CallbackData*)data;
  rb_funcall( cb->proc, rb_intern("call"), 2, cb->data,
    sql ? rb_str_new2(sql) : Qnil );
}

void Sqlite3_ruby_function_step(sqlite3_context* ctx,int n,
  sqlite3_value** args)
{
  CallbackData *data;
  VALUE rb_args;
  VALUE *rb_context;
  int idx;
  
  data = (CallbackData*)sqlite3_user_data(ctx);

  if( data->proc2 != Qnil ) {
    rb_context = (VALUE*)sqlite3_aggregate_context(ctx,sizeof(VALUE));
    if( *rb_context == 0 ) {
      *rb_context = rb_hash_new();
      rb_gc_register_address( rb_context );
    }
  }

  rb_args = rb_ary_new2(n+1);
  rb_ary_push( rb_args, SWIG_NewPointerObj(ctx,SWIGTYPE_p_sqlite3_context,0) );
  for( idx = 0; idx < n; idx++ ) {
    rb_ary_push( rb_args, SWIG_NewPointerObj(args[idx],
      SWIGTYPE_p_sqlite3_value,0) );
  }

  rb_apply( data->proc, rb_intern("call"), rb_args );
}

void Sqlite3_ruby_function_final(sqlite3_context *ctx) {
  VALUE *rb_context;
  CallbackData *data;
  
  rb_context = (VALUE*)sqlite3_aggregate_context(ctx,sizeof(VALUE));
  if( *rb_context == 0 ) {
    *rb_context = rb_hash_new();
    rb_gc_register_address( rb_context );
  }

  data = (CallbackData*)sqlite3_user_data(ctx);

  rb_funcall( data->proc2, rb_intern("call"), 1,
    SWIG_NewPointerObj(ctx,SWIGTYPE_p_sqlite3_context,0) );

  rb_gc_unregister_address( rb_context );
}
%}

%markfunc CallbackData "mark_CallbackData";

struct CallbackData {
  VALUE proc;
  VALUE proc2;
  VALUE data;
};

%typemap(in) const void *str {
  $1 = (void*)RSTRING_PTR($input);
}

%typemap(in) (const char *filename, sqlite3**) {
  $1 = STR2CSTR($input);
  $2 = (sqlite3**)malloc( sizeof( sqlite3* ) );
}

%typemap(argout) (const char *filename, sqlite3**) {
  VALUE ary;
  ary = rb_ary_new2(2);
  rb_ary_push( ary, $result );
  rb_ary_push( ary, SWIG_NewPointerObj( *$2, SWIGTYPE_p_sqlite3, 0 ) );
  free( $2 );
  $result = ary;
}

%typemap(in) (const void *filename, sqlite3**) {
  $1 = (void*)RSTRING_PTR($input);
  $2 = (sqlite3**)malloc( sizeof( sqlite3* ) );
}

%typemap(argout) (const void *filename, sqlite3**) {
  VALUE ary;
  ary = rb_ary_new2(2);
  rb_ary_push( ary, $result );
  rb_ary_push( ary, SWIG_NewPointerObj( *$2, SWIGTYPE_p_sqlite3, 0 ) );
  free( $2 );
  $result = ary;
}

typedef void RUBY_BLOB;
%typemap(out) const RUBY_BLOB * {
  $result = $1 ?
    rb_str_new( (char*)$1, sqlite3_column_bytes( arg1, arg2 ) ) : Qnil;
}

typedef void RUBY_VALBLOB;
%typemap(out) const RUBY_VALBLOB * {
  $result = $1 ? rb_str_new( (char*)$1, sqlite3_value_bytes( arg1 ) ) : Qnil;
}

%typemap(out) const void * {
  int i;
  if( $1 ) {
    for( i = 0; ((char*)$1)[i]; i += 2 );
    $result = rb_str_new( (char*)$1, i );
  } else $result = Qnil;
}

%typemap(in) (const char * sql,int,sqlite3_stmt**,const char**) (sqlite3_stmt *stmt, char *errmsg) {
  $1 = RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
  $3 = &stmt2;
  $4 = &errmsg2;
}

%typemap(argout) (const char* sql,int,sqlite3_stmt**,const char**) {
  VALUE ary;
  ary = rb_ary_new2(3);
  rb_ary_push( ary, $result );
  rb_ary_push( ary, SWIG_NewPointerObj( stmt2, SWIGTYPE_p_sqlite3_stmt, 0 ) );
  rb_ary_push( ary, errmsg2 ? rb_str_new2( errmsg2 ) : Qnil );
  $result = ary;
}

%typemap(in) (const void* sql,int,sqlite3_stmt**,const void**) (sqlite3_stmt *stmt, void *errmsg) {
  $1 = RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
  $3 = &stmt2;
  $4 = &errmsg2;
}

%typemap(argout) (const void* sql,int,sqlite3_stmt**,const void**) {
  VALUE ary;
  int i;

  for( i = 0; ((char*)errmsg2)[i]; i += 2 );

  ary = rb_ary_new2(3);
  rb_ary_push( ary, $result );
  rb_ary_push( ary, SWIG_NewPointerObj( stmt2, SWIGTYPE_p_sqlite3_stmt, 0 ) );
  rb_ary_push( ary, errmsg2 ? rb_str_new( (char*)errmsg2, i ) : Qnil );
  $result = ary;
}

%typemap(in) (const void *blob,int) {
  $1 = (void*)RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
}

%typemap(in) (const void *blob,int,void(*free)(void*)) {
  $1 = (void*)RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
  $3 = SQLITE_TRANSIENT;
}

%typemap(in) (const char *text,int) {
  $1 = RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
}

%typemap(in) (const char *text,int,void(*free)(void*)) {
  $1 = RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
  $3 = SQLITE_TRANSIENT;
}

%typemap(in) (const void *utf16,int) {
  $1 = (void*)RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
}

%typemap(in) (const void *utf16,int,void(*free)(void*)) {
  $1 = (void*)RSTRING_PTR($input);
  $2 = RSTRING_LEN($input);
  $3 = SQLITE_TRANSIENT;
}

%typemap(out) sqlite_int64 {
  $result = rb_ll2inum( $1 );
}

%typemap(out) const char * {
  $result = $1 ? rb_str_new2($1) : Qnil;
}

%typemap(in) sqlite_int64 {
  $1 = rb_num2ll( $input );
}

%typemap(in) (sqlite3_context*,int data_size) {
  SWIG_ConvertPtr($input,(void**)&$1, SWIGTYPE_p_sqlite3_context, 1);
  $2 = 4;
}

%typemap(out) VALUE* {
  $result = *(VALUE*)$1;
}

%constant int Sqlite3_ruby_busy_handler(void*,int);
%constant int Sqlite3_ruby_authorizer(void*,int,const char*,const char*,const char*,const char*);
%constant void Sqlite3_ruby_trace(void*,const char*);
%constant void Sqlite3_ruby_function_step(sqlite3_context* ctx,int n,
  sqlite3_value** args);
%constant void Sqlite3_ruby_function_final(sqlite3_context* ctx);

const char *sqlite3_libversion(void);
int sqlite3_close(sqlite3*);

sqlite_int64 sqlite3_last_insert_rowid(sqlite3*);

int sqlite3_changes(sqlite3*);
int sqlite3_total_changes(sqlite3*);
void sqlite3_interrupt(sqlite3*);

int sqlite3_complete(const char*);
int sqlite3_complete16(const void *str);

int sqlite3_busy_handler(sqlite3*, int(*)(void*,int), void*);
int sqlite3_busy_timeout(sqlite3*,int);
int sqlite3_set_authorizer(sqlite3*, int(*)(void*,int,const char*,const char*,const char*,const char*), void*);
int sqlite3_trace(sqlite3*, void(*)(void*,const char*), void*);

int sqlite3_open(const char *filename, sqlite3 **);
int sqlite3_open16(const void *filename, sqlite3 **);

int sqlite3_errcode(sqlite3*);
const char *sqlite3_errmsg(sqlite3*);
const void *sqlite3_errmsg16(sqlite3*);

int sqlite3_prepare(sqlite3*,const char* sql,int,sqlite3_stmt**,const char**);
int sqlite3_prepare16(sqlite3*,const void* sql,int,sqlite3_stmt**,const void**);

int sqlite3_bind_blob(sqlite3_stmt*,int,const void *blob,int,void(*free)(void*));
int sqlite3_bind_double(sqlite3_stmt*,int,double);
int sqlite3_bind_int(sqlite3_stmt*,int,int);
int sqlite3_bind_int64(sqlite3_stmt*,int,sqlite_int64);
int sqlite3_bind_null(sqlite3_stmt*,int);
int sqlite3_bind_text(sqlite3_stmt*,int,const char*text,int,void(*free)(void*));
int sqlite3_bind_text16(sqlite3_stmt*,int,const void*utf16,int,void(*free)(void*));

int sqlite3_bind_parameter_count(sqlite3_stmt*);
const char *sqlite3_bind_parameter_name(sqlite3_stmt*,int);
int sqlite3_bind_parameter_index(sqlite3_stmt*,const char*);

int sqlite3_column_count(sqlite3_stmt*);
const char *sqlite3_column_name(sqlite3_stmt*,int);
const void *sqlite3_column_name16(sqlite3_stmt*,int);
const char *sqlite3_column_decltype(sqlite3_stmt*,int);
const void *sqlite3_column_decltype16(sqlite3_stmt*,int);

int sqlite3_step(sqlite3_stmt*);

int sqlite3_data_count(sqlite3_stmt*);

const RUBY_BLOB *sqlite3_column_blob(sqlite3_stmt*,int);
int sqlite3_column_bytes(sqlite3_stmt*,int);
int sqlite3_column_bytes16(sqlite3_stmt*,int);
double sqlite3_column_double(sqlite3_stmt*,int);
double sqlite3_column_int(sqlite3_stmt*,int);
sqlite_int64 sqlite3_column_int64(sqlite3_stmt*,int);
const char *sqlite3_column_text(sqlite3_stmt*,int);
const void *sqlite3_column_text16(sqlite3_stmt*,int);
int sqlite3_column_type(sqlite3_stmt*,int);

int sqlite3_finalize(sqlite3_stmt*);
int sqlite3_reset(sqlite3_stmt*);

int sqlite3_create_function(sqlite3*,const char*str,int,int,void*,void(*func)(sqlite3_context*,int,sqlite3_value**),void(*step)(sqlite3_context*,int,sqlite3_value**),void(*final)(sqlite3_context*));

int sqlite3_create_function16(sqlite3*,const void*str,int,int,void*,void(*func)(sqlite3_context*,int,sqlite3_value**),void(*step)(sqlite3_context*,int,sqlite3_value**),void(*final)(sqlite3_context*));

int sqlite3_aggregate_count(sqlite3_context*);

const RUBY_VALBLOB *sqlite3_value_blob(sqlite3_value*);
int sqlite3_value_bytes(sqlite3_value*);
int sqlite3_value_bytes16(sqlite3_value*);
double sqlite3_value_double(sqlite3_value*);
int sqlite3_value_int(sqlite3_value*);
sqlite_int64 sqlite3_value_int64(sqlite3_value*);
const char *sqlite3_value_text(sqlite3_value*);
const void *sqlite3_value_text16(sqlite3_value*);
const void *sqlite3_value_text16le(sqlite3_value*);
const void *sqlite3_value_text16be(sqlite3_value*);
int sqlite3_value_type(sqlite3_value*);

void sqlite3_result_blob(sqlite3_context*,const void *blob,int,void(*free)(void*));
void sqlite3_result_double(sqlite3_context*,double);
void sqlite3_result_error(sqlite3_context*,const char *text,int);
void sqlite3_result_error16(sqlite3_context*,const void *blob,int);
void sqlite3_result_int(sqlite3_context*,int);
void sqlite3_result_int64(sqlite3_context*,sqlite_int64);
void sqlite3_result_text(sqlite3_context*,const char* text,int,void(*free)(void*));
void sqlite3_result_text16(sqlite3_context*,const void* utf16,int,void(*free)(void*));
void sqlite3_result_text16le(sqlite3_context*,const void* utf16,int,void(*free)(void*));
void sqlite3_result_text16be(sqlite3_context*,const void* utf16,int,void(*free)(void*));
void sqlite3_result_value(sqlite3_context*,sqlite3_value*);

VALUE *sqlite3_aggregate_context(sqlite3_context*,int data_size);
