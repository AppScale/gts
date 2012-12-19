from pyamf.remoting.gateway.wsgi import WSGIGateway

def echo(data):
   return data

services = {
   'echo': echo,
   # Add other exposed functions here
}

gateway = WSGIGateway(services)
