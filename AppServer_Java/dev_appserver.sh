#!/bin/bash
# Launches the AppScale Java AppServer with modified jars.
#
[ -z "${DEBUG}" ] || set -x  # trace if $DEBUG env. var. is non-zero
SDK_BIN="`dirname "$0" | sed -e "s#^\\([^/]\\)#${PWD}/\\1#"`" # sed makes absolute
SDK_LIB="$SDK_BIN/../lib"
JAR_FILE="$SDK_LIB/appengine-tools-api.jar:$SDK_LIB/user/appengine-api-1.0-sdk-1.8.0.jar:$SDK_LIB/impl/appscale-smtp.jar:$SDK_LIB/user/appengine-api-labs-1.8.0.jar:$SDK_LIB/impl/appscale-activation.jar:$SDK_LIB/user/jsr107cache-1.1.jar:$SDK_LIB/user/appengine-jsr107cache-1.8.0.jar:$SDK_LIB/impl/appscale-mail.jar"

if [ ! -e "$SDK_LIB/appengine-tools-api.jar" ]; then
    echo "Repacked jar files not found"
    exit 1
fi

java -ea -cp "$JAR_FILE" \
  com.google.appengine.tools.KickStart \
  com.google.appengine.tools.development.DevAppServerMain "$@"
