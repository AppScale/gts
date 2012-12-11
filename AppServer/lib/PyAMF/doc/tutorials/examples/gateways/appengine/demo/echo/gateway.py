# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Remoting gateway for Google App Engine.

@since: 0.3.0
"""

from pyamf.remoting.gateway.wsgi import WSGIGateway
from google.appengine.ext.webapp import util

from echo import echo

services = {
    'echo': echo,
    'echo.echo': echo
}

def main():
    gateway = WSGIGateway(services)

    util.run_wsgi_app(gateway)

if __name__ == "__main__":
    main()
