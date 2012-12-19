# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Hello world example client.

@see: U{HelloWorld<http://pyamf.org/tutorials/general/helloworld/index.html>} documentation.

@since: 0.1.0
"""

from pyamf.remoting.client import RemotingService

gateway = RemotingService('http://demo.pyamf.org/gateway/helloworld')

echo_service = gateway.getService('echo.echo')

print echo_service('Hello world!')
