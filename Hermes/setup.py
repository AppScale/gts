from setuptools import setup

setup(
  name='appscale-hermes',
  version='0.0.2',
  description='TODO',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'tornado',
    'psutil==5.1.3',
    'attrs',
  ],
  tests_require=[
    'flexmock',
    'mock',
  ],
  test_suite='appscale.hermes',
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3'
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.hermes',
            'appscale.hermes.stats',
            'appscale.hermes.stats.producers',
            'appscale.hermes.stats.subscribers'],
  entry_points={'console_scripts': ['appscale-hermes=appscale.hermes:main']}
)