from pyamf.remoting.client import RemotingService

appReferer = 'client.py'
gateway = 'http://demo.pyamf.org/gateway/helloworld'
client = RemotingService(gateway, referer=appReferer)
service = client.getService('echo')

print service.echo('Hello World!')
