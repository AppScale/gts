# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

import os.path

from django.conf.urls.defaults import *

import python.gateway

urlpatterns = patterns('',
    # Example:
    # (r'^python/', include('python.foo.urls')),

    (r'^images/(?P<path>.*)$', 'django.views.static.serve', {'document_root': python.gateway.images_root}),
    (r'^$', 'python.gateway.gateway.gw'),
    (r'^crossdomain.xml$', 'django.views.static.serve',
     {'document_root': os.path.abspath(os.path.dirname(__file__)), 'path': 'crossdomain.xml'}),
    # Uncomment this for admin:
    # (r'^admin/', include('django.contrib.admin.urls')),
)
