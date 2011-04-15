from jsonrpc.proxy import ServiceProxy

s = ServiceProxy("http://localhost:8000/jsonrpc.yaws")
p = [{"write":{"keyA":"valueA"}},{"commit":"commit"}]

print "write value to Scalaris"
ret = s.req_list(p)
print "row result: ",
print ret

print "read value from Scalaris"
p = [{"read":"keyA"}]
ret = s.req_list(p)

print "row result: ",
print ret

list = ret['results']
for map in list:
  if map.has_key('key') and map['key'] == 'keyA':
    print map['value']

