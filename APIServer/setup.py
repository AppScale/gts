from setuptools import setup


setup(
  name='appscale-api-server',
  version='0.0.1',
  description=('A server that handles API requests from App Engine Standard '
               'Environment runtimes'),
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-admin',
    'appscale-common',
    'cryptography',
    'kazoo',
    'protobuf',
    'six',
    'tornado'
  ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.api_server'],
  entry_points={'console_scripts': [
    'appscale-api-server=appscale.api_server.server:main'
  ]}
)
