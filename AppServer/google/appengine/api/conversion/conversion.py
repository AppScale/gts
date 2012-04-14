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




"""Conversion API providing document conversion service for applications."""










from google.appengine.api import apiproxy_stub_map
from google.appengine.api.conversion import conversion_service_pb
from google.appengine.runtime import apiproxy_errors





CONVERSION_MAX_NUM_PER_REQUEST = 10




CONVERSION_MAX_SIZE_BYTES = 2 * (2 ** 20)

_CONVERSION_SERVICE = "conversion"

_CONVERT_METHOD = "Convert"

_IMAGE_WIDTH_FLAG = "imageWidth"

_FIRST_PAGE_FLAG = "firstPage"

_LAST_PAGE_FLAG = "lastPage"



_LAST_PAGE_DEFAULT = -1

_OCR_INPUT_LANGUAGE_FLAG = "input_language_hint"


class Error(Exception):
  """Base-class for exceptions in this module."""


class BackendDeadlineExceeded(Error):
  """Communication to backend service timed-out."""


class TransientError(Error):
  """Transient error while accessing the backend, please try again later."""


class BackendError(Error):
  """Something wrong in the backend that can't be sent back to application."""


class ConversionUnsupported(Error):
  """Unsupported conversion attempted."""


class ConversionTooLarge(Error):
  """The conversion is too large."""


class TooManyConversions(Error):
  """Too many conversions in the request."""


class InvalidRequest(Error):
  """The request was not formed properly."""


def _to_conversion_error(error):
  """Translate an application error to a conversion Error, if possible.

  Args:
    error: An ApplicationError to translate.

  Returns:
    error: ConversionApi specific error message.
  """
  error_map = {
      conversion_service_pb.ConversionServiceError.TIMEOUT:
      BackendDeadlineExceeded,
      conversion_service_pb.ConversionServiceError.TRANSIENT_ERROR:
      TransientError,
      conversion_service_pb.ConversionServiceError.INTERNAL_ERROR:
      BackendError,
      conversion_service_pb.ConversionServiceError.UNSUPPORTED_CONVERSION:
      ConversionUnsupported,
      conversion_service_pb.ConversionServiceError.CONVERSION_TOO_LARGE:
      ConversionTooLarge,
      conversion_service_pb.ConversionServiceError.TOO_MANY_CONVERSIONS:
      TooManyConversions,
      conversion_service_pb.ConversionServiceError.INVALID_REQUEST:
      InvalidRequest,
      }
  if error.application_error in error_map:
    return error_map[error.application_error](error.error_detail)
  else:
    return error


def _to_error_text(error_code):
  """Translate an error code to an error message, if possible.

  Args:
    error_code: An conversion_service_pb.ConversionServiceError error code.

  Returns:
    Human readable error message.
  """
  error_map = {
      conversion_service_pb.ConversionServiceError.TIMEOUT:
      "BackendDeadlineExceeded",
      conversion_service_pb.ConversionServiceError.TRANSIENT_ERROR:
      "TransientError",
      conversion_service_pb.ConversionServiceError.INTERNAL_ERROR:
      "BackendError",
      conversion_service_pb.ConversionServiceError.UNSUPPORTED_CONVERSION:
      "ConversionUnsupported",
      conversion_service_pb.ConversionServiceError.CONVERSION_TOO_LARGE:
      "ConversionTooLarge",
      conversion_service_pb.ConversionServiceError.TOO_MANY_CONVERSIONS:
      "TooManyConversions",
      conversion_service_pb.ConversionServiceError.INVALID_REQUEST:
      "InvalidRequest",
      }
  if error_code in error_map:
    return error_map[error_code]
  else:
    return "UnknownError"


class Asset(object):
  """Represents a single asset in the request.

  An asset is a generic blob of data. A conversion document must contain
  at least one asset, typically the document contents. Additional assets
  are those needed for the conversion, for example images in HTML.
  """

  def __init__(self, mime_type, data, name=None):
    """Constructor.

    Args:
      mime_type: mime type of the asset (string).
      data: data to be converted (string).
      name: name of the asset (string).

    Raises:
      TypeError: if input arguments are not string.
    """
    if not isinstance(mime_type, basestring):
      raise TypeError("mime type %r is not a string" % (mime_type,))
    self._mime_type = mime_type.lower()

    if not isinstance(data, basestring):
      raise TypeError("data %r is not a string" % (data,))
    self._data = data

    if name is not None:
      if not isinstance(name, basestring):
        raise TypeError("name %r is not a string" % (name,))
    self._name = name

  @property
  def mime_type(self):
    """The mime type of the asset (string)."""
    return self._mime_type

  @property
  def data(self):
    """The data of the asset (string)."""
    return self._data

  @property
  def name(self):
    """The name of the asset (string)."""
    return self._name

  def _populate_proto(self, asset_info_pb):
    """Populate an AssetInfo protocol buffer with Asset properties.

    Args:
      asset_info_pb: An AssetInfo protocol buffer.
    """
    asset_info_pb.set_mime_type(self._mime_type)
    asset_info_pb.set_data(self._data)
    if self._name is not None:
      asset_info_pb.set_name(self._name)


class Conversion(object):
  """Represents a single conversion from one file format to another.

  A conversion must contain at least one asset, typically the document contents.
  Additional assets are those needed for the conversion, for example images in
  HTML.
  """

  def __init__(self,
               asset,
               output_mime_type,

               image_width=800,
               first_page=1,
               last_page=None,
               ocr_input_language=None):
    """Create a single conversion.

    Args:
      asset: An Asset instance.
      output_mime_type: The output data mime type (string), put into the
        output_mime_type field.
      image_width: The output image width in pixels. Only applies to
        conversions that generate image files.
      first_page: The number of the first page to generate. Only applies to
        conversions that generate image files.
      last_page: The number of the last page to generate, defaults to the last
        page of the document. Only applies to conversions that generate image
        files.
      ocr_input_language: The language code in BCP 47 format, used by OCR engine
        to search for language-specific character set.

    Raises:
      TypeError: if an unexpected type is used for any of the arguments.
      ValueError: if an unexpected value is used for any of the arguments.
    """
    self._assets = []

    if not asset.mime_type:
      raise ValueError("Asset mime type should not be empty")
    self.add_asset(asset)

    Conversion._ensure_nonempty_string(
        "output_mime_type", output_mime_type)
    self._output_mime_type = output_mime_type.lower()

    self._image_width = Conversion._ensure_positive_integer(
        "image_width", image_width)
    self._first_page = Conversion._ensure_positive_integer(
        "first_page", first_page)
    self._last_page = None
    if last_page is not None:
      self._last_page = Conversion._ensure_positive_integer(
          "last_page", last_page)

    self._ocr_input_language = None
    if ocr_input_language is not None:
      Conversion._ensure_nonempty_string(
          "ocr_input_language", ocr_input_language)
      self._ocr_input_language = ocr_input_language.lower()

  @staticmethod
  def _ensure_nonempty_string(argname, argvalue):
    """Ensure the input argument is a non-empty string.

    Args:
      argname: The name of argument to check.
      argvalue: The value of argument to check.

    Raises:
      TypeError: if an unexpected type is used for the argument.
      ValueError: if an unexpected value is used for the argument.
    """
    if not isinstance(argvalue, basestring):
      raise TypeError("%s(%r) is not a string" % (argname, argvalue))
    if not argvalue:
      raise ValueError("%s(%r) must not be empty" % (argname, argvalue))

  @staticmethod
  def _ensure_positive_integer(argname, argvalue):
    """Ensure the input argument is a positive integer.

    Args:
      argname: The name of argument to check.
      argvalue: The value of argument to check.

    Returns:
      The input argument value.

    Raises:
      TypeError: if an unexpected type is used for the argument.
      ValueError: if an unexpected value is used for the argument.
    """
    if not isinstance(argvalue, (int, long)):
      raise TypeError("%s(%r) is not integer or long" % (argname, argvalue))
    if argvalue <= 0:
      raise ValueError("%s(%r) must be larger than 0" % (argname, argvalue))

    return argvalue

  def add_asset(self, asset):
    """Add an asset into the conversion request.

    Args:
      asset: An Asset instance.

    Raises:
      TypeError: if the asset is not an Asset instance.
    """
    if not isinstance(asset, Asset):
      raise TypeError("Input %r is not an Asset instance" % asset)

    self._assets.append(asset)

  def _populate_proto(self, conversion_input_pb):
    """Populate a ConversionInput protocol buffer with Conversion instance.

    Args:
      conversion_input_pb: A ConversionInput protocol buffer.
    """
    for asset in self._assets:
      asset_pb = conversion_input_pb.mutable_input().add_asset()
      asset._populate_proto(asset_pb)

    conversion_input_pb.set_output_mime_type(self._output_mime_type)

    self._populate_flags(conversion_input_pb)

  def _populate_flags(self, conversion_input_pb):
    """Populate a ConversionInput protocol buffer with auxiliary parameters.

    Args:
      conversion_input_pb: A ConversionInput protocol buffer.
    """
    image_width_flag = conversion_input_pb.add_flag()
    image_width_flag.set_key(_IMAGE_WIDTH_FLAG)
    image_width_flag.set_value(str(self._image_width))

    first_page_flag = conversion_input_pb.add_flag()
    first_page_flag.set_key(_FIRST_PAGE_FLAG)
    first_page_flag.set_value(str(self._first_page))

    last_page_flag = conversion_input_pb.add_flag()
    last_page_flag.set_key(_LAST_PAGE_FLAG)
    if self._last_page is not None:
      last_page_flag.set_value(str(self._last_page))
    else:

      last_page_flag.set_value(str(_LAST_PAGE_DEFAULT))

    if self._ocr_input_language is not None:
      ocr_input_language_flag = conversion_input_pb.add_flag()
      ocr_input_language_flag.set_key(_OCR_INPUT_LANGUAGE_FLAG)
      ocr_input_language_flag.set_value(self._ocr_input_language)


class ConversionOutput(object):
  """Represents a single conversion output from the response.

  A conversion output includes the error code and a list of converted assets.
  """

  def __init__(self, conversion_output_proto):
    """Constructor.

    Args:
      conversion_output_proto: the ConversionOutput protocol buffer.

    Raises:
      AssertionError: if asset_info_proto is not an AssetInfo protocol buffer.
    """
    assert isinstance(conversion_output_proto,
                      conversion_service_pb.ConversionOutput)

    self._error_code = conversion_output_proto.error_code()
    self._error_text = "OK"
    if self._error_code != conversion_service_pb.ConversionServiceError.OK:
      self._error_text = _to_error_text(self._error_code)
    self._assets = []
    for asset_pb in conversion_output_proto.output().asset_list():
      self._assets.append(Asset(
          asset_pb.mime_type(), asset_pb.data(), asset_pb.name()))

  @property
  def error_code(self):
    """The error code of this conversion."""
    return self._error_code

  @property
  def error_text(self):
    """The error message of this conversion if not successful."""
    return self._error_text

  @property
  def assets(self):
    """A list of converted assets in the format of Asset instances."""
    return self._assets


def convert(conversion, deadline=None):
  """Makes all conversions in parallel, blocking until all results are returned.

  Args:
    conversion: A Conversion instance or a list of Conversion instances.
    deadline: Optional deadline in seconds for all the conversions.

  Returns:
    A ConverionOutput instance if conversion is a Conversion instance. Or a list
    of ConversionOutput instances, one per Conversion in the same order.

  Raises:
    TypeError: Input conversions with wrong type.
    See more details in _to_conversion_error function.
  """
  rpc = create_rpc(deadline=deadline)
  make_convert_call(rpc, conversion)
  return rpc.get_result()


def create_rpc(deadline=None, callback=None):
  """Creates an RPC object for use with the Conversion API.

  Args:
    deadline: Optional deadline in seconds for the operation; the default is
      a system-specific deadline (typically 5 seconds).
    callback: Optional callable to invoke on completion.

  Returns:
    An apiproxy_stub_map.UserRPC object specialized for this service.
  """
  return apiproxy_stub_map.UserRPC(_CONVERSION_SERVICE, deadline, callback)


def make_convert_call(rpc, conversion):
  """Executes the RPC call to do the conversions.

  The result can then be got from rpc.get_result which will call
  _get_convert_result. See the docstring there for more details.

  Args:
    rpc: a UserRPC instance.
    conversion: A Conversion instance or a list of Conversion instances.

  Raises:
    TypeError: Input conversions with wrong type.
    See more details in _to_conversion_error function.
  """
  request = conversion_service_pb.ConversionRequest()
  response = conversion_service_pb.ConversionResponse()

  try:
    conversions = list(iter(conversion))
  except TypeError:
    conversions = [conversion]
    multiple = False
  else:
    multiple = True

  for conversion in conversions:
    if isinstance(conversion, Conversion):
      conversion_input_pb = request.add_conversion()

      conversion._populate_proto(conversion_input_pb)
    else:
      raise TypeError("conversion must be a Conversion instance "
                      "or a list of Conversion instances")

  rpc.make_call(_CONVERT_METHOD, request, response,
                _get_convert_result, user_data=multiple)


def _get_convert_result(rpc):
  """Check success, handle exceptions, and return conversion results.

  Args:
    rpc: A UserRPC instance.

  Returns:
    A ConverionOutput instance if conversion is a Conversion instance. Or a list
    of ConversionOutput instances, one per Conversion in the same order.

  Raises:
    See more details in _to_conversion_error function.
  """
  assert rpc.service == _CONVERSION_SERVICE, repr(rpc.service)
  assert rpc.method == _CONVERT_METHOD, repr(rpc.method)
  try:
    rpc.check_success()
  except apiproxy_errors.ApplicationError, e:
    raise _to_conversion_error(e)

  results = []
  for output_pb in rpc.response.result_list():
    results.append(ConversionOutput(output_pb))

  multiple = rpc.user_data
  if multiple:
    return results
  else:
    assert len(results) == 1
    return results[0]
