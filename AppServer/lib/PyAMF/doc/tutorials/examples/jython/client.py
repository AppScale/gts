import logging
	
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


from pyamf.remoting.client import RemotingService
from pyamf.remoting import RemotingError

url = 'http://localhost:8080/pyamf'
client = RemotingService(url, logger=logging)
service = client.getService('my_service')

try:
    print service.echo('Hello World!')
except RemotingError, e:
    print e
