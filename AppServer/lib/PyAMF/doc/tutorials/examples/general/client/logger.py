from pyamf.remoting.client import RemotingService

import logging
logging.basicConfig(level=logging.DEBUG,
           format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s')

gateway = 'http://demo.pyamf.org/gateway/recordset'
client = RemotingService(gateway, logger=logging)
service = client.getService('service')

print service.getLanguages()