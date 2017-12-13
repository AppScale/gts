from setuptools import setup

setup(
  name='appscale-controller-client',
  version='0.0.1',
  description='A client used for making AppController calls',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=['SOAPpy'],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
  ],
  namespace_packages=['appscale'],
  packages=['appscale',
            'appscale.appcontroller_client']
)
