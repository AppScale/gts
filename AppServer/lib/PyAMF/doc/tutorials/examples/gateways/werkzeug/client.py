from pyamf.remoting.client import RemotingService

import logging
        
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

url = 'http://localhost:8080'
client = RemotingService(url, logger=logging)
service = client.getService('echo')
echo = service('Hello World!')

logging.debug(echo)