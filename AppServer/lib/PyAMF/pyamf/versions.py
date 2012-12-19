# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Because there is disparity between Python packaging (and it is being sorted
out ...) we currently provide our own way to get the string of a version tuple.

@since: 0.6
"""


class Version(tuple):

    _version = None

    def __new__(cls, *args):
        x = tuple.__new__(cls, args)

        return x

    def __str__(self):
        if not self._version:
            self._version = get_version(self)

        return self._version


def get_version(_version):
    v = ''
    prev = None

    for x in _version:
        if prev is not None:
            if isinstance(x, int):
                v += '.'

        prev = x
        v += str(x)

    return v.strip('.')
