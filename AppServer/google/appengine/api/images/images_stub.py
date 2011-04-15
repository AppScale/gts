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




"""Stub version of the images API."""







import logging
import StringIO

try:
  import PIL
  from PIL import _imaging
  from PIL import Image
except ImportError:
  import _imaging
  import Image

from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import blobstore
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import images
from google.appengine.api.images import images_service_pb
from google.appengine.runtime import apiproxy_errors


MAX_REQUEST_SIZE = 32 << 20


def _ArgbToRgbaTuple(argb):
  """Convert from a single ARGB value to a tuple containing RGBA.

  Args:
    argb: Signed 32 bit integer containing an ARGB value.

  Returns:
    RGBA tuple.
  """

  unsigned_argb = argb % 0x100000000
  return ((unsigned_argb >> 16) & 0xFF,
          (unsigned_argb >> 8) & 0xFF,
          unsigned_argb & 0xFF,
          (unsigned_argb >> 24) & 0xFF)


def _BackendPremultiplication(color):
  """Apply premultiplication and unpremultiplication to match production.

  Args:
    color: color tuple as returned by _ArgbToRgbaTuple.

  Returns:
    RGBA tuple.
  """




  alpha = color[3]
  rgb = color[0:3]
  multiplied = [(x * (alpha + 1)) >> 8 for x in rgb]
  if alpha:
    alpha_inverse = 0xffffff / alpha
    unmultiplied = [(x * alpha_inverse) >> 16 for x in multiplied]
  else:
    unmultiplied = [0] * 3

  return tuple(unmultiplied + [alpha])


class ImagesServiceStub(apiproxy_stub.APIProxyStub):
  """Stub version of images API to be used with the dev_appserver."""

  def __init__(self, service_name="images", host_prefix=""):
    """Preloads PIL to load all modules in the unhardened environment.

    Args:
      service_name: Service name expected for all calls.
      host_prefix: the URL prefix (protocol://host:port) to preprend to
        image urls on a call to GetUrlBase.
    """
    super(ImagesServiceStub, self).__init__(service_name,
                                            max_request_size=MAX_REQUEST_SIZE)
    self._host_prefix = host_prefix
    Image.init()

  def _Dynamic_Composite(self, request, response):
    """Implementation of ImagesService::Composite.

    Based off documentation of the PIL library at
    http://www.pythonware.com/library/pil/handbook/index.htm

    Args:
      request: ImagesCompositeRequest, contains image request info.
      response: ImagesCompositeResponse, contains transformed image.
    """
    width = request.canvas().width()
    height = request.canvas().height()
    color = _ArgbToRgbaTuple(request.canvas().color())


    color = _BackendPremultiplication(color)
    canvas = Image.new("RGBA", (width, height), color)
    sources = []
    if (not request.canvas().width() or request.canvas().width() > 4000 or
        not request.canvas().height() or request.canvas().height() > 4000):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    if not request.image_size():
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    if not request.options_size():
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    if request.options_size() > images.MAX_COMPOSITES_PER_REQUEST:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    for image in request.image_list():
      sources.append(self._OpenImageData(image))

    for options in request.options_list():
      if (options.anchor() < images.TOP_LEFT or
          options.anchor() > images.BOTTOM_RIGHT):
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
      if options.source_index() >= len(sources) or options.source_index() < 0:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
      if options.opacity() < 0 or options.opacity() > 1:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
      source = sources[options.source_index()]
      x_anchor = (options.anchor() % 3) * 0.5
      y_anchor = (options.anchor() / 3) * 0.5
      x_offset = int(options.x_offset() + x_anchor * (width - source.size[0]))
      y_offset = int(options.y_offset() + y_anchor * (height - source.size[1]))
      alpha = options.opacity() * 255
      mask = Image.new("L", source.size, alpha)
      canvas.paste(source, (x_offset, y_offset), mask)
    response_value = self._EncodeImage(canvas, request.canvas().output())
    response.mutable_image().set_content(response_value)

  def _Dynamic_Histogram(self, request, response):
    """Trivial implementation of ImagesService::Histogram.

    Based off documentation of the PIL library at
    http://www.pythonware.com/library/pil/handbook/index.htm

    Args:
      request: ImagesHistogramRequest, contains the image.
      response: ImagesHistogramResponse, contains histogram of the image.
    """
    image = self._OpenImageData(request.image())

    img_format = image.format
    if img_format not in ("BMP", "GIF", "ICO", "JPEG", "PNG", "TIFF"):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.NOT_IMAGE)
    image = image.convert("RGBA")
    red = [0] * 256
    green = [0] * 256
    blue = [0] * 256




    for pixel in image.getdata():
      red[int((pixel[0] * pixel[3]) / 255)] += 1
      green[int((pixel[1] * pixel[3]) / 255)] += 1
      blue[int((pixel[2] * pixel[3]) / 255)] += 1
    histogram = response.mutable_histogram()
    for value in red:
      histogram.add_red(value)
    for value in green:
      histogram.add_green(value)
    for value in blue:
      histogram.add_blue(value)

  def _Dynamic_Transform(self, request, response):
    """Trivial implementation of ImagesService::Transform.

    Based off documentation of the PIL library at
    http://www.pythonware.com/library/pil/handbook/index.htm

    Args:
      request: ImagesTransformRequest, contains image request info.
      response: ImagesTransformResponse, contains transformed image.
    """
    original_image = self._OpenImageData(request.image())

    new_image = self._ProcessTransforms(original_image,
                                        request.transform_list())

    response_value = self._EncodeImage(new_image, request.output())
    response.mutable_image().set_content(response_value)

  def _Dynamic_GetUrlBase(self, request, response):
    """Trivial implementation of ImagesService::GetUrlBase.

    Args:
      request: ImagesGetUrlBaseRequest, contains a blobkey to an image
      response: ImagesGetUrlBaseResponse, contains a url to serve the image
    """
    response.set_url("%s/_ah/img/%s" % (self._host_prefix, request.blob_key()))

  def _EncodeImage(self, image, output_encoding):
    """Encode the given image and return it in string form.

    Args:
      image: PIL Image object, image to encode.
      output_encoding: ImagesTransformRequest.OutputSettings object.

    Returns:
      str with encoded image information in given encoding format.
    """
    image_string = StringIO.StringIO()

    image_encoding = "PNG"

    if (output_encoding.mime_type() == images_service_pb.OutputSettings.JPEG):
      image_encoding = "JPEG"






      image = image.convert("RGB")

    image.save(image_string, image_encoding)

    return image_string.getvalue()

  def _OpenImageData(self, image_data):
    """Open image data from ImageData protocol buffer.

    Args:
      image_data: ImageData protocol buffer containing image data or blob
        reference.

    Returns:
      Image containing the image data passed in or reference by blob-key.

    Raises:
      ApplicationError if both content and blob-key are provided.
      NOTE: 'content' must always be set because it is a required field,
      however, it must be the empty string when a blob-key is provided.
    """
    if image_data.content() and image_data.has_blob_key():
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.INVALID_BLOB_KEY)

    if image_data.has_blob_key():
      image = self._OpenBlob(image_data.blob_key())
    else:
      image = self._OpenImage(image_data.content())


    img_format = image.format
    if img_format not in ("BMP", "GIF", "ICO", "JPEG", "PNG", "TIFF"):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.NOT_IMAGE)
    return image

  def _OpenImage(self, image):
    """Opens an image provided as a string.

    Args:
      image: image data to be opened

    Raises:
      apiproxy_errors.ApplicationError if the image cannot be opened or if it
      is an unsupported format.

    Returns:
      Image containing the image data passed in.
    """
    if not image:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.NOT_IMAGE)

    image = StringIO.StringIO(image)
    try:
      return Image.open(image)
    except IOError:

      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_IMAGE_DATA)

  def _OpenBlob(self, blob_key):
    key = datastore_types.Key.from_path(blobstore.BLOB_INFO_KIND,
                                        blob_key,
                                        namespace='')
    try:
      datastore.Get(key)
    except datastore_errors.Error:


      logging.exception('Blob with key %r does not exist', blob_key)
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.UNSPECIFIED_ERROR)

    blobstore_stub = apiproxy_stub_map.apiproxy.GetStub("blobstore")


    try:
      blob_file = blobstore_stub.storage.OpenBlob(blob_key)
    except IOError:
      logging.exception('Could not get file for blob_key %r', blob_key)

      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_IMAGE_DATA)

    try:
      return Image.open(blob_file)
    except IOError:
      logging.exception('Could not open image %r for blob_key %r',
                        blob_file, blob_key)

      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_IMAGE_DATA)

  def _ValidateCropArg(self, arg):
    """Check an argument for the Crop transform.

    Args:
      arg: float, argument to Crop transform to check.

    Raises:
      apiproxy_errors.ApplicationError on problem with argument.
    """
    if not isinstance(arg, float):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    if not (0 <= arg <= 1.0):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

  def _CalculateNewDimensions(self,
                              current_width,
                              current_height,
                              req_width,
                              req_height):
    """Get new resize dimensions keeping the current aspect ratio.

    This uses the more restricting of the two requested values to determine
    the new ratio.

    Args:
      current_width: int, current width of the image.
      current_height: int, current height of the image.
      req_width: int, requested new width of the image.
      req_height: int, requested new height of the image.

    Returns:
      tuple (width, height) which are both ints of the new ratio.
    """


    width_ratio = float(req_width) / current_width
    height_ratio = float(req_height) / current_height



    if req_width == 0 or (width_ratio > height_ratio and req_height != 0):

      return int(height_ratio * current_width), req_height
    else:

      return req_width, int(width_ratio * current_height)

  def _Resize(self, image, transform):
    """Use PIL to resize the given image with the given transform.

    Args:
      image: PIL.Image.Image object to resize.
      transform: images_service_pb.Transform to use when resizing.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the resize data given is bad.
    """
    width = 0
    height = 0

    if transform.has_width():
      width = transform.width()
      if width < 0 or 4000 < width:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    if transform.has_height():
      height = transform.height()
      if height < 0 or 4000 < height:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    current_width, current_height = image.size
    new_width, new_height = self._CalculateNewDimensions(current_width,
                                                         current_height,
                                                         width,
                                                         height)

    return image.resize((new_width, new_height), Image.ANTIALIAS)

  def _Rotate(self, image, transform):
    """Use PIL to rotate the given image with the given transform.

    Args:
      image: PIL.Image.Image object to rotate.
      transform: images_service_pb.Transform to use when rotating.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the rotate data given is bad.
    """
    degrees = transform.rotate()
    if degrees < 0 or degrees % 90 != 0:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    degrees %= 360


    degrees = 360 - degrees
    return image.rotate(degrees)

  def _Crop(self, image, transform):
    """Use PIL to crop the given image with the given transform.

    Args:
      image: PIL.Image.Image object to crop.
      transform: images_service_pb.Transform to use when cropping.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the crop data given is bad.
    """
    left_x = 0.0
    top_y = 0.0
    right_x = 1.0
    bottom_y = 1.0

    if transform.has_crop_left_x():
      left_x = transform.crop_left_x()
      self._ValidateCropArg(left_x)

    if transform.has_crop_top_y():
      top_y = transform.crop_top_y()
      self._ValidateCropArg(top_y)

    if transform.has_crop_right_x():
      right_x = transform.crop_right_x()
      self._ValidateCropArg(right_x)

    if transform.has_crop_bottom_y():
      bottom_y = transform.crop_bottom_y()
      self._ValidateCropArg(bottom_y)


    width, height = image.size

    box = (int(transform.crop_left_x() * width),
           int(transform.crop_top_y() * height),
           int(transform.crop_right_x() * width),
           int(transform.crop_bottom_y() * height))

    return image.crop(box)

  def _ProcessTransforms(self, image, transforms):
    """Execute PIL operations based on transform values.

    Args:
      image: PIL.Image.Image instance, image to manipulate.
      trasnforms: list of ImagesTransformRequest.Transform objects.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if we are passed more than one of the same type of
      transform.
    """
    new_image = image
    if len(transforms) > images.MAX_TRANSFORMS_PER_REQUEST:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    for transform in transforms:
      if transform.has_width() or transform.has_height():

        new_image = self._Resize(new_image, transform)

      elif transform.has_rotate():

        new_image = self._Rotate(new_image, transform)

      elif transform.has_horizontal_flip():

        new_image = new_image.transpose(Image.FLIP_LEFT_RIGHT)

      elif transform.has_vertical_flip():

        new_image = new_image.transpose(Image.FLIP_TOP_BOTTOM)

      elif (transform.has_crop_left_x() or
          transform.has_crop_top_y() or
          transform.has_crop_right_x() or
          transform.has_crop_bottom_y()):

        new_image = self._Crop(new_image, transform)

      elif transform.has_autolevels():


        logging.info("I'm Feeling Lucky autolevels will be visible once this "
                     "application is deployed.")
      else:
        logging.warn("Found no transformations found to perform.")

    return new_image
