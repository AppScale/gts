"""
"""

from django.contrib.auth import models

import pyamf.adapters


models.User.__amf__ = {
    'exclude': ('message_set', 'password'),
    'readonly': ('username',)
}

# ensure that the adapter that we depend on is loaded ..
pyamf.adapters.get_adapter('django.db.models.base')

pyamf.register_package(models, models.__name__)