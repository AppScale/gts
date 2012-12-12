# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Guestbook remoting service.

@since: 0.3
"""


from datetime import datetime
from urlparse import urlparse
import re

try:
    from genshi.input import HTML
    from genshi.filters import HTMLSanitizer
except ImportError:
    import sys
    print >> sys.stderr, "Genshi is required for this example"
    raise

from twisted.internet import defer
from twisted.internet.task import LoopingCall

import pyamf 
from pyamf.flex import ArrayCollection, ObjectProxy
from pyamf.remoting.gateway import expose_request


EMAIL_RE = r"^.+\@(\[?)[a-zA-Z0-9\-\.]+\.([a-zA-Z]{2,3}|[0-9]{1,3})(\]?)$"

# This is MySQL specific, make sure that if you use a different database server
# this is updated to ensure sql injection attacks don't occur 
def sql_safe(value):
    if isinstance(value, basestring):
        return value.replace("'", "\\'")
    elif isinstance(type(value), (int, float)):
        return value

    raise TypeError, 'basestring, int or float expected' 


def is_valid_url(url):
    o = urlparse(url)

    # scheme
    if o[0] == '':
        return (False, 'Scheme required')

    if o[1] == '':
        return (False, 'Hostname required')

    return (True, None)


def is_valid_email(email):
    """
    A very basic email address format validator
    """
    if re.match(EMAIL_RE, email) != None:
        return True

    return False


def strip_message(message):
    markup = HTML(message) | HTMLSanitizer()

    return markup.render('xhtml')


def build_message(row):
    m = Message()

    m.name = row[0]
    m.url = row[1]
    #m.email = row[2]
    m.created = row[3]
    m.message = row[4]

    return m


class Message:
    pass

pyamf.register_class(Message, 'org.pyamf.examples.guestbook.Message')


class GuestBookService(object):
    def __init__(self, pool):
        self.conn_pool = pool
        LoopingCall(self._keepAlive).start(3600, False)
        
    def _keepAlive():
        print 'Running Keep Alive...'
        self.conn_pool.runOperation('SELECT 1')

    def getMessages(self):
        """
        Gets all approved messages.
        """
        def cb(rs):
            ret = [ObjectProxy(build_message(row)) for row in rs]

            return ArrayCollection(ret)

        def eb(failure):
            # TODO nick: logging
            return ArrayCollection()

        d = self.conn_pool.runQuery("SELECT name, url, email, created, message FROM " + \
            "message WHERE approved = 1 ORDER BY id DESC").addErrback(eb).addCallback(cb)

        return d

    def getMessageById(self, id):
        def cb(rs):
            return build_message(rs[0])

        return self.conn_pool.runQuery("SELECT name, url, email, created, message FROM " + \
            "message WHERE id = %d" % int(id)).addCallback(cb)

    @expose_request
    def addMessage(self, request, msg):
        """
        Adds a message to the guestbook

        @param request: The underlying HTTP request.
        @type msg: L{Message}
        """
        name = msg._amf_object.name
        url = msg._amf_object.url
        email = msg._amf_object.email
        message = msg._amf_object.message
 
        if not isinstance(name, basestring):
            name = str(name)

        if len(name) > 50:
            raise IOError, "Name exceeds maximum length (50 chars max)"

        if not isinstance(url, basestring):
            url = str(url)

        if len(url) > 255:
            raise IOError, "Website url exceeds maximum length (255 chars max)"

        if len(url) > 0:
            valid_url, reason = is_valid_url(url)

            if not valid_url:
                raise ValueError, "Website url not valid"

        if not isinstance(email, basestring):
            email = str(email)

        if not is_valid_email(email):
            raise ValueError, "Email address is not valid"

        if not isinstance(message, basestring):
            message = str(message)

        if len(message) == 0:
            raise ValueError, "Message is required"

        message = strip_message(message)
        response_deferred = defer.Deferred()

        def cb(rs):
            # rs contains the last inserted id of the message
            def cb2(msg):
                response_deferred.callback(msg)

            self.getMessageById(rs[0][0]).addCallback(cb2).addErrback(eb)

        def eb(failure):
            response_deferred.errback(failure)

        d = self.conn_pool.runQuery("INSERT INTO message (name, url, email, created, ip_address, message, approved)" + \
            " VALUES ('%s', '%s', '%s', NOW(), '%s', '%s', 1);" % (
                sql_safe(name),
                sql_safe(url),
                sql_safe(email),
                sql_safe(request.getClientIP()),
                sql_safe(message)
            )).addCallback(lambda x: self.conn_pool.runQuery("SELECT id FROM message ORDER BY id DESC LIMIT 0, 1"))

        d.addCallback(cb).addErrback(eb)

        return response_deferred
