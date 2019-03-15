#!/bin/bash

#
# Helper script to gather all git log messages from the last tag
# and construct a preliminary RELEASE file for the release.
#
# Assumes the new release from the VERSION file.
#

if [ ! -e RELEASE ]; then
	echo "Unable to locate RELEASE file, is your working dir the top level of the repo"
	exit 1
fi

echo "Generating RELEASE file (changelog)"

# header
head -7 RELEASE > t_release

echo "New Release version: $(tail -1 VERSION) - released $(date +'%B %Y')"
# release line
echo "$(tail -1 VERSION), released $(date +'%B %Y')" >> t_release
echo "Highlights of features and defects fixed in this release:" >> t_release

echo -n "Gathering git logs"
# Git logs from last tag (eg 3.4.0)
git log $(git describe --tags --abbrev=0)..HEAD  | grep -A5 'Merge pull request' | grep -v 'commit ' | grep -v Author: | grep -v -- '--' | grep -v "Merge" | grep -v -e '^[[:space:]]*$' | sed 's/[[:space:]]*/ - /' >> t_release

echo "" >> t_release
echo "" >> t_release
echo "...done"

echo "Known Issues:" >> t_release
echo "" >> t_release

echo -n "Appending old release notes"
tail -n+7 RELEASE >> t_release
echo "...done"

echo -n "Constructing new RELEASE file"
cp t_release RELEASE
rm -f t_release
echo "...done"

echo "Be sure to read through the RELEASE file before commiting the changes"
