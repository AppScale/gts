#!/bin/bash

: ${1:?ERROR: Please supply a control file to parse}

#
# Select range from Build-Depends|Depends, until last element in list (no comma)
# gather package names and output them as a space separated list.
#
sed -r -n '/^(Build-Depends|Depends):/,/[-.+a-zA-Z0-9]+$/ {
    s/(Build-Depends|Depends)://               # Remove stanza
    s/[[:space:]]*([-+.a-zA-Z0-9]+).*/\1/      # Remove space and commas
    /appscale-.*/d                             # Remove appscale packages
    p                                          # Print package name
    }' "$@" | tr '\n' ' '
