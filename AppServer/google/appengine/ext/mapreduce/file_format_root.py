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














"""Define file format root."""

from __future__ import with_statement



__all__ = ['FileFormatRoot',
           'split']

import copy
import google.appengine.ext.mapreduce.file_format_parser as parser

from google.appengine.api.files import file as files
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import file_formats


def split(filenames, format_string, shards):
  """Get a FileFormatRoot for each shard.

  This method creates a list of FileFormatRoot and assigns each root
  some input files. The number of roots is less than or equal to shards.

  Args:
    filenames: input filenames
    format_string: format string from user.
    shards: number of shards to split inputs.

  Returns:
    A list of FileFormatRoot or None if all input files have zero bytes.
  """
  parsed_formats = parser.parse(format_string)

  sizes = [files.stat(filename).st_size for filename in filenames]

  size_per_shard = float(sum(sizes)) / shards
  if not size_per_shard:
    return

  if parsed_formats[0].can_split():
    return _deep_split(filenames, size_per_shard, parsed_formats)
  else:
    return _shallow_split(filenames, size_per_shard, parsed_formats, sizes)


def _shallow_split(filenames, size_per_shard, parsed_formats, sizes):
  """Split files into roots only based on top level file sizes.

  This split does not cross file boundary.
  """
  roots = []
  inputs = []
  shard_size = 0
  for i, size in enumerate(sizes):
    shard_size += size
    inputs.append(_FileRange(filenames[i], None))
    if shard_size >= size_per_shard:
      roots.append(FileFormatRoot(copy.deepcopy(parsed_formats), inputs))
      inputs = []
      shard_size = 0

  if inputs:
    roots.append(FileFormatRoot(copy.deepcopy(parsed_formats), inputs))

  return roots


def _deep_split(filenames, size_per_shard, parsed_formats):
  """Split files into roots using the first FileFormat.

  Deep split can split within a file. It tells the first format how big
  a split it wants and the first format will do the actually splitting
  because only the first format knows how to operate on this particular
  format.

  Args:
    filenames: a list of input filenames.
    size_per_shard: size per shard.
    parsed_format: the parsed FileFormats.

  Returns:
    A list of FileFormatRoot.
  """
  roots = []
  inputs = []
  size_left = size_per_shard

  for filename in filenames:
    index = 0
    with files.open(filename) as f:
      cache_for_split = {}

      while True:
        if size_left <= 0:

          roots.append(FileFormatRoot(copy.deepcopy(parsed_formats), inputs))
          size_left = size_per_shard
          inputs = []
        start_index = index
        size_left, index = parsed_formats[0].split(size_left,
                                                   start_index,
                                                   f,
                                                   cache_for_split)

        if start_index == index:
          break
        inputs.append(_FileRange(filename, (start_index, index)))

  if inputs:
    roots.append(FileFormatRoot(copy.deepcopy(parsed_formats), inputs))

  return roots


class _FileRange(model.JsonMixin):
  """Describe a range of a file to read.

  FileFormatRootFactory creates instances of this class and
  feeds them to different roots.
  """


  FILENAME = 'filename'
  RANGE = 'range'

  def __init__(self, filename, file_range=None):
    """Init.

    Args:
      filename: filename in str.
      file_range: [start_index, end_index) tuple. This only makes sense for
        _FileFormats that support splitting within a file.
        It specify the range to read this file.
        None means reading the entire file. When defined, what it means
        differ for each format. For example, if a file is of zip format,
        index specifies the member files to read. If a file is of record
        format, index specifies the records to read.
    """
    self.filename = filename
    self.range = file_range

  def to_json(self):
    return {self.FILENAME: self.filename,
            self.RANGE: self.range}

  @classmethod
  def from_json(cls, json):
    return cls(json[cls.FILENAME], json[cls.RANGE])


class FileFormatRoot(model.JsonMixin):
  """FileFormatRoot.

  FileFormatRoot takes a list of FileFormats as processing units and
  a list of _FileRanges as inputs. It provides an interface to
  iterate through all the inputs. All inputs will be processed by each
  processing unit in a cascaded manner before being emitted.

  The order of the list of FileFormats matters. The last
  FileFormat's output is returned by FileFormatRoot.
  Each FileFormat asks FileFormatRoot for inputs, which are either outputs
  from its previous FileFormat or, in the case of the first FileFormat,
  outputs directly from FileFormatRoot.

  FileFormats don't know each other. FileFormatRoot coordinates all
  their initializations, (de)serialization, and communications.
  """


  _INPUTS = 'inputs'
  _FORMATS = 'formats'
  _FILES_STREAMS = 'files_streams'

  def __init__(self, formats, inputs, files_streams_json=None):
    """Init.

    Args:
      formats: A list of _FileFormats.
      inputs: A list of _FileRanges.
      init_files_streams: If to initialize files streams to default value.
    """
    self._inputs = inputs
    self._formats = formats
    for i, file_format in enumerate(self._formats):
      stream_cls = _RootFilesStream if i == 0 else _FilesStream
      if files_streams_json:
        file_format._input_files_stream = stream_cls.from_json(
            files_streams_json[i], self)
      else:
        file_format._input_files_stream = stream_cls(i, self)

  def __repr__(self):
    return str(self.to_json())

  def __iter__(self):
    return self

  def to_json(self):
    return  {self._INPUTS: [_.to_json() for _ in self._inputs],
             self._FORMATS: [_.to_json() for _ in self._formats],
             self._FILES_STREAMS:
             [_._input_files_stream.to_json() for _ in self._formats]}

  @classmethod
  def from_json(cls, json):
    formats = [file_formats.FORMATS[_json[file_formats.FileFormat._FORMAT]].
        from_json(_json) for _json in json[cls._FORMATS]]

    root = cls(formats,
               [_FileRange.from_json(_) for _ in json[cls._INPUTS]],
               json[cls._FILES_STREAMS])

    return root

  def next(self):
    """Iterate over inputs."""
    result = self._formats[-1].next()
    self._formats[-1]._input_files_stream.checkpoint()
    self._formats[-1].checkpoint()
    return result


class _FilesStream(object):
  """Provide FileFormat with a stream of file-like objects as inputs.

  Attributes:
    current: the current file-like object to read from.
  """


  PREVIOUS_OFFSET = 'previous'
  INDEX = 'index'

  def __init__(self,
               index,
               file_format_root,
               offset=0,
               next_func=None):
    """Init.

    Args:
      file_format_root: the FileFormatRoot this stream should talk to.
      index: the index of this stream within the FileFormatRoot.
      offset: the offset to start reading current file.
      next_func: a function that gives back the next file from the stream.
    """
    self._next_file = next_func or file_format_root._formats[index-1].next
    self._preprocess = file_format_root._formats[index].preprocess

    self._previous_offset = offset
    self._index = index
    self._current = self._preprocess(self._next_file())
    self._current.seek(offset)

  def advance(self):
    """Advance _current to the next file-like object.

    _FileStream should call this after consumed the current file-like object.
    """
    self._previous_offset = 0
    self._current.close()
    self._current = self._preprocess(self._next_file())

  @property
  def current(self):
    return self._current

  def checkpoint(self):
    self._previous_offset = self._current.tell()

  def to_json(self):
    return {self.PREVIOUS_OFFSET: self._previous_offset,
            self.INDEX: self._index}

  @classmethod
  def from_json(cls, json, file_format_root):
    return cls(json[cls.INDEX], file_format_root, json[cls.PREVIOUS_OFFSET])


class _RootFilesStream(_FilesStream):
  """Special FilesStream for the first FileFormat"""

  PREVIOUS_INPUT_INDEX = 'input_index'

  def __init__(self,
               index,
               file_format_root,
               offset=0,
               input_index=0):
    """Init.

    Args:
      index: the index of this stream within the FileFormatRoot.
      file_format_root: the FileFormatRoot this stream should talk to.
      offset: the offset to start reading current file.
      input_index: index of the next input file to read.
    """
    self.__inputs = file_format_root._inputs
    self.__input_index = input_index
    self.__previous_input_index = input_index
    self.__file_format_root = file_format_root

    super(_RootFilesStream, self).__init__(index,
                                           file_format_root,
                                           offset,
                                           self.next_file)

  def next_file(self):
    if self.__input_index == len(self.__inputs):
      raise StopIteration()
    file_input = self.__inputs[self.__input_index]
    if file_input.range:
      first_format = self.__file_format_root._formats[0]
      if not first_format.can_split():
        raise ValueError('Input range specified for a non splitable format %s'
                         % first_format.NAME)
      first_format._range = file_input.range
    self.__previous_input_index = self.__input_index
    self.__input_index += 1
    return files.open(file_input.filename, 'r', buffering=-1)

  def to_json(self):
    result = super(_RootFilesStream, self).to_json()
    result[self.PREVIOUS_INPUT_INDEX] = self.__previous_input_index
    return result

  @classmethod
  def from_json(cls, json, file_format_root):
    return cls(json[cls.INDEX],
               file_format_root,
               json[cls.PREVIOUS_OFFSET],
               json[cls.PREVIOUS_INPUT_INDEX])
