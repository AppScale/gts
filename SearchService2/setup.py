from setuptools import setup

setup(
  name='appscale-search2',
  version='1.0.0',
  description='An implementation of the Google App Engine Search API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common>=0.0.4',
    'boto3==1.9.178',
    'kazoo==2.6.0',
    'tornado==5.1.1',
    'attrs==18.2.0',
    'protobuf==3.6.1',
    'antlr4-python3-runtime==4.7.2',  # Should match version in
                                      # build-scripts/compile_query_grammar.sh
  ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 3'
  ],
  namespace_packages=['appscale'],
  packages=[
    'appscale',
    'appscale.search',
    'appscale.search.protocols',
    'appscale.search.query_parser',
    'appscale.search.backup_restore',
  ],
  include_package_data=True,
  entry_points={'console_scripts': [
    'appscale-search2=appscale.search.search_server:main',
    'appscale-search2-reindex=appscale.search.scripts:reindex',
    'appscale-list-solr-collections=appscale.search.scripts:list_solr_collections',
    'appscale-delete-solr-collection=appscale.search.scripts:delete_solr_collection',
    'appscale-search-backup-from-v1=appscale.search.backup_restore.backup_from_v1:main',
    'appscale-search-backup-from-v2=appscale.search.backup_restore.backup_from_v2:main',
    'appscale-search-restore-to-v2=appscale.search.backup_restore.restore_to_v2:main'
  ]}
)
