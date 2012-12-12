from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^python/', include('python.foo.urls')),

    # Uncomment this for admin:
    # (r'^admin/', include('django.contrib.admin.urls')),
    
    (r'^gateway/shell/', 'python.gateway.gateway'),
)
