#!/usr/bin/env python
#
# Copyright 2011 Google Inc. All rights reserved.
# Use of this source code is governed by the Apache 2.0
# license that can be found in the LICENSE file.

"""Convenience wrapper for starting a Go tool in the App Engine SDK."""

import os
import sys

SDK_BASE = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
GOROOT = os.path.join(SDK_BASE, 'goroot')

if __name__ == '__main__':
  tool = os.path.basename(__file__)
  bin = os.path.join(GOROOT, 'bin', tool)
  os.environ['GOROOT'] = GOROOT
  os.environ['APPENGINE_DEV_APPSERVER'] = os.path.join(SDK_BASE,
                                                       'dev_appserver.py')
  if 'GOBIN' in os.environ:
    del os.environ['GOBIN']

  # Set a GOPATH if one is not set.
  if not os.environ.get('GOPATH'):
    os.environ['GOPATH'] = os.path.join(SDK_BASE, 'gopath')

  os.execve(bin, sys.argv, os.environ)
