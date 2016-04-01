""" Client app utilities. """

import logging
import re

from mapreduce import control

from custom_exceptions import BackupValidationException
from custom_exceptions import RestoreValidationException

# The bucket regex a bucket name must match.
BUCKET_PATTERN = (r'^([a-zA-Z0-9]+([\-_]+[a-zA-Z0-9]+)*)'
                  r'(\.([a-zA-Z0-9]+([\-_]+[a-zA-Z0-9]+)*))*$')

# The maximum length of a bucket name.
MAX_BUCKET_LEN = 222

# The minimum length of a bucket name.
MIN_BUCKET_LEN = 3

# Segment length of bucket name should not be longer than this.
MAX_BUCKET_SEGMENT_LEN = 63

# Mapreduce arguments on the number of shards to use.
MAPREDUCE_DEFAULT_SHARDS = 32
MAPREDUCE_MIN_SHARDS = 8
MAPREDUCE_MAX_SHARDS = 256

def get_pretty_bytes(bytes_num, significant_digits=0):
  """ Get a pretty print view of the given number of bytes.

  This will give a string like 'X MBytes'.

  Args:
    bytes_num: the original number of bytes to pretty print.
    significant_digits: number of digits to display after the decimal point.

  Returns:
    A string that has the pretty print version of the given bytes.
    If bytes_num is too big the string 'Oodles' will be returned.
  """
  byte_prefixes = ['', 'K', 'M', 'G', 'T', 'P', 'E']
  for i in range(0, 7):
    exp = i * 10
    if bytes_num < 1<<(exp + 10):
      if i == 0:
        formatted_bytes = str(bytes_num)
      else:
        formatted_bytes = '%.*f' % \
          (significant_digits, (bytes_num * 1.0 / (1<<exp)))
      if formatted_bytes != '1':
        plural = 's'
      else:
        plural = ''
      return '%s %sByte%s' % (formatted_bytes, byte_prefixes[i], plural)

  logging.error('Number too high to convert: %d', bytes_num)
  return 'Oodles'

def format_thousands(value):
  """ Format a numerical value, inserting commas as thousands separators.

  Args:
    value: An integer, float, or string representation thereof.
      If the argument is a float, it is converted to a string using '%.2f'.

  Returns:
    A string with groups of 3 digits before the decimal point (if any)
    separated by commas.

  NOTE: We don't deal with whitespace, and we don't insert
  commas into long strings of digits after the decimal point.
  """
  if isinstance(value, float):
    value = '%.2f' % value
  else:
    value = str(value)
  if '.' in value:
    head, tail = value.split('.', 1)
    tail = '.' + tail
  elif 'e' in value:
    head, tail = value.split('e', 1)
    tail = 'e' + tail
  else:
    head = value
    tail = ''
  sign = ''
  if head.startswith('-'):
    sign = '-'
    head = head[1:]
  while len(head) > 3:
    tail = ',' + head[-3:] + tail
    head = head[:-3]
  return sign + head + tail

def parse_gs_handle(gs_handle, mode):
  """ Splits [/gs/]?bucket_name[/folder]*[/file]? to
    (bucket_name, path | '').

  Args:
    gs_handle: The full GCS handle of the file.
    mode: "backup"/"restore" depending on the calling method.

  Returns:
    A str, the GCS bucket handle.

  Raises:
    BackupValidationException for unsupported filesystems during a backup.
    RestoreValidationException for unsupported filesystems during a restore.
  """
  if gs_handle.startswith('/'):
    filesystem = gs_handle[1:].split('/', 1)[0]
    if filesystem == 'gs':
      gs_handle = gs_handle[4:]
    else:
      if mode == 'backup':
        raise BackupValidationException('Unsupported filesystem: {0}'.format(
          filesystem))
      elif mode == 'restore':
        raise RestoreValidationException('Unsupported filesystem: {0}'.format(
          filesystem))
  tokens = gs_handle.split('/', 1)
  return (tokens[0], '') if len(tokens) == 1 else tuple(tokens)

def validate_gs_bucket_name(bucket_name):
  """ Validate the format of the given bucket_name.

  Validation rules are based:
  https://developers.google.com/storage/docs/bucketnaming#requirements

  Args:
    bucket_name: The bucket name to validate.

  Raises:
    BackupValidationException: If the bucket name is invalid.
  """
  if len(bucket_name) > MAX_BUCKET_LEN:
    raise BackupValidationException(
      'Bucket name length should not be longer than %d' % MAX_BUCKET_LEN)
  if len(bucket_name) < MIN_BUCKET_LEN:
    raise BackupValidationException(
      'Bucket name length should be longer than %d' % MIN_BUCKET_LEN)
  if bucket_name.lower().startswith('goog'):
    raise BackupValidationException(
      'Bucket name should not start with a "goog" prefix')
  bucket_elements = bucket_name.split('.')
  for bucket_element in bucket_elements:
    if len(bucket_element) > MAX_BUCKET_SEGMENT_LEN:
      raise BackupValidationException(
        'Segment length of bucket name should not be longer than %d' %
        MAX_BUCKET_SEGMENT_LEN)
  if not re.match(BUCKET_PATTERN, bucket_name):
    raise BackupValidationException('Invalid bucket name "%s"' % bucket_name)

def start_map(job_name,
              handler_spec,
              reader_spec,
              writer_spec,
              mapper_params,
              done_callback,
              mapreduce_params=None,
              queue_name=None,
              shard_count=MAPREDUCE_DEFAULT_SHARDS):
  """ Start map as part of datastore admin operation.

  Will increase number of active jobs inside the operation and start new map.

  Args:
    job_name: Map job name.
    handler_spec: Map handler specification.
    reader_spec: Input reader specification.
    writer_spec: Output writer specification.
    mapper_params: Custom mapper parameters.
    mapreduce_params: Custom mapreduce parameters.
    queue_name: the name of the queue that will be used by the M/R.
    shard_count: the number of shards the M/R will try to use.

  Returns:
    Resulting map job ID as string.
  """
  if not mapreduce_params:
    mapreduce_params = {}
  mapreduce_params['done_callback'] = done_callback
  if queue_name is not None:
    mapreduce_params['done_callback_queue'] = queue_name
  mapreduce_params['force_writes'] = 'True'
  job_id = control.start_map(
    job_name, handler_spec, reader_spec,
    mapper_params,
    output_writer_spec=writer_spec,
    mapreduce_parameters=mapreduce_params,
    shard_count=shard_count,
    queue_name=queue_name)
  return job_id
