import logging
	
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

from pyamf.remoting.client import RemotingService

url = 'http://127.0.0.1:8000/gateway/'
gw = RemotingService(url, logger=logging)
service = gw.getService('myservice')

print service.echo('Hello World!')
