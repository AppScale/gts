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
  ],
  include_package_data=True,
  entry_points={'console_scripts': [
    'appscale-search2=appscale.search.search_server:main',
  ]}
)
