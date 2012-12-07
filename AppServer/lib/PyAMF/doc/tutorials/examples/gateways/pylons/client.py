import logging
	
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

from pyamf.remoting.client import RemotingService

url = 'http://127.0.0.1:5000/gateway'
client = RemotingService(url, logger=logging)
service = client.getService('myservice')
echo = service.echo('Hello World!')

logging.debug(echo) 
