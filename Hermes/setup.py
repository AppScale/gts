from setuptools import setup

setup(
  name='appscale-hermes',
  version='0.4.0',
  description='AppScale module which provides statistics API.',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'appscale-admin',
    'psutil==5.6.3',
    'attrs==19.1.0',
    'mock==2.0.0',
    'aiohttp==2.3.9'
  ],
  classifiers=[
    'Development Status :: 3 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 3.5'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.hermes',
            'appscale.hermes.producers'],
  entry_points={'console_scripts': [
    'appscale-hermes=appscale.hermes.hermes_server:main'
  ]}
)
