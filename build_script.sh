#!/bin/bash
echo -n "Checking to make sure you are root..."
if [ "$(id -u)" != "0" ]; then
   echo "Failed" 1>&2
   exit 1
fi
echo "Success"

set -e
set -x
BRANCH=master
USER=AppScale

echo -n "Setting root password for this image"
# Set the password for this image
passwd
echo "Success"

echo -n "Getting source code..."
apt-get install -y git-core
git clone https://github.com/$USER/appscale.git $BRANCH
git clone https://github.com/$USER/appscale-tools.git $BRANCH
echo "Success"

echo "Building AppScale Image..."
cd appscale/debian/
bash appscale_build.sh

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
