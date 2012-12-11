# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
Python ByteArray example.

@since: 0.5
""" 

import os
from optparse import OptionParser

from gateway import images_root

from pyamf.amf3 import ByteArray
from pyamf.remoting.client import RemotingService


# parse commandline options
parser = OptionParser()
parser.add_option("-p", "--port", default=8000,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default="127.0.0.1",
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()


# define gateway
url = 'http://%s:%d' % (options.host, int(options.port))
server = RemotingService(url)
service = server.getService('getSnapshots')()

# get list of snapshots
base_path = service[0]
types = service[1]
snapshots = service[2]

print "Found %d snapshot(s):" % (len(snapshots))

for snapshot in snapshots:
    print "\t%s%s" % (base_path, snapshot['name'])    

# save snapshot
path = 'django-logo.jpg'
image = os.path.join(images_root, path)
file = open(image, 'r').read()

snapshot = ByteArray()
snapshot.write(file)

save_snapshot = server.getService('ByteArray.saveSnapshot')
saved = save_snapshot(snapshot, 'jpg')

print "Saved snapshot:\n\t%s:\t%s" % (saved['name'], saved['url'])
