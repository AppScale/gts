#!/bin/sh

# Scanning deb package files.
# This script assumes deb files placed as follows.
#
# pool/
#   jaunty-test .. test release deb packages.
#                  This folder should contains all architecture binaries.
#   jaunty-stable .. stable release deb packages.
#   karmic-test
#   karmic-stable

#SCAN_OPT=--multiversion
SCAN_OPT=

scanbinary()
{
    if [ -e pool/${1}-${2} ]; then
	echo "scanning $1 $2 $3"
	dpkg-scanpackages $SCAN_OPT --arch $3 pool/${1}-${2} | gzip > Packages.gz
	if [ -e Packages.gz ]; then
	    mkdir -p dists/$1/$2/binary-$3
	    mv Packages.gz dists/$1/$2/binary-$3
	fi
    else
	echo "$1 $2 is not found."
    fi
}

if [ -n "$1" ]; then
    scanbinary $1 $2 $3
else
    for dist in precise
    do
	for ver in test stable
	do
	    for arch in amd64 i386
	    do
		scanbinary $dist $ver $arch
	    done
	done
    done
fi
