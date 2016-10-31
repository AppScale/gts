import glob
from setuptools import setup

setup(
  name='appscale-datastore',
  version='0.0.1',
  description='An implementation of the Google Cloud Datastore API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'cassandra-driver',
    'kazoo',
    'M2Crypto',
    'SOAPpy',
    'tornado'
  ],
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.datastore',
            'appscale.datastore.cassandra_env',
            'appscale.datastore.backup',
            'appscale.datastore.zkappscale'],
  scripts=glob.glob('scripts/*'),
  package_data={'appscale.datastore.cassandra_env': ['templates/*']}
)
