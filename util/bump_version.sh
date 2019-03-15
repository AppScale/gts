#!/bin/bash

#
# Simple script to allow version bumping of AppScale.
#
# major -> 3.4.0 -> 4.0.0
# minor -> 3.4.3 -> 3.5.0
# patch -> 3.4.3 -> 3.4.4
#
if [ ! -e VERSION ]; then
	echo "Unable to locate the VERSION file, is your working directory the top level of the repo?"
	exit 1
fi

version=$(tail -1 VERSION | cut -d' ' -f3)

case $1 in
	"major")
	bump_field="\$1"
	fmt_str="%s.0.0"
	;;
	"minor")
	bump_field="\$2"
	fmt_str="%s.%s.0"
	;;
	"patch")
	bump_field="\$3"
	fmt_str="%s.%s.%s"
	;;
	*)
	echo "usage: $0 [major|minor|patch]"
	exit 1
esac

# awk doesn't mind that not all fields will get formatted...
new_version=$(echo $version | awk -F. "{${bump_field}++;printf \"${fmt_str}\", \$1, \$2, \$3}")

echo "Bumping version from: ${version} to ${new_version}, changes not automatically committed"

# Do the version change
sed -i "s/${version}/${new_version}/g" VERSION
