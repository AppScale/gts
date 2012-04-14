#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: jcgregorio@google.com (Joe Gregorio)
#
# Script to update google3 from the external hg repository or local
# copy of repository.  This will open/add all the changed/new files
# from the external repository. It does not take care of deleted file.
# You must manaully call 'g4 mail' on the changes.

source gbash.sh || exit

DEFINE_string local_source "" \
  "Local copy of repository to copy over.  If not set, remote repository is used."

gbash::init_google "$@"

if [[ -z "${FLAGS_local_source}" ]]; then
  echo '*** Syncing copy of repository'
  rm -rf /tmp/httplib2
  mkdir /tmp/httplib2
  hg clone https://httplib2.googlecode.com/hg/ /tmp/httplib2
  COPY_SOURCE=/tmp/httplib2
else
  eval COPY_SOURCE=${FLAGS_local_source}
fi

echo '*** Copying httplib2 over'
find third_party/py/httplib2 | xargs g4 open
cp -r ${COPY_SOURCE}/python2/httplib2/. third_party/py/httplib2/

echo '*** Adding new files'
g4 nothave third_party/py/httplib2 | xargs --no-run-if-empty g4 add

if [[ -z "${FLAGS_local_source}" ]]; then
  echo '*** Updating README.google'
  g4 edit third_party/py/httplib2/README.google
  VERSION=`hg log -r tip --template="{node}" /tmp/httplib2/`
  sed --in-place "s/^Version: .*/Version: $VERSION/" third_party/py/httplib2/README.google
  sed --in-place "s/r=.*/r=$VERSION/" third_party/py/httplib2/README.google
fi

echo '*** Reverting unchanged files'
g4 revert -a third_party/py/httplib2/...

echo
echo '*** All new and updated files have been added. Remember to look for deleted files.'
echo
echo '*** REMEMBER to fix up the importing of CA_CERTS in __init__.py'
