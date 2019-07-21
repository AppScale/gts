#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#














"""Define file formats."""





__all__ = ['FileFormat',
           'FORMATS']

import StringIO
import zipfile


class FileFormat(object):
  """FileFormat can operate/iterate on files of a specific format.

  Life cycle of FileFormat:
    1. Two ways that FileFormat is created: file_format_root.split creates
       FileFormat from scratch. FileFormatRoot.from_json creates FileFormat
       from serialized json str. Either way, it is associated with a
       FileFormatRoot. It should never be instantiated directly.
    2. Root acts as a coordinator among FileFormats. Root initializes
       its many fields so that FileFormat knows how to iterate over its inputs.
    3. Its next() method is used to iterate.
    4. It keeps iterating until either root calls its to_json() or root
       sends it a StopIteration.

  How to define a new format:
    1. Subclass this.
    2. Override NAME and ARGUMENTS. file_format_parser._FileFormatParser
       uses them to validate a format string contains only legal
       names and arguments.
    3. Optionally override preprocess(). See method doc.
    4. Override get_next(). Used by next() to fetch the next content to
       return. See method.
    5. Optionally override split() if this format supports it. See method.
    6. Write unit tests. Tricky logics (to/from_json, advance
       current input file) are shared. Thus as long as you respected
       get_next()'s pre/post conditions, tests are very simple.
    7. Register your format at FORMATS.

  Attributes:
    ARGUMENTS: a set of acceptable arguments to this format. Used for parsing
        this format.
    NAME: the name of this format. Used for parsing this format.
  """

  ARGUMENTS = set()
  NAME = '_file'


  _KWARGS = 'kwargs'
  _RANGE = 'index_range'
  _FORMAT = 'name'
  _PREVIOUS_INDEX = 'previous_index'

  def __init__(self,
               index,
               index_range=None,
               **kwargs):

    """Initialize.

    Args:
      index: the index of the subfile to read from the current file.
      index_range: a tuple [start_index, end_index) that if defined, should
        bound index. When index is end_index, current file is consumed.
      kwargs: kwargs for a specific FileFormat. What arguments are accepted
        and their semantics depend on each subclass's interpretation.

    Raises:
      ValueError: if some argument is not expected by the format.
    """
    for k in kwargs:
      if k not in self.ARGUMENTS:
        raise ValueError('Illegal argument %s' % k)
    self._kwargs = kwargs

    self._index = index
    self._previous_index = index


    self._range = index_range
    self._input_files_stream = None

    self._cache = {}

  def get_current_file(self):
    """Get the current file to iterate upon.

    Returns:
      A Python file object. This file is already seeked to the position from
      last iteration. If read raises EOF, that means the file is exhausted.
    """
    return self._input_files_stream.current

  def get_index(self):
    """Get index.

    If the format is an archive format, get_index() tells the format which
    subfile from current file should it process. This value is maintained
    across pickles and resets to 0 when a new file starts.

    Returns:
      index of the subfile to process from current file.
    """
    return self._index

  def increment_index(self):
    """Increment index.

    Increment index value after finished processing the current subfile from
    current file.
    """
    self._index += 1

  def get_cache(self):
    """Get cache to store expensive objects.

    Some formats need expensive initialization to even start iteration.
    They can store the initialized objects into the cache and try to retrieve
    the objects from the cache at later iterations.

    For example, a zip format needs to create a ZipFile object to iterate over
    the zipfile. It can avoid doing so on every "next" call by storing the
    ZipFile into cache.

    Cache does not guarantee persistence. It is cleared at pickles.
    It is also intentionally cleared after the currently iterated file is
    entirely consumed.

    Returns:
      A dict to store temporary objects.
    """
    return self._cache

  @classmethod
  def default_instance(cls, **kwargs):

    """Create an default instance of FileFormat.

    Used by parser to create default instances.

    Args:
      kwargs: kwargs parser parsed from user input.

    Returns:
      A default instance of FileFormat.
    """
    return cls(0, **kwargs)

  def __repr__(self):
    return str(self.to_json())

  def __str__(self):
    result = self.NAME

    if self._kwargs:
      result += (
          '(' +
          ','.join(k + '=' + v for k, v in sorted(self._kwargs.iteritems())) +
          ')')
    return result

  def checkpoint(self):
    """Save _index before updating it to support potential rollback."""
    self._previous_index = self._index

  def to_json(self):
    """Serialize states to a json compatible structure."""
    return {self._KWARGS: self._kwargs,
            self._RANGE: self._range,
            self._FORMAT: self.NAME,
            self._PREVIOUS_INDEX: self._previous_index}

  @classmethod
  def from_json(cls, json):
    """Deserialize from json compatible structure."""
    return cls(json[cls._PREVIOUS_INDEX], json[cls._RANGE], **json[cls._KWARGS])

  @classmethod
  def can_split(cls):
    """Indicates whether this format support splitting within a file boundary.

    Returns:
      True if a FileFormat allows its inputs to be splitted into
    different shards.
    """
    try:
      cls.split(0, 0, None, {})
    except NotImplementedError:
      return False
    return True

  @classmethod

  def split(cls, desired_size, start_index, input_file, cache):
    """Splits a single chunk of desired_size from file.

    FileFormatRoot uses this method to ask FileFormat how to split
    one file of this format.

    This method takes an opened file and a start_index. If file
    size is bigger than desired_size, the method determines a chunk of the
    file whose size is close to desired_size. The chuck is indicated by
    [start_index, end_index). If the file is smaller than desired_size,
    the chunk will include the rest of the input_file.

    This method also indicates how many bytes are consumed by this chunk
    by returning size_left to the caller.

    Args:
      desired_size: desired number of bytes for this split. Positive int.
      start_index: the index to start this split. The index is not necessarily
        an offset. In zipfile, for example, it's the index of the member file
        in the archive. Non negative int.
      input_file: opened Files API file to split. Do not close this file.
      cache: a dict to cache any object over multiple calls if needed.

    Returns:
      Returns a tuple of (size_left, end_index). If end_index equals
      start_index, the file is fully split.
    """
    raise NotImplementedError('split is not implemented for %s.' %
                              cls.__name__)

  def __iter__(self):
    return self

  def preprocess(self, file_object):
    """Does preprocessing on the file-like object and returns another one.

    Normally a FileFormat directly reads from the file returned by
    get_current_file(). But some formats need to preprocess that file entirely
    before iteration can starts (e.g. text formats need to decode first).

    Args:
      file_object: read from this object and process its content.

    Returns:
      a file-like object containing processed contents. This file object will
      be returned by get_current_file() instead. If the returned object
      is newly created, close the old one.
    """
    return file_object

  def next(self):
    """Returns a file-like object containing next content.

    Returns:
      A file-like object containing next content.

    Raises:
      ValueError: if content is of none str type.
    """
    result = None
    try:

      if self._range is not None:
        if self._index < self._range[0]:
          self._index = self._range[0]
        elif self._index >= self._range[1]:
          raise EOFError()

      self._input_files_stream.checkpoint()
      self.checkpoint()
      result = self.get_next()
    except EOFError:
      self._input_files_stream.advance()
      self._index = 0
      self._cache = {}
      return self.next()
    if isinstance(result, str):
      result = StringIO.StringIO(result)
    elif isinstance(result, unicode):
      raise ValueError('%s can not return unicode object.' %
                       self.__class__.__name__)
    return result

  def get_next(self):
    """Finds the next content to return.

    Expected steps of any implementation:
      1. Call get_current_file() to get the file to iterate on.
      2. If nothing is read, raise EOFError. Otherwise, process the
         contents read in anyway. _kwargs is guaranteed to be a dict
         containing all arguments and values specified by user.
      3. If the format is an archive format, use get_index() to
         see which subfile to read. Call increment_index() if
         finished current subfile. These two methods will make sure
         the index is maintained during (de)serialization.
      4. Return the processed contents either as a file-like object or
         Python str. NO UNICODE.

    Returns:
      The str or file like object if got anything to return.

    Raises:
      EOFError if no content is found to return.
    """
    raise NotImplementedError('%s not implemented.' % self.__class__.__name__)



class _BinaryFormat(FileFormat):
  """Base class for any binary formats.

  This class just reads the entire file as raw str. All subclasses
  should simply override NAME. That NAME will be passed to Python
  to decode the bytes so NAME has to be a valid encoding.
  """

  NAME = 'bytes'

  def get_next(self):
    """Inherited."""
    result = self.get_current_file().read()
    if not result:
      raise EOFError()
    if self.NAME != _BinaryFormat.NAME:
      return result.decode(self.NAME)
    return result


class _Base64Format(_BinaryFormat):
  """Read entire file as base64 str."""

  NAME = 'base64'



class _ZipFormat(FileFormat):
  """Read member files of zipfile."""

  NAME = 'zip'

  DEFAULT_INDEX_VALUE = 0

  def get_next(self):
    """Inherited."""
    cache = self.get_cache()
    if 'zip_file' in cache:
      zip_file = cache['zip_file']
      infolist = cache['infolist']
    else:
      zip_file = zipfile.ZipFile(self._input_files_stream.current)
      infolist = zip_file.infolist()
      cache['zip_file'] = zip_file
      cache['infolist'] = infolist

    if self.get_index() == len(infolist):
      raise EOFError()

    result = zip_file.read(infolist[self.get_index()])
    self.increment_index()
    return result

  @classmethod
  def can_split(cls):
    """Inherited."""
    return True

  @classmethod
  def split(cls, desired_size, start_index, opened_file, cache):
    """Inherited."""
    if 'infolist' in cache:
      infolist = cache['infolist']
    else:
      zip_file = zipfile.ZipFile(opened_file)
      infolist = zip_file.infolist()
      cache['infolist'] = infolist

    index = start_index
    while desired_size > 0 and index < len(infolist):
      desired_size -= infolist[index].file_size
      index += 1
    return desired_size, index



class _TextFormat(FileFormat):
  """Base class for any text format.

  Text formats are those that require decoding before iteration.
  This class takes care of the preprocessing logic of decoding.
  """

  ARGUMENTS = set(['encoding'])
  NAME = '_text'

  def preprocess(self, file_object):
    """Decodes the entire file to read text."""
    if 'encoding' in self._kwargs:
      content = file_object.read()
      content = content.decode(self._kwargs['encoding'])
      file_object.close()
      return StringIO.StringIO(content)
    return file_object


class _LinesFormat(_TextFormat):
  """Read file line by line."""

  NAME = 'lines'

  def get_next(self):
    """Inherited."""
    result = self.get_current_file().readline()
    if not result:
      raise EOFError()
    if 'encoding' in self._kwargs:
      result = result.encode(self._kwargs['encoding'])
    return result


class _CSVFormat(_TextFormat):
  ARGUMENTS = _TextFormat.ARGUMENTS.union(['delimiter'])
  NAME = 'csv'



FORMATS = {

    'base64': _Base64Format,
    'bytes': _BinaryFormat,

    'csv': _CSVFormat,
    'lines': _LinesFormat,

    'zip': _ZipFormat}
