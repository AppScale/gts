#!/bin/bash
function pause(){
if [ "$1" = "-i" ] 
then 
  echo "press any key"
  read -p "$*"
fi 
}
if [ "$1" = "-i" ]
then 
  echo "Interactive mode"
fi
echo "Starting Script" 

pause $1
echo "export APPSCALE_HOME=/root/appscale" >> /root/.bashrc
export APPSCALE_HOME=/root/appscale
export PYTHON_EGG_CACHE=/tmp/.python_eggs
ls /root/ibm_yum.sh
if [ $? != 0 ]; then echo "FAILURE: You must have ibm_yum.sh in /root/ in order to run this build script. " ; exit; fi
bash ibm_yum.sh -y update
# install packages here
pause $1
bash ibm_yum.sh -y install ruby
pause $1
bash ibm_yum.sh -y install ant
pause $1
bash ibm_yum.sh -y install ruby-devel
pause $1
bash ibm_yum.sh -y install gcc-c++ 
pause $1
bash ibm_yum.sh -y install make 
pause $1
bash ibm_yum.sh -y install doxygen 
pause $1
bash ibm_yum.sh -y install rsync 
pause $1
bash ibm_yum.sh -y install libtool 
pause $1
bash ibm_yum.sh -y install boost
pause $1
bash ibm_yum.sh -y install boost-devel
pause $1
bash ibm_yum.sh -y install rdoc
pause $1
#bash ibm_yum.sh -y install MySQL-python
#pause $1
bash ibm_yum.sh -y install zlib-devel
pause $1
#bash ibm_yum.sh -y install libevent-devel
#pause $1
bash ibm_yum.sh -y remove libevent
pause $1
bash ibm_yum.sh -y install bison
pause $1
bash ibm_yum.sh -y install flex 
pause $1
bash ibm_yum.sh -y install java-1.6.0-sun-devel
pause $1
bash ibm_yum.sh -y install junit
pause $1
bash ibm_yum.sh -y install ant-junit
pause $1
bash ibm_yum.sh -y install swig
pause $1
bash ibm_yum.sh -y install openssl-devel
pause $1
bash ibm_yum.sh -y install byacc 
pause $1
bash ibm_yum.sh -y install pcre-devel
pause $1
rhn_register
#################################
# get BZR with python2.4 for yum
#################################
cd 
rpm -Uvh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-3.noarch.rpm
yum -y install bzr
pause $1
yum -y install libyaml
pause $1
yum -y install libyaml-devel
pause $1
yum -y install bzip2-devel
pause $1
yum -y install cmake
pause $1
yum -y install log4cpp-devel
pause $1
yum -y install readline-devel
pause $1
yum -y install ncurses-devel
pause $1

# Grab the appscale source, after installing python 2.6 this breaks
cd 
bzr branch lp:~appscale-maintainers/appscale/appscale
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD APPSCALE. CHECK BZR." ; exit; fi
disabling mysql and hypertable for now

mkdir -p ${APPSCALE_HOME}/downloads

pause $1
#####################
# Install libevent
#####################
cd ${APPSCALE_HOME}/downloads
wget http://kings.cs.ucsb.edu/appscale_files/libevent-1.4.12-stable.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD LIBEVENT. CHECK LINK." ; exit; fi 
tar zxvf libevent-1.4.12-stable.tar.gz
cd libevent-1.4.12-stable
./configure
make
make install

pause $1

cd ${APPSCALE_HOME}/downloads
wget http://www.graphviz.org/pub/graphviz/stable/SOURCES/graphviz-2.26.0.tar.gz
tar zxvf graphviz-2.26.0.tar.gz
cd graphviz-2.26.0
./configure
make 
make install
pause $1

cd ${APPSCALE_HOME}/downloads
wget http://sysoev.ru/nginx/nginx-0.7.64.tar.gz 
tar zxvf nginx-0.7.64.tar.gz
cd nginx-0.7.64
./configure
make 
make install
pause $1

########################
# Install libyaml by rpm
# If yum install fails
########################
#cd ${APPSCALE_HOME}/downloads
#wget http://packages.sw.be/libyaml/libyaml-0.0.1-1.el5.rf.x86_64.rpm
#rpm -i libyaml-0.0.1-1.el5.rf.x86_64.rpm


# need junit for ant 
export CLASSPATH=/usr/share/java/junit.jar 

# ant for hbase
cd ${APPSCALE_HOME}/downloads
wget http://www.gtlib.gatech.edu/pub/apache/ant/source/apache-ant-1.7.1-src.tar.gz
tar zxvf apache-ant-1.7.1-src.tar.gz
export JAVA_HOME=/usr/lib/jvm/java-1.6.0-sun.x86_64
cd apache-ant-1.7.1/
./bootstrap.sh
sh build.sh
export ANT_HOME=/root/appscale/downloads/apache-ant-1.7.1/bootstrap/
echo "export ANT_HOME=/root/appscale/downloads/apache-ant-1.7.1/bootstrap/" >> ~/.bashrc
###############
# Get Python2.6
###############
cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/Python-2.6.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET PYTHON2.6. " ; exit; fi
tar zxvf Python-2.6.tar.gz
cd Python-2.6
./configure
make 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE PYTHON2.6. " ; exit; fi
make install
rm -f /usr/bin/python
ln -s /usr/local/bin/python2.6 /usr/bin/python
pause $1

cd ${APPSCALE_HOME}/downloads
wget http://downloads.sourceforge.net/project/swig/swig/swig-1.3.40/swig-1.3.40.tar.gz?use_mirror=voxel
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD SWIG. CHECK LINK." ; exit; fi
tar zxvf swig-1.3.40.tar.gz
cd swig-1.3.40
./configure
make
make install
cp -f /usr/local/bin/swig /usr/bin/swig
pause $1

cd ${APPSCALE_HOME}/downloads
wget http://pypi.python.org/packages/source/M/M2Crypto/M2Crypto-0.20.2.tar.gz#md5=6c24410410d6eb1920ea43f77a93613a
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD M2Crypto. CHECK LINK." ; exit; fi
tar zxvf M2Crypto-0.20.2.tar.gz 
cd M2Crypto-0.20.2
#sed -i 's/opensslconf_x86_64.h/openssl\/opensslconf_x86_64.h/g' /usr/include/openssl/opensslconf.h 
./fedora_setup.sh build
./fedora_setup.sh install
export PYTHONPATH="/usr/local/lib/python2.6/site-packages/M2Crypto"
python -c "from M2Crypto import SSL; ctx = SSL.Context()"
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO USE M2Crypto. CHECK LINK." ; exit; fi
pause $1

cd ${APPSCALE_HOME}/downloads
wget http://pyyaml.org/download/pyyaml/PyYAML-3.09.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PYYAML. CHECK LINK." ; exit; fi
tar zxvf PyYAML-3.09.tar.gz 
cd PyYAML-3.09
python setup.py install

pause $1

# expat libraries for hypertable
cd ${APPSCALE_HOME}/downloads
wget http://downloads.sourceforge.net/project/expat/expat/2.0.1/expat-2.0.1.tar.gz?use_mirror=softlayer
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET EXPAT. " ; exit; fi
tar zxvf expat-2.0.1.tar.gz
cd expat-2.0.1/
./configure
make 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE EXPAT. " ; exit; fi
make install

pause $1

# Update /etc/hosts file here
echo "fe00::0 ip6-localnet">> /etc/hosts 
echo "ff00::0 ip6-mcastprefix" >> /etc/hosts
echo "ff02::1 ip6-allnodes" >> /etc/hosts
echo "ff02::2 ip6-allrouters" >>/etc/hosts
echo "ff02::3 ip6-allhosts" >>/etc/hosts

update-alternatives --install /bin/sh sh /bin/dash 1
update-alternatives --install /bin/sh sh /bin/bash 1
update-alternatives --config sh

echo "source /root/appscale/appscale.env" >> /root/.bashrc
echo "export PYTHON_EGG_CACHE=/tmp/.python_eggs" >> /root/.bashrc
echo "export PYTHONPATH=/usr/lib/python2.6/site-packages:/root/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py:/usr/local/lib/python2.6/site-packages:/usr/local/lib/python2.6:/usr/local/lib/python2.6/site-packages/M2Crypto:/usr/lib/python2.6/site-packages/thrift" >> /root/.bashrc
source ~/.bashrc
###########
# fpconst
###########
cd ${APPSCALE_HOME}/downloads/
wget http://pypi.python.org/packages/source/f/fpconst/fpconst-0.7.2.tar.gz#md5=10ba9e04129af23108d24c22c3a698b1
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET FPCONST. " ; exit; fi
tar zxvf fpconst-0.7.2.tar.gz 
cd fpconst-0.7.2
python setup.py install 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO INSTALL FPCONST. " ; exit; fi

pause $1
#############################
# modified version of SOAPpy
############################
cd ${APPSCALE_HOME}/downloads/
wget http://appscale.cs.ucsb.edu/appscale_files/SOAPpy-0.12.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET SOAP. " ; exit; fi
tar zxvf SOAPpy-0.12.0.tar.gz
cd SOAPpy-0.12.0
python setup.py install
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE SOAP. " ; exit; fi

pause $1
######################
# Setup tools
######################
cd ${APPSCALE_HOME}/downloads/
wget http://pypi.python.org/packages/source/s/setuptools/setuptools-0.6c11.tar.gz#md5=7df2a529a074f613b509fb44feefe74e 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET SETUPTOOLS. " ; exit; fi
tar xfvz setuptools-0.6c11.tar.gz 
cd setuptools-0.6c11
python setup.py build
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO BUILD SETUPTOOLS. " ; exit; fi
python setup.py install

################
# MySQL 64 bit
################
mkdir -p ${APPSCALE_HOME}/AppDB/mysql
cd ${APPSCALE_HOME}/AppDB/mysql
wget http://appscale.cs.ucsb.edu/appscale_files/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz -O  ${APPSCALE_HOME}/AppDB/mysql/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MYSQL. CHECK LINK." ; exit; fi
mv mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz mysql.tar.gz


pause $1
cd ${APPSCALE_HOME}/AppDB/mysql/
tar zxvf mysql.tar.gz
cd ${APPSCALE_HOME}/downloads/
# MySQL for python
wget http://downloads.sourceforge.net/project/mysql-python/mysql-python-test/1.2.3c1/MySQL-python-1.2.3c1.tar.gz?use_mirror=hivelocity
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET MYSQL-PYTHON. " ; exit; fi
tar zxvf MySQL-python-1.2.3c1.tar.gz
cd MySQL-python-1.2.3c1
echo "mysql_config = /root/appscale/AppDB/mysql/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23/bin/mysql_config" >> site.cfg
python setup.py build
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO BUILD MYSQL-PYTHON. " ; exit; fi
python setup.py install
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/root/appscale/AppDB/mysql/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23/lib/
echo "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/root/appscale/AppDB/mysql/mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23/lib/" >> ~/.bashrc
#################
# Thrift
#################
cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/thrift.tgz -O ${APPSCALE_HOME}/downloads/thrift.tgz
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD THRIFT. CHECK LINK." ; exit; fi
tar zxvf thrift.tgz
cd ${APPSCALE_HOME}/downloads/thrift
# move python to python2.4 in /usr/local/bin/
# softlink python2.5 to python
./bootstrap.sh
CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
$CONFIG_SHELL ./configure --without-csharp --disable-gen-java --without-java --without-ruby
make
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE THRIFT. " ; exit; fi
make install
cd ${APPSCALE_HOME}/downloads/thrift/lib/py
make install
cd ${APPSCALE_HOME}/downloads/thrift/lib/perl
perl Makefile.PL
make install
echo "include /usr/local/lib" >> /etc/ld.so.conf

pause $1
#rpm -Uvh ftp://download.fedora.redhat.com/pub/fedora/linux/releases/10/Everything/source/SRPMS/boost-1.34.1-17.fc10.src.rpm

#wget http://downloads.sourceforge.net/project/boost/boost/1.41.0/boost_1_41_0.tar.gz?use_mirror=cdnetworks-us-2

cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/rubygems-1.3.1.tgz -O ${APPSCALE_HOME}/downloads/rubygems-1.3.1.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD RUBY GEMS. CHECK LINK." ; exit; fi
tar zxvf rubygems-*.tgz
cd ${APPSCALE_HOME}/downloads/rubygems-1.3.1
ruby setup.rb

pause $1
gem update
pause $1
gem install god redgreen 
pause $1
gem install capistrano
gem install -v=2.3.4 rails
pause $1
gem install mongrel mongrel_cluster
pause $1
# this questionable since the file is not in BZR
cd ${APPSCALE_HOME}
mkdir -p /etc/nginx
mkdir -p /etc/nginx/sites-enabled/
cp AppLoadBalancer/config/nginx.conf /etc/nginx/
sed -i 's/user www-data;/user root;/g' /etc/nginx/nginx.conf
cp /usr/local/nginx/conf/mime.types /etc/nginx/
cp AppLoadBalancer/config/load-balancer.conf /etc/nginx/sites-enabled/
sed -i 's/false/off/g' /etc/nginx/sites-enabled/load-balancer.conf
mkdir -p /var/log/nginx/
touch /var/log/nginx/error.log

cp AppLoadBalancer/nginx /etc/init.d/nginx
chkconfig --add nginx
chkconfig nginx on
pause $1

echo "export PATH=\${PATH}:/var/lib/gems/1.8/bin" >> /root/.bashrc
export PATH=${PATH}:/var/lib/gems/1.8/bin

#TODO
cp /root/appscale/appscale_rhel /etc/init.d/appscale
chmod ugo+x /etc/init.d/appscale
chkconfig --add appscale
chkconfig appscale on

###################
# HADOOP
###################
cd ${APPSCALE_HOME}/AppDB
rm -rf hadoop-0.20.0
wget http://appscale.cs.ucsb.edu/appscale_files/hadoop-0.20.0.tar.gz -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HADOOP 0.20.0. CHECK LINK." ; exit; fi

tar xvzf hadoop-0.20.0.tar.gz
cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
echo "export APPSCALE_HOME=/root/appscale" >> ./conf/hadoop-env.sh
echo "export JAVA_HOME=/usr/lib/jvm/java-1.6.0-sun.x86_64" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_HOME=${APPSCALE_HOME}/AppDB/hadoop-0.20.0" >> ./conf/hadoop-env.sh
 
echo "export HBASE_HOME=${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_CLASSPATH=${HBASE_HOME}:${HBASE_HOME}/hbase/hbase-0.20.0-alpha.jar:${HBASE_HOME}/hbase/hbase-0.20.0-alpha-test.jar:${HBASE_HOME}/conf:${HBASE_HOME}/build/classes:${HADOOP_HOME}/build/classes" >> ./conf/hadoop-env.sh
 
echo "export CLASSPATH=${CLASSPATH}:${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ./conf/hadoop-env.sh
 
echo "export HADOOP_HEAPSIZE=2000" >> ./conf/hadoop-env.sh

cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
wget http://issues.apache.org/jira/secure/attachment/12405513/hadoop-includes-2.patch -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/hadoop-includes-2.patch
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO GET PATH. " ; exit; fi
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
pause $1
#########
# HBASE
#########
cd ${APPSCALE_HOME}/AppDB
rm -fdr ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha
cd ${APPSCALE_HOME}/AppDB/hbase
wget http://appscale.cs.ucsb.edu/appscale_files/hbase-0.20.0-alpha.tar.gz -O ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HBASE 0.20.0-alpha. CHECK LINK." ; exit; fi

tar zxvf hbase-0.20.0-alpha.tar.gz
echo "export APPSCALE_HOME=/root/appscale" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
echo "export JAVA_HOME=/usr/lib/jvm/java-1.6.0-sun.x86_64" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
 
echo "export HBASE_CLASSPATH=${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
 
echo "export HBASE_HEAPSIZE=2000" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
echo "export HBASE_MANAGES_ZK=FALSE" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh

rm  -f ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/hdfs/org/apache/hadoop/hdfs/DistributedFileSystem.java

cp -f ${APPSCALE_HOME}/AppDB/hbase/hbasefix/DistributedFileSystem.java ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/hdfs/org/apache/hadoop/hdfs/DistributedFileSystem.java             

cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0   
/root/appscale/downloads/apache-ant-1.7.1/bootstrap/bin/ant jar
cp build/hadoop-0.20.1-dev-core.jar ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/lib/hadoop-0.20.0-core.jar 

pause $1
############################
# Install Cassandra database
############################
echo "Install Cassandra for AppScale"
mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
cd ${APPSCALE_HOME}/AppDB/cassandra
wget http://appscale.cs.ucsb.edu/appscale_files/appscale_cassandra.06302009.tgz -O  ${APPSCALE_HOME}/AppDB/cassandra/appscale_cassandra.06302009.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD CASSANDRA. CHECK LINK." ; exit; fi
tar xzvf appscale_cassandra.06302009.tgz
rm -f appscale_cassandra.06302009.tgz
cd ${APPSCALE_HOME}/AppDB/cassandra/cassandra
ant build
mkdir /var/cassandra
chmod +x bin/cassandra

#############################
# Install Voldemort database
#############################
mkdir -p ${APPSCALE_HOME}/AppDB/voldemort
cd ${APPSCALE_HOME}/AppDB/voldemort
wget http://appscale.cs.ucsb.edu/appscale_files/appscale_voldemort.06302009.tgz -O ${APPSCALE_HOME}/AppDB/voldemort/appscale_voldemort.06302009.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD VOLDEMORT. CHECK LINK." ; exit; fi
tar xzvf appscale_voldemort.06302009.tgz
rm -f appscale_voldemort.06302009.tgz
cd ${APPSCALE_HOME}/AppDB/voldemort/voldemort
ant jar
mkdir /var/voldemort
chmod +x bin/voldemort

#sh ${APPSCALE_HOME}/ec2_scratch_install.sh

echo "export PATH=/usr/local/ec2-api-tools/bin/:\$PATH" >> /root/.bashrc
 
echo "export EC2_HOME=/usr/local/ec2-api-tools" >> /root/.bashrc
 
echo "export EC2_PRIVATE_KEY=/root/appscale/.appscale/certs/mykey.pem " >> /root/.bashrc

echo "export EC2_CERT=/root/appscale/.appscale/certs/mycert.pem  " >> /root/.bashrc

echo "export JAVA_HOME=/usr/lib/jvm/java-1.6.0-sun.x86_64" >> /root/.bashrc

source /root/.bashrc
mkdir -p ${APPSCALE_HOME}/logs

#################
# MongoDB 64bit
#################
cd ${APPSCALE_HOME}/AppDB/
wget http://appscale.cs.ucsb.edu/appscale_files/mongodb-linux-x86_64-1.0.0.tgz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MONGODB. CHECK LINK." ; exit; fi
tar zxvf mongodb-linux-x86_64-1.0.0.tgz
mv mongodb-linux-x86_64-1.0.0 mongodb
chmod +x mongodb/mongodb-linux-x86_64-1.0.0/bin/mongo mongodb//mongodb-linux-x86_64-1.0.0/bin/mongod
rm -f mongodb-linux-x86_64-1.0.0.tgz
easy_install -U setuptools
easy_install pymongo

pause $1
####################
# install memcached
####################
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/memcached-1.4.2.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MEMCAHCED. CHECK LINK." ; exit; fi
tar zxvf memcached-1.4.2.tar.gz
cd memcached-1.4.2
./configure
make
make install
cd ..
rm -rf memcached-1.4.2*

# install python lib for memcached
#apt-get -y install python-memcached
wget ftp://ftp.tummy.com/pub/python-memcached/python-memcached-1.45.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD python memcached. CHECK LINK." ; exit; fi
tar zxvf python-memcached-1.45.tar.gz
cd python-memcached-1.45
python setup.py build
python setup.py install
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO INSTALL python memcached. CHECK LINK." ; exit; fi

pause $1
# first install berkeley db
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/db-4.8.24.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD BERKDB. CHECK LINK." ; exit; fi
tar zxvf db-4.8.24.tar.gz
cd db-4.8.24
cd build_unix/
../dist/configure
make
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO BUILD BERKDB. " ; exit; fi
make install
cd ${APPSCALE_HOME}
rm -rf db-4.8.24*

pause $1
# first install berkeley db
cd ${APPSCALE_HOME}
wget http://kings.cs.ucsb.edu/appscale_files/db-4.7.25.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD BERKDB. CHECK LINK." ; exit; fi
tar zxvf db-4.7.25.tar.gz
cd db-4.7.25
cd build_unix/
../dist/configure --enable-cxx 
make 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO BUILD BERKDB. " ; exit; fi
make install
cd ${APPSCALE_HOME}
rm -rf db-4.7.25*
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/BerkeleyDB.4.7/lib/:/usr/local/lib/
echo "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/BerkeleyDB.4.7/lib:/usr/local/lib/" >> ~/.bashrc
echo "include /usr/local/lib" >> /etc/ld.so.conf
echo "include /usr/local/BerkeleyDB.4.7/lib" >> /etc/ld.so.conf
ldconfig

pause $1
# Install memcachedb
cd ${APPSCALE_HOME}/AppDB/memcachedb
wget http://kings.cs.ucsb.edu/appscale_files/memcachedb.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD MEMCACHEDB. CHECK LINK." ; exit; fi
tar zxvf memcachedb.tar.gz
cd memcachedb
./configure --enable-threads --with-libevent=/usr/local/lib
make
make install
pause $1
cd ${APPSCALE_HOME}/AppDB/memcachedb
rm -f memcachedb.tar.gz
cd ${APPSCALE_HOME}/downloads/
wget http://appscale.cs.ucsb.edu/appscale_files/Python-2.5.4.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PYTHON2.5. CHECK LINK." ; exit; fi
tar zxvf Python-2.5.4.tar.gz
cd Python-2.5.4
./configure
make 
make install 
pause $1
# make the default 2.6
cp -f /usr/local/bin/python2.6 /usr/local/bin/python

###################
# HYPERTABLE THRIFT
###################
cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/thrift-hypertable.tar.gz -O ${APPSCALE_HOME}/downloads/thrift-hypertable.tar.gz
if [ $? != 0 ]; then echo "UNABLE TO DOWNLOAD THRIFT-HYPERTABLE. CHECK LINK." ; exit; fi

tar zxfv thrift-hypertable.tar.gz
cd ${APPSCALE_HOME}/downloads/thrift-hypertable
./bootstrap.sh
CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
$CONFIG_SHELL ./configure --without-java
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

########################
# Hypertable
########################
cd ${APPSCALE_HOME}/downloads
wget http://appscale.cs.ucsb.edu/appscale_files/hyperic-sigar-1.6.0.tar.gz -O  ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0.tar.gz
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HYPERIC SIGAR. CHECK LINK." ; exit; fi

tar -xzvf hyperic-sigar-1.6.0.tar.gz
cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/include/*.h /usr/local/include
# 64 BIT
cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-amd64-linux.so ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-ia64-linux.so /usr/local/lib/

cd ${APPSCALE_HOME}/downloads
 wget http://downloads.sourceforge.net/project/boost/boost/1.41.0/boost_1_41_0.tar.gz?use_mirror=softlayer
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD BOOST. CHECK LINK." ; exit; fi
tar zxvf boost_1_41_0.tar.gz
cd boost_1_41_0
./bootstrap.sh
./bjam
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO BUILD BOOST. CHECK LINK." ; exit; fi
./bjam install
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
cmake -DHADOOP_INCLUDE_PATH=${HADOOP}/src/c++/install/include/ -DHADOOP_LIB_PATH=${HADOOP}/src/c++/install/lib/ -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=${HYPERTABLE} -DJAVA_INCLUDE_PATH=${JAVA_HOME}/include/ -DJAVA_INCLUDE_PATH2=${JAVA_HOME}/include/linux/  ../src/hypertable-0.9.2.5-alpha

rm -f ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableRangeMap.cc   

cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableRangeMap.cc  ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableRangeMap.cc 
rm -f ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableReader.cc

cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableReader.cc ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableReader.cc

make -j 2 
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE HYPERTABLE 0.9.2.5. " ; exit; fi

make install
if [ $? != 0 ]; then echo "FAILURE: UNABLE TO MAKE INSTALL HYPERTABLE 0.9.2.5. " ; exit; fi

echo "${HYPERTABLE}/0.9.2.5/lib" | tee -a /etc/ld.so.conf.d/hypertable.conf
ldconfig

##################
# /hypertable
#################

pause $1

ssh-keygen 
cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys

pause $1
cp /usr/bin/ruby /usr/bin/ruby1.8
#/usr/bin/ruby1.8 /usr/bin/god -c /root/appscale/AppLoadBalancer/config/global.god
# in case it was not installed before, seen issues where things are not installed
# the first time around
gem install god redgreen 
gem install -v=2.3.4 rails
gem install mongrel mongrel_cluster
pause $1
# Port 9000 is cslistener so replace it for RH
sed -i 's/grep 9000/grep cslistener/g' ${APPSCALE_HOME}/AppDB/wait_on_hadoop.py

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

######################
# Prime Python eggs
######################
python2.6 ${APPSCALE_HOME}/AppDB/appscale_server.py
pkill python

