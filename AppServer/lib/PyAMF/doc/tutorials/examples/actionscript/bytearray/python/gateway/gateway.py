# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

import logging

from pyamf.remoting.gateway.django import DjangoGateway

import python.gateway.views as views
from python.settings import DEBUG


services = {
    'ByteArray.saveSnapshot': views.save_snapshot,
    'getSnapshots': views.get_snapshots
}

gw = DjangoGateway(services, logger=logging, debug=DEBUG)
