from distutils.core import setup

setup(
  name='taskqueue-api-helpers',
  long_description=(
    'Taskqueue API helpers. Contains useful functions for sending '
    'REST and Protobuffer requests.\n'
    'Contains related protobuffer protocol definitions.'
  ),
  version='0.1',
  packages=['helpers'],
  license='Apache License 2.0',
  install_requires=[
    'attrs',
    'protobuf',
    'aiohttp',
  ],
)
