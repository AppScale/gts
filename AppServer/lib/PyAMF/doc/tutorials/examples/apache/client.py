import logging
	
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

from pyamf.remoting.client import RemotingService

url = 'http://192.168.1.108/flashservices/gateway'
gw = RemotingService(url, logger=logging)
service = gw.getService('echo')

print service('Hello World!')
