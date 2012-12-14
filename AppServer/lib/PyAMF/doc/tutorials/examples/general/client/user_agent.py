from pyamf.remoting.client import RemotingService

appName = 'MyApp/0.1.0'
gateway = 'http://demo.pyamf.org/gateway/helloworld'
client = RemotingService(gateway, user_agent=appName)
service = client.getService('echo')

print service.echo('Hello World!')
