from pyamf.remoting.client import RemotingService

import logging
        
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


url = 'http://localhost:8080'
client = RemotingService(url, logger=logging)

service1 = client.getService('example')
print service1.testn('Hello World')

service2 = client.getService('myadd')
print service2(1,2)