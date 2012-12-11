# yourproject/yourapp/amfgateway.py

from pyamf.remoting.gateway.django import DjangoGateway

def echo(request, data):
    return data

services = {
    'myservice.echo': echo
    # could include other functions as well
}

echoGateway = DjangoGateway(services)