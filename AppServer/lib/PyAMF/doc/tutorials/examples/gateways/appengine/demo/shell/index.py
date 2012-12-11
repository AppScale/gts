# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

from google.appengine.ext.webapp import template

print "Content-Type: text/html"
print
print template.render('../templates/swf.html', {
    'swf_url': '/assets/swf/shell.swf',
    'width': '900px',
    'height': '650px',
    'flash_ver': '9.0.0'
})