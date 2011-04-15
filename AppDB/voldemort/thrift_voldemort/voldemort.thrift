#
# Interface definition for Voldemort Service
#
namespace java voldemort.server.thrift

struct clock_t {
  1: i16  nodeId,
  2: i64  version
}

struct vector_clock_t {
  1: list<clock_t> versions,
  2: i64  timestamp
}

struct value_t {
  1: vector_clock_t    vector_clock,
  2: string       value
}

service Voldemort {
  value_t get(1:string store, 2:string key),
  async void put(1:string store, 2:string key, 3:string value),
  async void remove(1:string store, 2:string key)
}  



