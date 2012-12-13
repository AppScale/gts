from django.conf.urls.defaults import *

urlpatterns = patterns('django.views.generic.simple',
    (r'^$', 'direct_to_template', {'template': 'index.html'}),
)

# ByteArray demo urls
urlpatterns += patterns('django.views.generic.simple',
    (r'^bytearray/$', 'direct_to_template', {'template': 'swf.html', 'extra_context': {
        'swf_url': '/assets/swf/bytearray.swf',
        'width': '500px',
        'height': '600px',
        'flash_ver': '9.0.0',
        'title': 'PyAMF ByteArray Demo'
    }}),
)

urlpatterns += patterns('',
    (r'^gateway/bytearray/', 'bytearray.gateway.gateway'),
)

# Shell example

urlpatterns += patterns('django.views.generic.simple',
    (r'^shell/$', 'direct_to_template', {'template': 'swf.html', 'extra_context': {
        'swf_url': '/assets/swf/shell.swf',
        'width': '800px',
        'height': '600px',
        'flash_ver': '9.0.0',
        'title': 'PyAMF Python Shell Demo'
    }}),
)

urlpatterns += patterns('',
    (r'^gateway/shell/', 'shell.gateway.gateway'),
)

# EchoTest example

urlpatterns += patterns('django.views.generic.simple',
    (r'^echo/$', 'direct_to_template', {'template': 'swf.html', 'extra_context': {
        'swf_url': '/assets/swf/echo_test.swf',
        'width': '800px',
        'height': '600px',
        'flash_ver': '9.0.0',
        'title': 'PyAMF Echo Test Demo'
    }}),
)

urlpatterns += patterns('',
    (r'^gateway/echo/', 'echo.gateway.gateway'),
)

