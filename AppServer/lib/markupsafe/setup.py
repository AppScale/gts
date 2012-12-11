import os
import sys
from setuptools import setup, Extension, Feature
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsExecError, \
    DistutilsPlatformError


# fail safe compilation shamelessly stolen from the simplejson
# setup.py file.  Original author: Bob Ippolito

is_jython = 'java' in sys.platform
is_pypy = hasattr(sys, 'pypy_version_info')


speedups = Feature(
    'optional C speed-enhancement module',
    standard=True,
    ext_modules = [
        Extension('markupsafe._speedups', ['markupsafe/_speedups.c']),
    ],
)

ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)
if sys.platform == 'win32' and sys.version_info > (2, 6):
   # 2.6's distutils.msvc9compiler can raise an IOError when failing to
   # find the compiler
   ext_errors += (IOError,)


extra = {}
if sys.version_info >= (3, 0):
    extra['use_2to3'] = True


class BuildFailed(Exception):
    pass


class ve_build_ext(build_ext):
    """This class allows C extension building to fail."""

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except ext_errors:
            raise BuildFailed()
        except ValueError:
            # this can happen on Windows 64 bit, see Python issue 7511
            if "'path'" in str(sys.exc_info()[1]): # works with Python 2 and 3
                raise BuildFailed()
            raise


def echo(msg=''):
    sys.stdout.write(msg + '\n')


readme = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()


def run_setup(with_binary):
    features = {}
    if with_binary:
        features['speedups'] = speedups
    setup(
        name='MarkupSafe',
        version='0.15',
        url='http://dev.pocoo.org/',
        license='BSD',
        author='Armin Ronacher',
        author_email='armin.ronacher@active-4.com',
        description='Implements a XML/HTML/XHTML Markup safe string for Python',
        long_description=readme,
        zip_safe=False,
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Text Processing :: Markup :: HTML'
        ],
        packages=['markupsafe'],
        test_suite='markupsafe.tests.suite',
        include_package_data=True,
        cmdclass={'build_ext': ve_build_ext},
        features=features,
        **extra
    )


def try_building_extension():
    try:
        run_setup(True)
    except BuildFailed:
        LINE = '=' * 74
        BUILD_EXT_WARNING = 'WARNING: The C extension could not be ' \
                            'compiled, speedups are not enabled.'

        echo(LINE)
        echo(BUILD_EXT_WARNING)
        echo('Failure information, if any, is above.')
        echo('Retrying the build without the C extension now.')
        echo()

        run_setup(False)

        echo(LINE)
        echo(BUILD_EXT_WARNING)
        echo('Plain-Python installation succeeded.')
        echo(LINE)


if not (is_pypy or is_jython):
    try_building_extension()
else:
    run_setup(False)
