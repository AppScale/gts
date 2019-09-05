from setuptools import setup

install_requires = [
  'appscale-common',
  # TODO: add 'appscale-agents' to required packages.
  'mock',
  'psutil==5.6.3',
  'tornado'
]

setup(
  name='appscale-infrastructure',
  version='0.0.1',
  description='AppScale module for communicating with cloud infrastructures.',
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
