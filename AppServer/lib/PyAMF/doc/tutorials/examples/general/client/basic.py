from pyamf.remoting.client import RemotingService

client = RemotingService('http://demo.pyamf.org/gateway/recordset')
service = client.getService('service')

print service.getLanguages()