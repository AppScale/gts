# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
The adapter package provides additional functionality for other Python
packages. This includes registering classes, setting up type maps etc.

@since: 0.1.0
"""

import os.path
import glob

from pyamf.util import imports


adapters_registered = False


class PackageImporter(object):
    """
    Package importer used for lazy module loading.
    """
    def __init__(self, name):
        self.name = name

    def __call__(self, mod):
        __import__('%s.%s' % ('pyamf.adapters', self.name))


def register_adapters():
    global adapters_registered

    if adapters_registered is True:
        return

    try:
        import pkg_resources
        packageDir = pkg_resources.resource_filename('pyamf', 'adapters')
    except:
        packageDir = os.path.dirname(__file__)

    for f in glob.glob(os.path.join(packageDir, '*.py')):
        mod = os.path.basename(f).split(os.path.extsep, 1)[0]

        if mod == '__init__' or not mod.startswith('_'):
            continue

        try:
            register_adapter(mod[1:].replace('_', '.'), PackageImporter(mod))
        except ImportError:
            pass

    adapters_registered = True


def register_adapter(mod, func):
    """
    Registers a callable to be executed when a module is imported. If the
    module already exists then the callable will be executed immediately.
    You can register the same module multiple times, the callables will be
    executed in the order they were registered. The root module must exist
    (i.e. be importable) otherwise an `ImportError` will be thrown.

    @param mod: The fully qualified module string, as used in the imports
        statement. E.g. 'foo.bar.baz'. The string must map to a module
        otherwise the callable will not fire.
    @param func: The function to call when C{mod} is imported. This function
        must take one arg, the newly imported C{module} object.
    @type func: callable
    @raise TypeError: C{func} must be callable
    """
    if not hasattr(func, '__call__'):
        raise TypeError('func must be callable')

    imports.when_imported(mod, func)


def get_adapter(mod):
    """
    """
    base_name = '_' + mod.replace('.', '_')

    full_import = '%s.%s' % (__name__, base_name)

    ret = __import__(full_import)

    for attr in full_import.split('.')[1:]:
        ret = getattr(ret, attr)

    return ret
