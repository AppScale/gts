#!/bin/bash

git clone https://github.com/lmandres/appscale-raspberry-pi.git
git clone https://github.com/lmandres/appscale-tools-raspberry-pi.git

mv -v appscale-raspberry-pi appscale
mv -v appscale-tools-raspberry-pi appscale-tools

sh appscale/debian/appscale_build.sh
sh appscale-tools/debian/appscale_build.sh

echo Done!
