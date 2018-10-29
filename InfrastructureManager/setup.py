import sys

from setuptools import setup

install_requires = [
  'appscale-common',
  'appscale-tools',
  'requests[security]>=2.16.0,<=2.19.1',
  'cryptography>=2.3.0',
  'psutil',
  'tornado',
  'kazoo'
]

setup(
  name='appscale-infrastructure',
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
    'Programming Language :: Python :: 2.7'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.infrastructure'],
  entry_points={'console_scripts': [
    'appscale-infrastructure=appscale.infrastructure:main'
  ]}
)
