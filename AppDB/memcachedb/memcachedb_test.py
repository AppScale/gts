import memcachedb
cl = memcachedb.Client(["128.111.55.223:30000"], debug=0)
print cl.set("aaa".encode(),"aaa")
print cl.set("bbb".encode(),"bbb")
print cl.get("aaa".encode())
print cl.get("bbb".encode())
print cl.rget("0".encode(),"z".encode(), 1, 0, 100)

