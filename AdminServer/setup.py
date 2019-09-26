import sys

from setuptools import setup

install_requires = [
  'appscale-common',
  'jsonschema',
  'kazoo',
  'idna>=2.5,<2.8',  # Required for requests.
  'monotonic',
  'psutil',
  'PyYaml',
  'requests-unixsocket',
  'six',
  'SOAPpy',
  'tabulate',
  'tornado',
  'mock',
]
if sys.version_info < (3,):
  install_requires.append('futures')

setup(
  name='appscale-admin',
  version='0.0.5',
  description='An implementation of the Google App Engine Admin API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=install_requires,
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.admin',
            'appscale.admin.instance_manager',
            'appscale.admin.routing'],
  package_data={'': ['*.json'],
                'appscale.admin.routing': ['templates/*']},
  include_package_data=True,
  entry_points={'console_scripts': [
    'appscale-admin=appscale.admin.admin_server:main',
    'appscale-instance-manager=appscale.admin.instance_manager.server:main',
    'appscale-stop-services=appscale.admin.stop_services:main',
    'appscale-stop-service=appscale.admin.stop_services:stop_service',
    'appscale-start-service=appscale.admin.stop_services:start_service'
  ]}
)
