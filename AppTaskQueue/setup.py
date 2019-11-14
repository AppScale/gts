from setuptools import setup

setup(
  name='appscale-taskqueue',
  version='0.1.0',
  description='An implementation of the App Engine Task Queue API',
  author='AppScale Systems, Inc.',
  url='https://github.com/AppScale/appscale',
  license='Apache License 2.0',
  keywords='appscale google-app-engine python',
  platforms='Posix',
  install_requires=[
    'appscale-common',
    'celery>=3.1,<4.0.0',
    'eventlet==0.22',
    'kazoo',
    'monotonic',
    'protobuf',
    'psycopg2-binary',
    'PyYaml>=4.2b1',
    'requests',
    'tornado==4.2.0'
  ],
  extras_require={'celery_gui': ['flower']},
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 3',
  ],
  namespace_packages=['appscale'],
  packages=[
    'appscale',
    'appscale.taskqueue',
    'appscale.taskqueue.brokers',
    'appscale.taskqueue.protocols'
  ],
  entry_points={
    'console_scripts': [
      'appscale-taskqueue=appscale.taskqueue.appscale_taskqueue:main'
    ]
  }
)
