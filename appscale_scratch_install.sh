cp /etc/apt/sources.list /etc/apt/sources.list.pre-appscale
echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty main restricted" > /etc/apt/sources.list 
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty main restricted" >> /etc/apt/sources.list 

echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty-updates main restricted" >> /etc/apt/sources.list 
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty-updates main restricted" >> /etc/apt/sources.list 

echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty universe" >> /etc/apt/sources.list 
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty universe" >> /etc/apt/soure.list 
echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty-updates universe" >> /etc/apt/sources.list
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty-updates universe" >> /etc/apt/sources.list

echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty multiverse" >> /etc/apt/sources.list
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty multiverse" >> /etc/apt/sources.list
echo "deb http://us.archive.ubuntu.com/ubuntu/ jaunty-updates multiverse" >> /etc/apt/sources.list
echo "deb-src http://us.archive.ubuntu.com/ubuntu/ jaunty-updates multiverse" >> /etc/apt/sources.list

echo "deb http://security.ubuntu.com/ubuntu jaunty-security main restricted" >> /etc/apt/sources.list
echo "deb-src http://security.ubuntu.com/ubuntu jaunty-security main restricted" >> /etc/apt/sources.list
echo "deb http://security.ubuntu.com/ubuntu jaunty-security universe" >> /etc/apt/sources.list
echo "deb-src http://security.ubuntu.com/ubuntu jaunty-security universe" >> /etc/apt/sources.list
echo "deb http://security.ubuntu.com/ubuntu jaunty-security multiverse" >> /etc/apt/sources.list
echo "deb-src http://security.ubuntu.com/ubuntu jaunty-security multiverse" >> /etc/apt/sources.list

apt-get update
apt-get -y upgrade
apt-get -y dist-upgrade

apt-get -y install xterm ssh openssl libssl-dev sun-java6-jdk python2.6-dev python-m2crypto python-soappy make gcc g++ ntp python-yaml cvs wget autoconf automake libtool bison flex zlib1g zlib1g-dev libzlib-ruby  ruby1.8 libzip-ruby1.8 libboost-dev ruby1.8-dev libopenssl-ruby libopenssl-ruby1.8 libruby1.8 irb1.8 rdoc iptables

apt-get -y install cmake libboost-filesystem-dev libboost-serialization-dev libboost-thread-dev libboost-program-options-dev libboost-iostreams-dev libboost-python-dev liblog4cpp5-dev libexpat1-dev libreadline5-dev libncurses5-dev libevent-dev build-essential automake pkg-config doxygen graphviz rsync lsof

apt-get -y install make tcl-dev libbz2-dev libreadline-dev libgdbm-dev python-tk byacc tk8.4-dev sun-java5-jdk ant libdb4.7++-dev nginx python-imaging haproxy

apt-get -y remove gij ecj

cp /etc/hosts /etc/hosts.orig
echo "127.0.0.1       localhost localhost.localdomain"> /etc/hosts 
echo "::1     ip6-localhost ip6-loopback">> /etc/hosts 
echo "fe00::0 ip6-localnet">> /etc/hosts 
echo "ff00::0 ip6-mcastprefix" >> /etc/hosts
echo "ff02::1 ip6-allnodes" >> /etc/hosts
echo "ff02::2 ip6-allrouters" >>/etc/hosts
echo "ff02::3 ip6-allhosts" >>/etc/hosts

update-alternatives --install /bin/sh sh /bin/dash 1
update-alternatives --install /bin/sh sh /bin/bash 1
update-alternatives --config sh

echo "source /root/appscale/appscale.env" >> /root/.bashrc
echo "export APPSCALE_HOME=/root/appscale" >> /root/.bashrc
echo "export PYTHON_EGG_CACHE=/tmp/.python_eggs" >> /root/.bashrc
echo "export PYTHONPATH=/usr/local/python-2.6/lib/python26.zip:/usr/local/python-2.6/lib/python2.6:/usr/local/python-2.6/lib/python2.6/plat-linux2:/usr/local/python-2.6/lib/python2.6/lib-tk:/usr/local/python-2.6/lib/python2.6/lib-dynload:/usr/local/python-2.6/lib/python2.6/site-packages:/usr/lib/python2.6/site-packages:/var/lib/python-support:/usr/share/python-support/python-yaml:/usr/share/python-support:/usr/share/python-support/python-m2crypto:/usr/share/python-support/python-soappy:/root/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py:/usr/lib/python-support/python-m2crypto/python2.6/M2Crypto/" >> /root/.bashrc
 
export APPSCALE_HOME=/root/appscale
export PYTHONPATH=/usr/local/python-2.6/lib/python25.zip:/usr/local/python-2.6/lib/python2.6:/usr/local/python-2.6/lib/python2.6/plat-linux2:/usr/local/python-2.6/lib/python2.6/lib-tk:/usr/local/python-2.6/lib/python2.6/lib-dynload:/usr/local/python-2.6/lib/python2.6/site-packages:/usr/lib/python2.6/site-packages:/var/lib/python-support:/usr/share/python-support/python-yaml:/usr/share/python-support:/usr/share/python-support/python-m2crypto:/usr/share/python-support/python-soappy:/root/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py:/usr/lib/python-support/python-m2crypto/python2.6/M2Crypto/

ln /usr/bin/ruby1.8 /usr/bin/ruby

apt-get -y install bzr
bzr branch lp:~appscale-maintainers/appscale/appscale
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD APPSCALE. CHECK BZR." ; exit; fi

#wget http://appscale.googlecode.com/files/appscale-1.1.tar.gz
#if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD APPSCALE TAR BALL. CHECK LINK." ; exit; fi
#tar zxvf appscale-1.1.tar.gz
#rm appscale-1.1.tar.gz 

cd ${APPSCALE_HOME}
mkdir downloads
cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/thrift.tgz -O ${APPSCALE_HOME}/downloads/thrift.tgz
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD THRIFT. CHECK LINK." ; exit; fi

tar zxfv thrift.tgz
cd ${APPSCALE_HOME}/downloads/thrift
./bootstrap.sh
CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
$CONFIG_SHELL ./configure --without-csharp --disable-gen-java --without-java
make
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE THRIFT. " ; exit; fi
make install
cd ${APPSCALE_HOME}/downloads/thrift/lib/py
make install
cd ${APPSCALE_HOME}/downloads/thrift/lib/rb
make install
cd ${APPSCALE_HOME}/downloads/thrift/lib/perl
perl Makefile.PL
make install
echo "include /usr/local/lib" >> /etc/ld.so.conf

cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/thrift-hypertable.tar.gz -O ${APPSCALE_HOME}/downloads/thrift-hypertable.tar.gz
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD THRIFT-HYPERTABLE. CHECK LINK." ; exit; fi

tar zxfv thrift-hypertable.tar.gz
cd ${APPSCALE_HOME}/downloads/thrift-hypertable
./bootstrap.sh
CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
$CONFIG_SHELL ./configure 
make
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE THRIFT HYPERTABLE. " ; exit; fi
make install
cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/py
make install
cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/rb
make install
cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/perl
perl Makefile.PL
make install

cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/rubygems-1.3.1.tgz -O ${APPSCALE_HOME}/downloads/rubygems-1.3.1.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD RUBY GEMS. CHECK LINK." ; exit; fi

tar zxvf rubygems-*.tgz
cd ${APPSCALE_HOME}/downloads/rubygems-1.3.1
ruby setup.rb
ln -sf /usr/bin/gem1.8 /usr/bin/gem

gem update
gem install god redgreen 

gem install -v=2.3.4 rails
gem install mongrel mongrel_cluster

cd ${APPSCALE_HOME}
cp AppLoadBalancer/config/load-balancer.conf /etc/nginx/sites-enabled/
cp AppLoadBalancer/config/haproxy.cfg /etc/haproxy/

cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/hyperic-sigar-1.6.0.tar.gz -O  ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HYPERIC SIGAR. CHECK LINK." ; exit; fi

tar -xzvf hyperic-sigar-1.6.0.tar.gz
cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/include/*.h /usr/local/include
# 64 BIT
cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-amd64-linux.so hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-ia64-linux.so /usr/local/lib/
# 32 BIT (comment the above line)
#cp hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-x86-linux.so /usr/local/lib/
ldconfig

gem install -y capistrano

echo "export PATH=\${PATH}:/var/lib/gems/1.8/bin" >> /root/.bashrc
export PATH=${PATH}:/var/lib/gems/1.8/bin

cd ${APPSCALE_HOME}/AppDB
rm -rf hadoop-0.20.0
wget http://appscale.cs.ucsb.edu/appscale_files/hadoop-0.20.0.tar.gz -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HADOOP 0.20.0. CHECK LINK." ; exit; fi

tar xvzf hadoop-0.20.0.tar.gz
cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
echo "export APPSCALE_HOME=/root/appscale" >> ./conf/hadoop-env.sh
echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_HOME=${APPSCALE_HOME}/AppDB/hadoop-0.20.0" >> ./conf/hadoop-env.sh
 
echo "export HBASE_HOME=${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_CLASSPATH=${HBASE_HOME}:${HBASE_HOME}/hbase/hbase-0.20.3.jar:${HBASE_HOME}/hbase/hbase-0.20.3-test.jar:${HBASE_HOME}/conf:${HBASE_HOME}/build/classes:${HADOOP_HOME}/build/classes" >> ./conf/hadoop-env.sh
 
echo "export CLASSPATH=${CLASSPATH}:${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_HEAPSIZE=2000" >> ./conf/hadoop-env.sh

cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
wget http://issues.apache.org/jira/secure/attachment/12405513/hadoop-includes-2.patch -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/hadoop-includes-2.patch
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO HADOOP PATH. CHECK LINK." ; exit; fi
patch -p0 < hadoop-includes-2.patch
cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/utils
sh configure

make

sed -i "s/CXXFLAGS = -g/CXXFLAGS = -fPIC -g/g" ./Makefile

make clean
make

if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE HADOOP UTIL. " ; exit; fi

make install
cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/pipes
sh configure
make
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE HADOOP PIPES. " ; exit; fi

make install
echo "${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/install/lib" | tee -a /etc/ld.so.conf.d/hadoop.conf
ldconfig          


cd ${APPSCALE_HOME}/AppDB/hypertable
rm -rf src build 0.9.2.5
mkdir -p src build
cd ${APPSCALE_HOME}/AppDB/hypertable/src
wget http://appscale.cs.ucsb.edu/appscale_files/hypertable-0.9.2.5-alpha-src.tar.gz -O ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha-src.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HYPERTABLE 0.9.2.5. CHECK LINK." ; exit; fi

tar xvzf hypertable-0.9.2.5-alpha-src.tar.gz

export HYPERTABLE=${APPSCALE_HOME}/AppDB/hypertable
export HADOOP=${APPSCALE_HOME}/AppDB/hadoop-0.20.0
cd ${APPSCALE_HOME}/AppDB/hypertable/build
cmake -DHADOOP_INCLUDE_PATH=${HADOOP}/src/c++/install/include/ -DHADOOP_LIB_PATH=${HADOOP}/src/c++/install/lib/ -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=${HYPERTABLE} -DJAVA_INCLUDE_PATH=/usr/lib/jvm/java-6-sun/include/ -DJAVA_INCLUDE_PATH2=/usr/lib/jvm/java-6-sun/include/linux/  ../src/hypertable-0.9.2.5-alpha

cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableRangeMap.cc  ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableRangeMap.cc 
cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableReader.cc ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableReader.cc

make -j 4 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE HYPERTABLE 0.9.2.5. " ; exit; fi


make install
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE INSTALL HYPERTABLE 0.9.2.5. " ; exit; fi

echo "${HYPERTABLE}/0.9.2.5/lib" | tee -a /etc/ld.so.conf.d/hypertable.conf
ldconfig


cd ${APPSCALE_HOME}/AppDB
rm -fdr ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3
cd ${APPSCALE_HOME}/AppDB/hbase
wget http://appscale.cs.ucsb.edu/appscale_files/hbase-0.20.3.tar.gz -O ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HBASE 0.20.3. CHECK LINK." ; exit; fi

tar zxvf hbase-0.20.3.tar.gz
echo "export APPSCALE_HOME=/root/appscale" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/conf/hbase-env.sh
echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/conf/hbase-env.sh
 
echo "export HBASE_CLASSPATH=${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/conf/hbase-env.sh
 
echo "export HBASE_HEAPSIZE=2000" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/conf/hbase-env.sh
echo "export HBASE_MANAGES_ZK=FALSE" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/conf/hbase-env.sh

cp ${APPSCALE_HOME}/AppDB/hbase/hbasefix/DistributedFileSystem.java ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/hdfs/org/apache/hadoop/hdfs/DistributedFileSystem.java 		
cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0		
ant jar
cp build/hadoop-0.20.1-dev-core.jar ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.3/lib/hadoop-0.20.0-core.jar 

cp /root/appscale/appscale /etc/init.d/
chmod ugo+x /etc/init.d/appscale
update-rc.d appscale defaults

cp /root/appscale/haproxy /etc/init.d/
chmod ugo+x /etc/init.d/haproxy
update-rc.d haproxy defaults


#install the tools so that auto deployment over ec2 is possible
#TODO: add the same for the faster euca tools
sh ${APPSCALE_HOME}/ec2_scratch_install.sh

echo "source /root/appscale/appscale.env" >> /root/.bashrc
echo "export PATH=/usr/local/ec2-api-tools/bin/:\$PATH" >> /root/.bashrc
 
echo "export EC2_HOME=/usr/local/ec2-api-tools" >> /root/.bashrc
 
echo "export EC2_PRIVATE_KEY=/root/appscale/.appscale/certs/mykey.pem " >> /root/.bashrc

echo "export EC2_CERT=/root/appscale/.appscale/certs/mycert.pem  " >> /root/.bashrc

echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> /root/.bashrc

source /root/.bashrc
mkdir -p ${APPSCALE_HOME}/logs

# Install Cassandra database - version 0.50.0
echo "Install Cassandra 0.50.0 for AppScale"
mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
cd ${APPSCALE_HOME}/AppDB/cassandra
wget http://appscale.cs.ucsb.edu/appscale_files/apache-cassandra-incubating-0.5.0-src.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD CASSANDRA. CHECK LINK." ; exit; fi
tar xzvf apache-cassandra-incubating-0.5.0-src.tar.gz
mv apache-cassandra-incubating-0.5.0-src cassandra
rm -f apache-cassandra-incubating-0.5.0-src.tar.gz
cd ${APPSCALE_HOME}/AppDB/cassandra/cassandra
ant
mkdir /var/cassandra
chmod +x bin/cassandra
cp ${APPSCALE_HOME}/.appscale/cassie_templates/cassandra.in.sh ${APPSCALE_HOME}/AppDB/cassandra/cassandra/bin

# Voldemort pre-req - protocol buffers
cd ${APPSCALE_HOME}
wget http://appscale.cs.ucsb.edu/appscale_files/protobuf-2.3.0.tar.gz
tar zxvf protobuf-2.3.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PROTOBUF. CHECK LINK." ; exit; fi
tar zxvf protobuf-2.3.0.tar.gz
rm protobuf-2.3.0.tar.gz
cd protobuf-2.3.0
./configure
make
make check
make install
cd python
python setup.py install

# Install Voldemort database - 0.80
mkdir -p ${APPSCALE_HOME}/AppDB/voldemort
cd ${APPSCALE_HOME}/AppDB/voldemort
wget http://appscale.cs.ucsb.edu/appscale_files/voldemort-0.80.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD VOLDEMORT. CHECK LINK." ; exit; fi
tar xzvf voldemort-0.80.tar.gz
mv voldemort-0.80 voldemort
rm voldemort-0.80.tar.gz
cd ${APPSCALE_HOME}/AppDB/voldemort/voldemort
ant jar
mkdir /var/voldemort
mkdir -p ${APPSCALE_HOME}/AppDB/voldemort/voldemort/config/appscale/config
chmod +x bin/voldemort-server.sh

# MySQL 64 bit
mkdir -p ${APPSCALE_HOME}/AppDB/mysql
cd ${APPSCALE_HOME}/AppDB/mysql
wget http://appscale.cs.ucsb.edu/appscale_files/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz -O  ${APPSCALE_HOME}/AppDB/mysql/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MYSQL. CHECK LINK." ; exit; fi
mv mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz mysql.tar.gz

# FOR 32 BIT COMMENT THE ABOVE THREE LINES AND UNCOMMENT
# THE FOLLOWING THREE LINES
###wget http://appscale.cs.ucsb.edu/appscale_files/mysql-cluster-gpl-6.3.20-linux-i686-glibc23.tar.gz
###if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MYSQL. CHECK LINK." ; exit; fi
###mv mysql-cluster-gpl-6.3.20-linux-i686-glibc23.tar.gz mysql.tar.gz

# MongoDB 64bit - version 1.2.2
cd ${APPSCALE_HOME}/AppDB/
wget http://appscale.cs.ucsb.edu/appscale_files/mongodb-linux-x86_64-1.2.2.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MONGO. CHECK LINK." ; exit; fi
tar zxvf mongodb-linux-x86_64-1.2.2.tgz
mv mongodb-linux-x86_64-1.2.2 mongodb
chmod +x mongodb/bin/mongo mongodb/bin/mongod
rm mongodb-linux-x86_64-1.2.2.tgz

cd ${APPSCALE_HOME}
wget http://pypi.python.org/packages/2.6/s/setuptools/setuptools-0.6c9-py2.6.egg#md5=ca37b1ff16fa2ede6e19383e7b59245a
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD SETUPTOOLS. CHECK LINK." ; exit; fi
tar zxvf mongodb-linux-x86_64-1.0.0.tgz
sh setuptools-0.6c9-py2.6.egg
rm setuptools-0.6c9-py2.6.egg 
easy_install pymongo

# install euca2ools dependencies
cd ${APPSCALE_HOME}
apt-get -y install python-dev swig libssl-dev
wget http://kings.cs.ucsb.edu/appscale_files/euca2ools-1.0-src-deps.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD EUCA TOOLS. CHECK LINK." ; exit; fi
tar zvxf euca2ools-1.0-src-deps.tar.gz
cd euca2ools-1.0-src-deps
tar zxvf boto-1.8d.tar.gz
cd boto-1.8d
sudo python setup.py install

# install euca2ools
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/euca2ools-1.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD EUCA TOOLS. CHECK LINK." ; exit; fi
tar zxvf euca2ools-1.0.tar.gz 
cd euca2ools-1.0
make
cd
rm -rf euca2ools-1.0*

# install appscale-tools
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/appscale-tools-1.3.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD APPSCALE TOOLS. CHECK LINK." ; exit; fi
tar zxvf appscale-tools-1.3.tar.gz
mv appscale-tools /usr/local/

# install memcached
# The version being installed from source seg faults upon connection
# Just use the version in the repo until a solution is found --jkupferman
apt-get -y install memcached

#cd ${APPSCALE_HOME}
#wget http://kings.cs.ucsb.edu/appscale_files/memcached-1.4.2.tar.gz
#if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MEMCACHE. CHECK LINK." ; exit; fi
#tar zxvf memcached-1.4.2.tar.gz
#cd memcached-1.4.2
#./configure
#make
#make install
#cd ..
#rm -rf memcached-1.4.2*

# install python lib for memcached
apt-get -y install python-memcache

# this isn't working right now - will return to this with raj
#cd ${APPSCALE_HOME}
#wget http://kings.cs.ucsb.edu/appscale_files/python-memcached-1.44.tar.gz
#tar zxvf python-memcached-1.44.tar.gz
#cd python-memcached-1.44
#python setup.py install
#cd ..
#rm -rf python-memcached-1.44*

# install memcachedb

# first install berkeley db
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/db-4.8.24.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD BERK DB. CHECK LINK." ; exit; fi
tar zxvf db-4.8.24.tar.gz
cd db-4.8.24
cd build_unix/
../dist/configure
make
make install
cd ${APPSCALE_HOME}
rm -rf db-4.8.24*

# next, install libevent
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/libevent-1.4.12-stable.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD LIB EVENT. CHECK LINK." ; exit; fi
tar zxvf libevent-1.4.12-stable.tar.gz
cd libevent-1.4.12-stable
./configure
make
make install
echo "include /usr/local/lib" >> /etc/ld.so.conf
echo "include /usr/local/BerkeleyDB.4.7/lib" >> /etc/ld.so.conf
ldconfig
cd ${APPSCALE_HOME}
rm -rf libevent-1.4.12-stable*

# now we can install memcachedb 1.2.1-beta
cd ${APPSCALE_HOME}/AppDB/memcachedb
wget http://kings.cs.ucsb.edu/appscale_files/memcachedb.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MEMCAHCEDB. CHECK LINK." ; exit; fi
tar zxvf memcachedb.tar.gz
cd memcachedb
./configure --enable-threads --with-libevent=/usr/local/lib
make
make install
cd ${APPSCALE_HOME}/AppDB/memcachedb
rm memcachedb.tar.gz

apt-get -y install curl screen tcpdump
apt-get -y remove ant mysql-server mysql-common mysql-client
apt-get -y install python-mysqldb 
apt-get -y install python2.5

# install TimesTen depending
apt-get -y install unixodbc-dev unzip
cd ${APPSCALE_HOME}/AppDB/timesten
wget http://pyodbc.googlecode.com/files/pyodbc-2.1.6.zip
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD TIMESTEN. CHECK LINK." ; exit; fi
unzip pyodbc-2.1.6.zip
cd pyodbc-2.1.6
python setup.py install
cat >> /root/.bashrc <<EOF
if [ -e /opt/TimesTen/tt70/bin/ttenv.sh ]; then
  source /opt/TimesTen/tt70/bin/ttenv.sh
fi
export ODBCINI=/root/appscale/AppDB/timesten/.odbc.ini
EOF

#########
# Pig
#########
cd ${APPSCALE_HOME}/downloads
wget http://apache.deathculture.net/hadoop/pig/pig-0.5.0/pig-0.5.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PIG. CHECK LINK." ; exit; fi
tar zxvf pig-0.5.0.tar.gz
cd pig-0.5.0
mkdir tmp
cp pig-0.5.0-core.jar tmp/
cd tmp
jar xvf pig-0.5.0-core.jar
rm -rf pig-0.5.0-core.jar
/bin/cp -f ~/appscale/AppDB/hadoop-0.20.0/build/classes/org/apache/hadoop/hdfs/* ${APPSCALE_HOME}/downloads/pig-0.5.0/tmp/org/apache/hadoop/hdfs/
jar cvf ../pig-0.5.0-core.jar ./*
rm -rf ./*
wget http://appscale.cs.ucsb.edu/appscale_files/pigtutorial.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PIGTUTORIAL. CHECK LINK." ; exit; fi
tar zxvf pigtutorial.tar.gz
export PIG_CLASSPATH=${APPSCALE_HOME}/downloads/pig-0.5.0/tmp/pigtmp/pig.jar:${APPSCALE_HOME}/AppDB/hadoop-0.20.0/conf
echo "export PIG_CLASSPATH=${APPSCALE_HOME}/downloads/pig-0.5.0/tmp/pig.jar:${APPSCALE_HOME}/AppDB/hadoop-0.20.0/conf" >> ~/.bashrc

# install x10 support
cd /usr/local
wget http://appscale.cs.ucsb.edu/appscale_files/x10-2.0.1_linux_x86_64.tgz
tar zxvf x10-2.0.1_linux_x86_64.tgz
rm x10-2.0.1_linux_x86_64.tgz
echo 'export PATH=/usr/local/x10/bin:$PATH' >> ~/.bashrc

######################
# Prime Python eggs
######################
python2.6 ${APPSCALE_HOME}/AppDB/appscale_server.py
pkill python

# finally
# cgb: control-c here if building on ec2
# otherwise it messes up the ssh key that ec2 puts on and you can't log in
ssh-keygen 
cat /root/.ssh/id_rsa.pub > /root/.ssh/authorized_keys

