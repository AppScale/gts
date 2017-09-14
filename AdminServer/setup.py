import sys

from setuptools import setup

install_requires = [
  'appscale-common',
  'kazoo',
  'PyYaml',
  'SOAPpy',
  'tornado'
]
if sys.version_info < (3,):
  install_requires.append('futures')

setup(
  name='appscale-admin',
  version='0.0.1',
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
            'appscale.admin.instance_manager'],
  entry_points={'console_scripts': ['appscale-admin=appscale.admin:main']}
)
