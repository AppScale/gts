# Copyright 2011 Google Inc. All Rights Reserved.

"""Specify the modules for which a Python 2.7 stub exists."""

__all__ = [
  # These reside here.
  'httplib',
  'socket',
  'threading',
  'urllib',
  ]

MODULE_OVERRIDES = __all__ + [
  # These are used in the Py27 runtime but must be imported from dist.
  'ftplib',
  'select',
  'subprocess',
  'tempfile',
  ]
