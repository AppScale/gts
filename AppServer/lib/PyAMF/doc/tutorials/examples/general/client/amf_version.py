from pyamf import AMF0, AMF3
from pyamf.remoting.client import RemotingService

gateway = 'http://demo.pyamf.org/gateway/helloworld'
client = RemotingService(gateway, amf_version=AMF3)
service = client.getService('echo')

print service("Hello AMF3 world!")
