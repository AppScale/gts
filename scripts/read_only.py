#!/usr/bin/env python2

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

make_active = False
if sys.argv[1] == 'on':
  make_active = True
elif sys.argv[1] == 'off':
  make_active = False
else:
  print('Please give a value of "on" or "off".')
  exit(1)

acc = appscale_info.get_appcontroller_client()
if make_active:
  acc.set_read_only('true')
  print('Datastore writes are now disabled.')
else:
  acc.set_read_only('false')
  print('Datastore writes are now enabled.')
