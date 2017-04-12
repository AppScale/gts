import glob
from setuptools import setup

setup(
  name='appscale-taskqueue',
  version='0.0.1',
  description='An implementation of the App Engine Task Queue API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'cassandra-driver',
    'celery<4.0.0',
    'PyYaml',
    'tornado==4.2.0'
  ],
  extras_require={'celery_gui': ['flower']},
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 2.7',
  ],
  namespace_packages=['appscale'],
  packages=['appscale', 'appscale.taskqueue', 'appscale.taskqueue.brokers'],
  entry_points={
    'console_scripts': [
      'appscale-taskqueue=appscale.taskqueue.appscale_taskqueue:main'
    ]
  },
  package_data={'appscale.taskqueue': ['templates/*']}
)
