import SOAPpy
import sys

"""
This script makes an https soap call with method "commit_new_user"
to the uaserver. This is executed from LocalChannelService.java. 
The reason this is done in python is that there was no wsdl 
for this web service.   
"""

client_id = sys.argv[1]
password = sys.argv[2]
secret = sys.argv[3]
url = sys.argv[4]

server = SOAPpy.SOAPProxy(url)
#Uncomment below line to see debug info
#server.config.debug = 1
reply = server.commit_new_user(client_id, password, 'channel', secret)
print str(reply)


