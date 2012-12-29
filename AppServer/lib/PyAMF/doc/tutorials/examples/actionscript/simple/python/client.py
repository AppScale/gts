# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


"""
Simple PyAMF client.

@see: U{Simple Example<http://pyamf.org/tutorials/actionscript/simple.html>} documentation.
@since: 0.5
"""


import logging
from server import AMF_NAMESPACE, host_info

import pyamf
from pyamf.remoting.client import RemotingService


logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s')


class UserDataTransferObject(object):
    """
    Models information associated with a simple user object.
    """
    # a default paren-paren constructor is needed for classes
    # that will be passed via AMF
    def __init__(self, username=None, password=None, email=None):
        """
        Create an instance of a user object.
        """
        self.username = username
        self.password = password
        self.email = email


def main():
    """
    Entry point for this client script.
    """
    url = 'http://%s:%d' % (host_info[0], host_info[1])
    client = RemotingService(url, logger=logging)
    print "Client running - pointing to server at %s" % url

    # at this point, calling the service gets us a dict of values
    user_service = client.getService('user')
    lenards = user_service.get_user('lenards')

    # in case you don't believe me - this shows I'm not lying
    logging.debug("isinstance(lenards, dict): %s" % isinstance(lenards, dict))

    # the User class attributes are not present at this point
    logging.debug("not hasattr(lenards, 'username'): %s" %
                  (not hasattr(lenards, 'username')))
    logging.debug("not hasattr(lenards, 'email'): %s" %
                  (not hasattr(lenards, 'email')))
    logging.debug("not hasattr(lenards, 'password'): %s" %
                  (not hasattr(lenards, 'password')))

    # but the values are there
    logging.debug("lenards['username'] == 'lenards': %s" %
                  (lenards['username'] == 'lenards'))
    logging.debug("lenards['email'] == 'lenards@ndy.net': %s" %
                  (lenards['email'] == 'lenards@ndy.net'))

    logging.debug("Output 'lenards': %s" % lenards)

    # if we register the class and the namespace, we get an object ref
    # (complete with attributes and such)
    logging.debug("Register UserDataTransferObject class...")
    pyamf.register_class(UserDataTransferObject, '%s.User' % AMF_NAMESPACE)

    logging.debug("Get a user from the server...")
    usr = user_service.get_user('lisa')

    # ensure it's the class we expect
    logging.debug("Ensure the class we got is our DTO, " +
                  "isinstance(usr, UserDataTransferObject): %s" %
                  isinstance(usr, UserDataTransferObject))

    # verify it has expected attributes
    logging.debug("Verify attributes present...")
    logging.debug("usr.username: %s" % usr.username)
    logging.debug("usr.email == 'lisa@pwns.net': %s" %
                  (usr.email == 'lisa@pwns.net'))
    logging.debug("usr.password == 'h1k3r': %s" %
                  (usr.password == 'h1k3r'))

    logging.debug("Output user returned: %s" % usr)

    # request an unknown user
    logging.debug("Try to get a user that does not exist...")
    george = user_service.get_user('george')

    logging.debug("Output returned: %s" % george)


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("--host", default=host_info[0],
        dest="host", help="host address [default: %default]")
    parser.add_option("-p", "--port", default=host_info[1],
        dest="port", help="port number [default: %default]")
    (options, args) = parser.parse_args()

    host_info[0] = options.host
    host_info[1] = int(options.port)

    # now we rock the code
    main()
