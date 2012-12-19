# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Simple PyAMF server.

@see: U{Simple Example<http://pyamf.org/tutorials/actionscript/simple.html>} documentation.
@since: 0.5
"""

import logging
from wsgiref import simple_server

import pyamf
from pyamf import amf3
from pyamf.remoting.gateway.wsgi import WSGIGateway


#: namespace used in the Adobe Flash Player client's [RemoteClass] mapping
AMF_NAMESPACE = 'org.pyamf.examples.simple'

#: Host and port to run the server on
host_info = ('localhost', 8000)

logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s')


def create_user(username, password, email):
    """
    Create a user object setting attributes to values passed as
    arguments.
    """
    user = User(username, password, email)
    return user


class User(object):
    """
    Models information associated with a simple user object.
    """
    # we need a default constructor (e.g. a paren-paren constructor)
    def __init__(self, username=None, password=None, email=None):
        """
        Create an instance of a user object.
        """
        self.username = username
        self.password = password
        self.email = email


class UserService(object):
    """
    Provide user related services.
    """
    def __init__(self, users):
        """
        Create an instance of the user service.
        """
        self.users = users

    def get_user(self, username):
        """
        Fetch a user object by C{username}.
        """
        try:
            return self.users[username]
        except KeyError:
            return "Username '%s' not found" % username


class EchoService(object):
    """
    Provide a simple server for testing.
    """
    def echo(self, data):
        """
        Return data with chevrons surrounding it.
        """
        return '<<%s>>' % data


def register_classes():
    """
    Register domain objects with PyAMF.
    """
    # set this so returned objects and arrays are bindable
    amf3.use_proxies_default = True

    # register domain objects that will be used with PyAMF
    pyamf.register_class(User, '%s.User' % AMF_NAMESPACE)


def main():
    """
    Create a WSGIGateway application and serve it.
    """
    # register class on the AMF namespace so that it is passed marshaled
    register_classes()

    # use a dict in leiu of sqlite or an actual database to store users
    # re passwords: plain-text in a production would be bad
    users = {
        'lenards': User('lenards', 'f00f00', 'lenards@ndy.net'),
        'lisa': User('lisa', 'h1k3r', 'lisa@pwns.net'),
    }

    # our gateway will have two services
    services = {
        'echo': EchoService,
        'user': UserService(users)
    }

    # setup our server
    application = WSGIGateway(services, logger=logging)
    httpd = simple_server.WSGIServer(host_info,
                simple_server.WSGIRequestHandler)
    httpd.set_app(application)
    
    try:
        # open for business
        print "Running Simple PyAMF gateway on http://%s:%d" % (
            host_info[0], host_info[1])
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", default=host_info[1],
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default=host_info[0],
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    host_info = (options.host, options.port)

    # now we rock the code
    main()
