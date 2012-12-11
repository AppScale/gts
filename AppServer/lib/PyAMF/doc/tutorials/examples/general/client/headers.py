from pyamf.remoting.client import RemotingService

gw = RemotingService('http://demo.pyamf.org/gateway/recordset')

gw.addHTTPHeader("Accept-encoding", "gzip")
gw.addHTTPHeader('Set-Cookie', 'sessionid=QT3cUmACNeKQo5oPeM0')
gw.removeHTTPHeader('Set-Cookie')

username = 'admin'
password = 'admin'
auth = ('%s:%s' % (username, password)).encode('base64')[:-1]

gw.addHTTPHeader("Authorization", "Basic %s" % auth)

service = gw.getService('service')
print service.getLanguages()
