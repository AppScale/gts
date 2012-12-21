set -e
set -x
BRANCH=master
USER=AppScale

# Set the password for this image
passwd

# Install git and retrieve repos
apt-get install -y git-core
git clone https://github.com/$USER/appscale.git $BRANCH
git clone https://github.com/$USER/appscale-tools.git $BRANCH

# Build Image and tools
cd appscale/debian/
bash appscale_build.sh
cd ../../
cd appscale-tools/debian
bash appscale_build.sh
cd ../../
echo "Image and tools are complete"

# Run unit tests
cd appscale
rake
sh ts_python.sh

cd ..
cd appscale-tools
rake
