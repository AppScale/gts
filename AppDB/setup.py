from setuptools import setup

setup(
  name='appscale-datastore',
  version='0.1.0',
  description='An implementation of the Google Cloud Datastore API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'kazoo',
    'monotonic',
    'mmh3',
    'psycopg2-binary',
    'SOAPpy',
    'tornado',
    'foundationdb~=6.1.8'
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
            'appscale.datastore.fdb',
            'appscale.datastore.fdb.stats',
            'appscale.datastore.scripts'],
  entry_points={'console_scripts': [
    'appscale-blobstore-server=appscale.datastore.scripts.blobstore:main',
    'appscale-datastore=appscale.datastore.scripts.datastore:main',
    'appscale-uaserver=appscale.datastore.scripts.ua_server:main',
    'appscale-uaserver-backup=appscale.datastore.scripts.ua_server_backup:main',
    'appscale-uaserver-restore=appscale.datastore.scripts.ua_server_restore:main',
  ]}
)
