#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
















"""Code to exist off of google.appengine.dist.

Kept in a separate file from the __init__ module for testing purposes.
"""


__all__ = ['use_library']


try:
  import distutils.version
except ImportError:

  distutils = None

import os
import sys

server_software = os.getenv('SERVER_SOFTWARE')
USING_SDK = not server_software or server_software.startswith('Dev')
del server_software


_DESIRED_DJANGO_VERSION = 'v0_96'



AUTO_IMPORT_FIXER_FILE = 'auto_import_fixer.py'


def fix_paths(app_path, python_lib_path):
  """Fix the __path__ attr of sys.modules entries.

  Specifically this fixes the path of those sys.modules package entries that
  have __path__ attributes that point to the python library, but where there
  is a similar package in the application's code.

  Args:
    app_path: The root path of the application code.
    python_lib_path: The root path of the python library.
  """




  if os.path.isfile(os.path.join(app_path, AUTO_IMPORT_FIXER_FILE)):
    return

  for module_name, module in sys.modules.items():
    if getattr(module, '__path__', None) is None:
      continue






    module_app_path = os.path.join(app_path, *module_name.split('.'))
    module_init_file = os.path.join(module_app_path, '__init__.py')
    if not os.path.isfile(module_init_file):

      continue

    found_python_lib_path = False
    found_app_path = False
    for path in module.__path__:
      if path.startswith(python_lib_path):
        found_python_lib_path = True

      if path.startswith(app_path):
        found_app_path = True

    if found_python_lib_path and not found_app_path:



      module.__path__.append(module_app_path)


try:
  import google
except ImportError:
  import google as google

if not USING_SDK:

  this_version = os.path.dirname(os.path.dirname(google.__file__))
  versions = os.path.dirname(this_version)
  PYTHON_LIB = os.path.dirname(versions)

  fix_paths(sys.path[-1], PYTHON_LIB)

  del this_version, versions
else:


  PYTHON_LIB = os.path.dirname(os.path.dirname(google.__file__))

del google



installed = {}



def SetAllowedModule(_):
  pass


class UnacceptableVersionError(Exception):
  """Raised when a version of a package that is unacceptable is requested."""
  pass



class LooseVersion(object):
  """Shallow class compatible with distutils.version.LooseVersion."""

  def __init__(self, version):
    """Create a new instance of LooseVersion.

    Args:
      version: iterable containing the version values.
    """
    self.version = tuple(map(str, version))

  def __repr__(self):
    return '.'.join(self.version)

  def __str__(self):
    return '.'.join(self.version)

  @classmethod
  def parse(cls, string):
    """Parse a version string and create a new LooseVersion instance.

    Args:
      string: dot delimited version string.

    Returns:
      A distutils.version.LooseVersion compatible object.
    """
    return cls(string.split('.'))


def DjangoVersion():
  """Discover the version of Django installed.

  Returns:
    A distutils.version.LooseVersion.
  """
  try:

    __import__('django.' + _DESIRED_DJANGO_VERSION)
  except ImportError:
    pass
  import django
  try:
    return distutils.version.LooseVersion('.'.join(map(str, django.VERSION)))
  except AttributeError:

    return LooseVersion(django.VERSION)


def PylonsVersion():
  """Discover the version of Pylons installed.

  Returns:
    A distutils.version.LooseVersion.
  """
  import pylons
  return distutils.version.LooseVersion(pylons.__version__)















PACKAGES = {
    'django': (DjangoVersion,
               {'0.96': None,
                '1.0': None,
                '1.1': None,
                '1.2': None,
                '1.3': None,
                }),







    '_test': (lambda: distutils.version.LooseVersion('1.0'), {'1.0': None}),
    '_testpkg': (lambda: distutils.version.LooseVersion('1.0'),
                 {'1.0': set([('_test', '1.0')])}),
    }


def EqualVersions(version, baseline):
  """Test that a version is acceptable as compared to the baseline.

  Meant to be used to compare version numbers as returned by a package itself
  and not user input.

  Args:
    version: distutils.version.LooseVersion.
        The version that is being checked.
    baseline: distutils.version.LooseVersion.
        The version that one hopes version compares equal to.

  Returns:
    A bool indicating whether the versions are considered equal.
  """





  baseline_tuple = baseline.version
  truncated_tuple = version.version[:len(baseline_tuple)]
  if truncated_tuple == baseline_tuple:
    return True
  else:
    return False


def AllowInstalledLibrary(name, desired):
  """Allow the use of a package without performing a version check.

  Needed to clear a package's dependencies in case the dependencies need to be
  imported in order to perform a version check. The version check is skipped on
  the dependencies because the assumption is that the package that triggered
  the call would not be installed without the proper dependencies (which might
  be a different version than what the package explicitly requires).

  Args:
    name: Name of package.
    desired: Desired version.

  Raises:
    UnacceptableVersion Error if the installed version of a package is
    unacceptable.
  """
  CallSetAllowedModule(name, desired)
  dependencies = PACKAGES[name][1][desired]
  if dependencies:
    for dep_name, dep_version in dependencies:
      AllowInstalledLibrary(dep_name, dep_version)
  installed[name] = desired, False


def CheckInstalledLibrary(name, desired):
  """Check that the library and its dependencies are installed.

  Args:
    name: Name of the library that should be installed.
    desired: The desired version.

  Raises:
    UnacceptableVersionError if the installed version of a package is
    unacceptable.
  """
  dependencies = PACKAGES[name][1][desired]
  if dependencies:
    for dep_name, dep_version in dependencies:
      AllowInstalledLibrary(dep_name, dep_version)
  CheckInstalledVersion(name, desired, explicit=True)


def CheckInstalledVersion(name, desired, explicit):
  """Check that the installed version of a package is acceptable.

  Args:
    name: Name of package.
    desired: Desired version string.
    explicit: Explicitly requested by the user or implicitly because of a
      dependency.

  Raises:
    UnacceptableVersionError if the installed version of a package is
    unacceptable.
  """
  CallSetAllowedModule(name, desired)
  find_version = PACKAGES[name][0]
  if name == 'django':
    global _DESIRED_DJANGO_VERSION
    _DESIRED_DJANGO_VERSION = 'v' + desired.replace('.', '_')
  installed_version = find_version()
  try:
    desired_version = distutils.version.LooseVersion(desired)
  except AttributeError:

    desired_version = LooseVersion.parse(desired)

  if not EqualVersions(installed_version, desired_version):
    raise UnacceptableVersionError(
        '%s %s was requested, but %s is already in use' %
        (name, desired_version, installed_version))
  installed[name] = desired, explicit


def CallSetAllowedModule(name, desired):
  """Helper to call SetAllowedModule(name), after special-casing Django."""

  if USING_SDK and name == 'django':

    sys.path[:] = [dirname
                   for dirname in sys.path
                   if not dirname.startswith(os.path.join(
                       PYTHON_LIB, 'lib', 'django'))]




    if desired in ('0.96', '1.2', '1.3'):
      sys.path.insert(1, os.path.join(PYTHON_LIB, 'lib', 'django-' + desired))
  SetAllowedModule(name)


def CreatePath(name, version):
  """Create the path to a package."""
  package_dir = '%s-%s' % (name, version)
  return os.path.join(PYTHON_LIB, 'versions', 'third_party', package_dir)


def RemoveLibrary(name):
  """Remove a library that has been installed."""
  installed_version, _ = installed[name]
  path = CreatePath(name, installed_version)
  try:
    sys.path.remove(path)
  except ValueError:
    pass
  del installed[name]


def AddLibrary(name, version, explicit):
  """Add a library to sys.path and 'installed'."""
  sys.path.insert(1, CreatePath(name, version))
  installed[name] = version, explicit


def InstallLibrary(name, version, explicit=True):
  """Install a package.

  If the installation is explicit then the user made the installation request,
  not a package as a dependency. Explicit installation leads to stricter
  version checking.

  Args:
    name: Name of the requested package (already validated as available).
    version: The desired version (already validated as available).
    explicit: Explicitly requested by the user or implicitly because of a
      dependency.
  """
  installed_version, explicitly_installed = installed.get(name, [None] * 2)





  if name in sys.modules:
    if explicit:
      CheckInstalledVersion(name, version, explicit=True)
    return

  elif installed_version:
    if version == installed_version:
      return


    if explicit:
      if explicitly_installed:
        raise ValueError('%s %s requested, but %s already in use' %
                         (name, version, installed_version))
      RemoveLibrary(name)


    else:
      version_ob = distutils.version.LooseVersion(version)
      installed_ob = distutils.version.LooseVersion(installed_version)
      if version_ob <= installed_ob:
        return
      else:
        RemoveLibrary(name)

  AddLibrary(name, version, explicit)
  dep_details = PACKAGES[name][1][version]
  if not dep_details:
    return
  for dep_name, dep_version in dep_details:
    InstallLibrary(dep_name, dep_version, explicit=False)


def use_library(name, version):
  """Specify a third-party package to use.

  Args:
    name: Name of package to use.
    version: Version of the package to use (string).
  """
  if name not in PACKAGES:
    raise ValueError('%s is not a supported package' % name)
  versions = PACKAGES[name][1].keys()
  if version not in versions:
    raise ValueError('%s is not a supported version for %s; '
                     'supported versions are %s' % (version, name, versions))
  if USING_SDK:
    CheckInstalledLibrary(name, version)
  else:
    InstallLibrary(name, version, explicit=True)


if not USING_SDK:








  InstallLibrary('django', '0.96', explicit=False)
