from google.appengine._internal.django.conf.urls.defaults import *

urlpatterns = patterns('django.views',
    (r'^(?P<content_type_id>\d+)/(?P<object_id>.*)/$', 'defaults.shortcut'),
)
