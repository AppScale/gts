# TODO add the license
# I had to rewrite this class because the python MIME email.mime (version 2.5)
# are buggy, they use \n instead \r\n for new line which is not compliant
# to standard!
# http://bugs.python.org/issue5525

# TODO do not load all the message in memory stream it from the disk

import re
import random
import sys


# new line
NL = '\r\n'

_width = len(repr(sys.maxint - 1))
_fmt = '%%0%dd' % _width


class MIMEMessage:

    def __init__(self):
        self._files = []
        self._xmlMessage = ""
        self._startCID = ""
        self._boundary = ""

    def makeBoundary(self):
        # create the boundary
        msgparts = []
        msgparts.append(self._xmlMessage)
        for i in self._files:
            msgparts.append(i.read())
        # this sucks, all in memory
        alltext = NL.join(msgparts)
        self._boundary = _make_boundary(alltext)
        # maybe I can save some memory
        del alltext
        del msgparts
        self._startCID = "<" + (_fmt % random.randrange(sys.maxint)) \
            + (_fmt % random.randrange(sys.maxint)) + ">"

    def toString(self):
        '''it return a string with the MIME message'''
        if len(self._boundary) == 0:
            # the makeBoundary hasn't been called yet
            self.makeBoundary()
        # ok we have everything let's start to spit the message out
        # first the XML
        returnstr = NL + "--" + self._boundary + NL
        returnstr += "Content-Type: text/xml; charset=\"us-ascii\"" + NL
        returnstr += "Content-Transfer-Encoding: 7bit" + NL
        returnstr += "Content-Id: " + self._startCID + NL + NL
        returnstr += self._xmlMessage + NL
        # then the files
        for file in self._files:
            returnstr += "--" + self._boundary + NL
            returnstr += "Content-Type: application/octet-stream" + NL
            returnstr += "Content-Transfer-Encoding: binary" + NL
            returnstr += "Content-Id: <" + str(id(file)) + ">" + NL + NL
            file.seek(0)
            returnstr += file.read() + NL
        # closing boundary
        returnstr += "--" + self._boundary + "--" + NL
        return returnstr

    def attachFile(self, file):
        '''
        it adds a file to this attachment
        '''
        self._files.append(file)

    def addXMLMessage(self, xmlMessage):
        '''
        it adds the XML message. we can have only one XML SOAP message
        '''
        self._xmlMessage = xmlMessage

    def getBoundary(self):
        '''
        this function returns the string used in the mime message as a
        boundary. First the write method as to be called
        '''
        return self._boundary

    def getStartCID(self):
        '''
        This function returns the CID of the XML message
        '''
        return self._startCID


def _make_boundary(text=None):
    # some code taken from python stdlib
    # Craft a random boundary.  If text is given, ensure that the chosen
    # boundary doesn't appear in the text.
    token = random.randrange(sys.maxint)
    boundary = ('=' * 10) + (_fmt % token) + '=='
    if text is None:
        return boundary
    b = boundary
    counter = 0
    while True:
        cre = re.compile('^--' + re.escape(b) + '(--)?$', re.MULTILINE)
        if not cre.search(text):
            break
        b = boundary + '.' + str(counter)
        counter += 1
    return b
