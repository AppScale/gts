# Copyright (c) The PyAMF Project.
# See LICENSE for details.

from twisted.application import internet, service
from server import server, port


# this is the important bit
application = service.Application("pyamf-twisted-guestbook-example")
guestbookService = internet.TCPServer(port, server)

guestbookService.setServiceParent(application)
