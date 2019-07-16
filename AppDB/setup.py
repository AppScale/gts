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
    'cassandra-driver<3.18.0',
    'kazoo',
    'M2Crypto',
    'monotonic',
    'mmh3',
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
            'appscale.datastore.fdb',
            'appscale.datastore.scripts',
            'appscale.datastore.zkappscale'],
  entry_points={'console_scripts': [
    'appscale-backup-data=appscale.datastore.scripts.backup_data:main',
    'appscale-blobstore-server=appscale.datastore.scripts.blobstore:main',
    'appscale-cassandra-backup='
      'appscale.datastore.scripts.cassandra_backup:main',
    'appscale-data-layout=appscale.datastore.scripts.data_layout:main',
    'appscale-datastore=appscale.datastore.scripts.datastore:main',
    'appscale-delete-all-records='
      'appscale.datastore.scripts.delete_records:main',
    'appscale-get-token=appscale.datastore.cassandra_env.get_token:main',
    'appscale-groomer=appscale.datastore.groomer:main',
    'appscale-groomer-service=appscale.datastore.scripts.groomer_service:main',
    'appscale-prime-cassandra=appscale.datastore.scripts.prime_cassandra:main',
    'appscale-rebalance=appscale.datastore.cassandra_env.rebalance:main',
    'appscale-restore-data=appscale.datastore.scripts.restore_data:main',
    'appscale-transaction-groomer='
      'appscale.datastore.scripts.transaction_groomer:main',
    'appscale-uaserver=appscale.datastore.scripts.ua_server:main',
    'appscale-update-index=appscale.datastore.scripts.update_index:main',
    'appscale-upgrade-schema=appscale.datastore.scripts.upgrade_schema:main',
    'appscale-view-all-records=appscale.datastore.scripts.view_records:main',
  ]},
  package_data={'appscale.datastore.cassandra_env': ['templates/*']}
)
