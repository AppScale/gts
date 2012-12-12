# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Ohloh API example to retrieve account info.

@since: 0.3.1
"""

import urllib, hashlib

try:
    import xml.etree.ElementTree as ET
except ImportError:
    try:
        import cElementTree as ET
        ET._ElementInterface = ET.ElementTree
    except ImportError:
       import elementtree.ElementTree as ET

def getAccount(email, api_key='123456789'):
    # We pass the MD5 hash of the email address
    emailhash = hashlib.md5()
    emailhash.update(email)

    # Connect to the Ohloh website and retrieve the account data.
    params = urllib.urlencode({'api_key': api_key, 'v': 1})
    url = "http://www.ohloh.net/accounts/%s.xml?%s" % (emailhash.hexdigest(), params)
    f = urllib.urlopen(url)
    
    # Parse the response into a structured XML object
    tree = ET.parse(f)
    
    # Did Ohloh return an error?
    elem = tree.getroot()
    error = elem.find("error")
    if error != None:
        raise Exception(ET.tostring(error))
    
    # Return raw XML data
    return elem
