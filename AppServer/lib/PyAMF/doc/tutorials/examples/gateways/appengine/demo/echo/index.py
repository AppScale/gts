# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Index page for GAE echo example.

@since: 0.3.0
"""

from google.appengine.ext.webapp import template

print "Content-Type: text/html"
print
print template.render('../templates/swf.html', {
    'swf_url': '/static/echo_test.swf',
    'width': '900px',
    'height': '700px',
    'flash_ver': '9.0.0'
})
