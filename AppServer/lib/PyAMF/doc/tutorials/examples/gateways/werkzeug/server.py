#!/usr/bin/env python
# -*- coding: utf-8 -*-

from werkzeug import run_simple

from pyamf.remoting.gateway.wsgi import WSGIGateway

import logging
        

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


def echo(data):
    return data

services = {'echo': echo}
gw = WSGIGateway(services, logger=logging, debug=True)

run_simple('localhost', 8080, gw, use_reloader=True)