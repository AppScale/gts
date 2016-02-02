#!/bin/bash

git clone https://github.com/lmandres/zookeeper-raspberry-pi.git
git clone https://github.com/lmandres/appscale-raspberry-pi.git
git clone https://github.com/lmandres/appscale-tools-raspberry-pi.git

sh appscale-raspberry-pi/debian/appscale_build.sh
cd zookeeper-raspberry-pi
gem build zookeeper.gemspec
gem install --local zookeeper-1.4.11.gem
cd ..
sh appscale-tools-raspberry-pi/debian/appscale_build.sh

echo Done!
