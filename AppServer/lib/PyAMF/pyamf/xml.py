# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Provides XML support.

@since: 0.6
"""

#: list of supported third party packages that support the C{etree}
#: interface. At least enough for our needs anyway.
ETREE_MODULES = [
    'lxml.etree',
    'xml.etree.cElementTree',
    'cElementTree',
    'xml.etree.ElementTree',
    'elementtree.ElementTree'
]

#: A tuple of class/type objects that are used to represent XML objects.
types = None
#: A mapping of type -> module for all known xml types.
modules = {}
#: The module that will be used to create C{ElementTree} instances.
ET = None

__all__ = ['set_default_interface']


def set_default_interface(etree):
    """
    Sets the default interface that PyAMF will use to deal with XML entities
    (both objects and blobs).
    """
    global types, ET, modules

    t = _get_etree_type(etree)

    _types = set(types or [])
    _types.update([t])

    types = tuple(_types)

    modules[t] = etree

    old, ET = ET, etree

    return old


def find_libs():
    """
    Run through L{ETREE_MODULES} and find C{ElementTree} implementations so
    that any type can be encoded.

    We work through the C implementations first, then the pure Python versions.
    The downside to this is that B{all} libraries will be imported but I{only}
    one is ever used. The libs are small (relatively) and the flexibility that
    this gives seems to outweigh the cost. Time will tell.
    """
    from pyamf.util import get_module

    types = []
    mapping = {}

    for mod in ETREE_MODULES:
        try:
            etree = get_module(mod)
        except ImportError:
            continue

        t = _get_etree_type(etree)

        types.append(t)
        mapping[t] = etree

    return tuple(types), mapping


def is_xml(obj):
    """
    Determines C{obj} is a valid XML type.

    If L{types} is not populated then L{find_libs} be called.
    """
    global types

    try:
        _bootstrap()
    except ImportError:
        return False

    return isinstance(obj, types)


def _get_type(e):
    """
    Returns the type associated with handling XML objects from this etree
    interface.
    """
    try:
        return e.__class__
    except AttributeError:
        return type(e)


def _get_etree_type(etree):
    """
    Returns the type associated with handling XML objects from this etree
    interface.
    """
    e = etree.fromstring('<foo/>')

    return _get_type(e)


def _no_et():
    raise ImportError('Unable to find at least one compatible ElementTree '
        'library, use pyamf.set_default_etree to enable XML support')


def _bootstrap():
    global types, modules, ET

    if types is None:
        types, modules = find_libs()

    if ET is None:
        try:
            etree = modules[types[0]]
        except IndexError:
            _no_et()

        set_default_interface(etree)


def tostring(element, *args, **kwargs):
    """
    Helper func to provide easy access to the (possibly) moving target that is
    C{ET}.
    """
    global modules

    _bootstrap()
    t = _get_type(element)

    etree = modules.get(t, None)

    if not etree:
        raise RuntimeError('Unable to find the etree implementation related '
            'to %r (type %r)' % (element, t))

    return etree.tostring(element, *args, **kwargs)


def fromstring(*args, **kwargs):
    """
    Helper func to provide easy access to the (possibly) moving target that is
    C{ET}.
    """
    global ET

    _bootstrap()

    return ET.fromstring(*args, **kwargs)
