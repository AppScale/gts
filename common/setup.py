from setuptools import setup

setup(
  name='appscale-common',
  version='0.0.3',
  description='Modules used by multiple AppScale packages',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'kazoo',
    'PyYAML',
    'future'
  ],
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
