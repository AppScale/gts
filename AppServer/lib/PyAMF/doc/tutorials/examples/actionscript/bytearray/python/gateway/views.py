# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

import glob
import os.path
import tempfile

from django.http import HttpResponse, get_host
from pyamf.flex import ArrayCollection

from python import gateway


max_result = 50
file_types = 'jpg,png'
base_url = 'http://%s/images/'


def get_snapshots(http_request):
    """
    Gets a list of snapshots in the images dir.

    @return: list with 3 elements: URL of image folder, allowed filetypes and
        the L{ArrayCollection} of snapshots
    """
    url = base_url % get_host(http_request)
    extensions = file_types.split(',')
    l = []

    for type in extensions:
        location = os.path.join(gateway.images_root, '*.' + type.strip())
        for img in glob.glob(location):
            name = img[len(gateway.images_root) + 1:]
            obj = {
                'name': name
            }

            l.append(obj)

    l.reverse()

    return [url, extensions, ArrayCollection(l[:max_result])]


def save_snapshot(http_request, image, type):
    """
    Saves an image to the static image dir.

    @param image: A L{pyamf.amf3.ByteArray} instance
    """
    fp = tempfile.mkstemp(dir=gateway.images_root, prefix='snapshot_',
                          suffix='.' + type)

    fp = open(fp[1], 'wb+')
    fp.write(image.getvalue())
    fp.close()

    url = base_url % get_host(http_request)
    name = fp.name[len(gateway.images_root) + 1:]

    return {
        'url': url + name,
        'name': name
    }

