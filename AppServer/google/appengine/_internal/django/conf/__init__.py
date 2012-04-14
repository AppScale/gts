"""
Settings and configuration for Django.

Values will be read from the module specified by the DJANGO_SETTINGS_MODULE environment
variable, and then from google.appengine._internal.django.conf.global_settings; see the global settings file for
a list of all possible variables.
"""

import os
import re
import threading
import time     # Needed for Windows

from google.appengine._internal.django.conf import global_settings
from google.appengine._internal.django.utils.functional import LazyObject
from google.appengine._internal.django.utils import importlib

ENVIRONMENT_VARIABLE = "DJANGO_SETTINGS_MODULE"

class LazySettings(threading.local):
    """
    A lazy proxy for either global Django settings or a custom settings object.
    The user can manually configure settings prior to using them. Otherwise,
    Django uses the settings module pointed to by DJANGO_SETTINGS_MODULE.
    """

    def __init__(self):
        self.holder = None

    def __getattr__(self, name):
        assert self.holder, 'settings has not been configured in this thread'
        return getattr(self.holder, name)

    def configure(self, default_settings=global_settings, **options):
        """
        Called to manually configure the settings. The 'default_settings'
        parameter sets where to retrieve any unspecified values from (its
        argument must support attribute access (__getattr__)).
        """
        self.holder = UserSettingsHolder(default_settings)
        for name, value in options.items():
            setattr(self.holder, name, value)

    configured = True

class Settings(object):
    def __init__(self, settings_module):
        # update this dict from global settings (but only for ALL_CAPS settings)
        for setting in dir(global_settings):
            if setting == setting.upper():
                setattr(self, setting, getattr(global_settings, setting))

        # store the settings module in case someone later cares
        self.SETTINGS_MODULE = settings_module

        try:
            mod = importlib.import_module(self.SETTINGS_MODULE)
        except ImportError, e:
            raise ImportError("Could not import settings '%s' (Is it on sys.path? Does it have syntax errors?): %s" % (self.SETTINGS_MODULE, e))

        # Settings that should be converted into tuples if they're mistakenly entered
        # as strings.
        tuple_settings = ("INSTALLED_APPS", "TEMPLATE_DIRS")

        for setting in dir(mod):
            if setting == setting.upper():
                setting_value = getattr(mod, setting)
                if setting in tuple_settings and type(setting_value) == str:
                    setting_value = (setting_value,) # In case the user forgot the comma.
                setattr(self, setting, setting_value)

        # Expand entries in INSTALLED_APPS like "django.contrib.*" to a list
        # of all those apps.
        new_installed_apps = []
        for app in self.INSTALLED_APPS:
            if app.endswith('.*'):
                app_mod = importlib.import_module(app[:-2])
                appdir = os.path.dirname(app_mod.__file__)
                app_subdirs = os.listdir(appdir)
                app_subdirs.sort()
                name_pattern = re.compile(r'[a-zA-Z]\w*')
                for d in app_subdirs:
                    if name_pattern.match(d) and os.path.isdir(os.path.join(appdir, d)):
                        new_installed_apps.append('%s.%s' % (app[:-2], d))
            else:
                new_installed_apps.append(app)
        self.INSTALLED_APPS = new_installed_apps

        if hasattr(time, 'tzset') and getattr(self, 'TIME_ZONE'):
            # Move the time zone info into os.environ. See ticket #2315 for why
            # we don't do this unconditionally (breaks Windows).
            os.environ['TZ'] = self.TIME_ZONE
            time.tzset()

class UserSettingsHolder(object):
    """
    Holder for user configured settings.
    """
    # SETTINGS_MODULE doesn't make much sense in the manually configured
    # (standalone) case.
    SETTINGS_MODULE = None

    def __init__(self, default_settings):
        """
        Requests for configuration variables not in this class are satisfied
        from the module specified in default_settings (if possible).
        """
        self.default_settings = default_settings

    def __getattr__(self, name):
        return getattr(self.default_settings, name)

    def __dir__(self):
        return self.__dict__.keys() + dir(self.default_settings)

    # For Python < 2.6:
    __members__ = property(lambda self: self.__dir__())

settings = LazySettings()

