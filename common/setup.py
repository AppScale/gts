from setuptools import setup
import sys

install_requires = [
  'kazoo==2.6.0',
  'monotonic',
  'PyYAML>=4.2b1'
  'mock==2.0.0'
]

if sys.version_info < (3,):
  install_requires.append('future==0.17.1')

setup(
  name='appscale-common',
  version='0.0.5',
  description='Modules used by multiple AppScale packages',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=install_requires,
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.common',
            'appscale.common.service_stats'],
  package_data={'appscale.common': ['templates/*']}
)
