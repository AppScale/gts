from setuptools import setup

setup(
  name='appscale-remote-profiler',
  version='0.0.1',
  description='AppScale module which helps to monitor '
              'remote deployment using statistics API.',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'attrs>=16',
    'flexmock',
    'mock',
    'requests'
  ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.hermes',
            'appscale.hermes.stats',
            'appscale.hermes.stats.client'],
  entry_points={
    'console_scripts': [
      ('appscale-remote-profiler='
       'appscale.hermes.stats.client.remote_profiler:main')
    ]
  }
)
