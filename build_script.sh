#!/bin/bash
echo "Usage: bash build_script <branch> <user> <database>"

echo -n "Checking to make sure you are root..."
if [ "$(id -u)" != "0" ]; then
   echo "Failed" 1>&2
   exit 1
fi
echo "Success"

set -e
BRANCH=${1:-testing}
USER=${2:-AppScale}
echo "Will be using github branch \"$BRANCH\" for user \"$USER\""
echo "git clone https://github.com/$USER/appscale.git --branch $BRANCH"
echo "Exit now (ctrl-c) if this is incorrect"
echo -n "Setting root password for this image"
# Set the password for this image
passwd
echo "Success"

echo -n "Getting source code..."
apt-get install -y git-core
git clone https://github.com/$USER/appscale.git --branch $BRANCH
git clone https://github.com/$USER/appscale-tools.git --branch $BRANCH
echo "Success"

echo "Building AppScale Image..."
cd appscale/debian/
bash appscale_build.sh $3

echo "Building AppScale Tools..." 
cd ../../
cd appscale-tools/debian
bash appscale_build.sh
cd ../../
echo "****************************"
echo "Image and tools are complete"
echo "****************************"

# Run unit tests
echo "Running Unit tests"
cd appscale
rake
sh ts_python.sh

cd ..
cd appscale-tools
rake
echo "Unit tests complete"
