#!/bin/bash

git clone https://github.com/lmandres/zookeeper-raspberry-pi.git
git clone https://github.com/lmandres/appscale-raspberry-pi.git
git clone https://github.com/lmandres/appscale-tools-raspberry-pi.git

rm -Rf appscale
rm -Rf appscale-tools
mv appscale-raspberry-pi appscale
mv appscale-tools-raspberry-pi appscale-tools

sh appscale/debian/appscale_build.sh
cd zookeeper-raspberry-pi
gem build zookeeper.gemspec
gem install --local zookeeper-1.4.11.gem
cd ..
cp -v /root/appscale/AppDB/cassandra/templates/cassandra-env.sh /root/appscale/AppDB/cassandra/cassandra/conf
sh appscale-tools/debian/appscale_build.sh

echo Done!
