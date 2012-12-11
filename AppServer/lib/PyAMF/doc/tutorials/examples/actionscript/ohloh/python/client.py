#!/usr/bin/python
#
# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
This is an example of using the Ohloh API from a Python client.

Detailed information can be found at the Ohloh website:

     http://www.ohloh.net/api

This example uses the ElementTree library for XML parsing
(included in Python 2.5 and newer):

     http://effbot.org/zone/element-index.htm

This example retrieves basic Ohloh account information
and outputs it as simple name: value pairs.

Pass your Ohloh API key as the first parameter to this script.
Ohloh API keys are free. If you do not have one, you can obtain
one at the Ohloh website:

     http://www.ohloh.net/api_keys/new

Pass the email address of the account as the second parameter
to this script.
"""


import sys
import ohloh


if len(sys.argv) == 3:
    api_key = sys.argv[1]
    email = sys.argv[2]
else:
    print "Usage: client.py <api-key> <email-address>"
    sys.exit()
    
elem = ohloh.getAccount(email, api_key)

# Output all the immediate child properties of an Account
for node in elem.find("result/account"):
    if node.tag == "kudo_score":
        print "%s:" % node.tag
        for score in elem.find("result/account/kudo_score"):
            print "\t%s:\t%s" % (score.tag, score.text)
    else:
        print "%s:\t%s" % (node.tag, node.text)
