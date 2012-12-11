# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tools for doing dynamic imports.

@since: 0.3
"""

import sys


__all__ = ['when_imported']


def when_imported(name, *hooks):
    """
    Call C{hook(module)} when module named C{name} is first imported. C{name}
    must be a fully qualified (i.e. absolute) module name.

    C{hook} must accept one argument: which will be the imported module object.

    If the module has already been imported, 'hook(module)' is called
    immediately, and the module object is returned from this function. If the
    module has not been imported, then the hook is called when the module is
    first imported.
    """
    global finder

    finder.when_imported(name, *hooks)


class ModuleFinder(object):
    """
    This is a special module finder object that executes a collection of
    callables when a specific module has been imported. An instance of this
    is placed in C{sys.meta_path}, which is consulted before C{sys.modules} -
    allowing us to provide this functionality.

    @ivar post_load_hooks: C{dict} of C{full module path -> callable} to be
        executed when the module is imported.
    @ivar loaded_modules: C{list} of modules that this finder has seen. Used
        to stop recursive imports in L{load_module}
    @see: L{when_imported}
    @since: 0.5
    """

    def __init__(self):
        self.post_load_hooks = {}
        self.loaded_modules = []

    def find_module(self, name, path=None):
        """
        Called when an import is made. If there are hooks waiting for this
        module to be imported then we stop the normal import process and
        manually load the module.

        @param name: The name of the module being imported.
        @param path The root path of the module (if a package). We ignore this.
        @return: If we want to hook this module, we return a C{loader}
            interface (which is this instance again). If not we return C{None}
            to allow the standard import process to continue.
        """
        if name in self.loaded_modules:
            return None

        hooks = self.post_load_hooks.get(name, None)

        if hooks:
            return self

    def load_module(self, name):
        """
        If we get this far, then there are hooks waiting to be called on
        import of this module. We manually load the module and then run the
        hooks.

        @param name: The name of the module to import.
        """
        self.loaded_modules.append(name)

        try:
            __import__(name, {}, {}, [])

            mod = sys.modules[name]
            self._run_hooks(name, mod)
        except:
            self.loaded_modules.pop()

            raise

        return mod

    def when_imported(self, name, *hooks):
        """
        @see: L{when_imported}
        """
        if name in sys.modules:
            for hook in hooks:
                hook(sys.modules[name])

            return

        h = self.post_load_hooks.setdefault(name, [])
        h.extend(hooks)

    def _run_hooks(self, name, module):
        """
        Run all hooks for a module.
        """
        hooks = self.post_load_hooks.pop(name, [])

        for hook in hooks:
            hook(module)

    def __getstate__(self):
        return (self.post_load_hooks.copy(), self.loaded_modules[:])

    def __setstate__(self, state):
        self.post_load_hooks, self.loaded_modules = state


def _init():
    """
    Internal function to install the module finder.
    """
    global finder

    if finder is None:
        finder = ModuleFinder()

    if finder not in sys.meta_path:
        sys.meta_path.insert(0, finder)


finder = None
_init()
