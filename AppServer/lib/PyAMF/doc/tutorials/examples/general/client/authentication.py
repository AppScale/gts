from pyamf.remoting.client import RemotingService

client = RemotingService('https://demo.pyamf.org/gateway/authentication')
client.setCredentials('jane', 'doe')

service = client.getService('calc')
print service.sum(85, 115) # should print 200.0

client.setCredentials('abc', 'def')
print service.sum(85, 115).description # should print Authentication Failed