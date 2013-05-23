# Copyright 2011 Google Inc. All rights reserved.
# Use of this source code is governed by the Apache 2.0
# license that can be found in the LICENSE file.

include $(GOROOT)/src/Make.inc

all:	install

# Order matters!
DIRS=\
	appengine_internal/remote_api\
	appengine_internal\
	appengine_internal/blobstore\
	appengine_internal/datastore\
	appengine_internal/files\
	appengine_internal/mail\
	appengine_internal/memcache\
	appengine_internal/taskqueue\
	appengine_internal/urlfetch\
	appengine_internal/user\
	appengine\
	appengine/datastore\
	appengine/mail\
	appengine/memcache\
	appengine/neptune\
	appengine/taskqueue\
	appengine/urlfetch\
	appengine/user\
	appengine/blobstore\
	go-app-builder\

install clean nuke:
	for dir in $(DIRS); do \
		make -C $$dir $@ || break; \
	done
