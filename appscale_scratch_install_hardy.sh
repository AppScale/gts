#!/bin/bash -x

echo "hardy installation for appscale"

##############################################################################
# functions                                                                  #
##############################################################################

function check_hardy {
	RELEASE=`lsb_release -a | grep Codename | awk '{print $2}'`
	if [ "$RELEASE" != "hardy" ]; then
 	 echo "this is not hardy"
 	 exit;
	fi
}

function upgrade_distribution {
	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy main restricted" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy main restricted" >> /etc/apt/sources.list

	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy-updates main restricted" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy-updates main restricted" >> /etc/apt/sources.list

	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy universe" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy universe" >> /etc/apt/soure.list
	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy-updates universe" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy-updates universe" >> /etc/apt/sources.list

	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy multiverse" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy multiverse" >> /etc/apt/sources.list
	echo "deb http://us.archive.ubuntu.com/ubuntu/ hardy-updates multiverse" >> /etc/apt/sources.list
	echo "deb-src http://us.archive.ubuntu.com/ubuntu/ hardy-updates multiverse" >> /etc/apt/sources.list

	echo "deb http://security.ubuntu.com/ubuntu hardy-security main restricted" >> /etc/apt/sources.list
	echo "deb-src http://security.ubuntu.com/ubuntu hardy-security main restricted" >> /etc/apt/sources.list
	echo "deb http://security.ubuntu.com/ubuntu hardy-security universe" >> /etc/apt/sources.list
	echo "deb-src http://security.ubuntu.com/ubuntu hardy-security universe" >> /etc/apt/sources.list
	echo "deb http://security.ubuntu.com/ubuntu hardy-security multiverse" >> /etc/apt/sources.list
	echo "deb-src http://security.ubuntu.com/ubuntu hardy-security multiverse" >> /etc/apt/sources.list

	apt-get update
	apt-get -y upgrade
	apt-get update && apt-get upgrade
	apt-get dist-upgrade
}

function make_etc_hosts {
	echo "127.0.0.1       localhost"> /etc/hosts 
	echo "::1     ip6-localhost ip6-loopback">> /etc/hosts 
	echo "fe00::0 ip6-localnet">> /etc/hosts 
	echo "ff00::0 ip6-mcastprefix" >> /etc/hosts
	echo "ff02::1 ip6-allnodes" >> /etc/hosts
	echo "ff02::2 ip6-allrouters" >>/etc/hosts
	echo "ff02::3 ip6-allhosts" >>/etc/hosts
}

function install_programming_tools {
	apt-get -y install ssh openssl libssl-dev 
	apt-get -y install sun-java6-jdk 
	apt-get -y install python-m2crypto python-soappy python-yaml
  apt-get -y install python-mysqldb
	apt-get -y install make gcc g++ ntp cvs wget autoconf automake libtool bison flex 
	apt-get -y install zlib1g zlib1g-dev libzlib-ruby  
	apt-get -y install ruby1.8 libzip-ruby1.8 libboost-dev ruby1.8-dev libopenssl-ruby libopenssl-ruby1.8 libruby1.8 irb1.8 
	apt-get -y install rdoc iptables
	ln /usr/bin/ruby1.8 /usr/bin/ruby
	echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> /root/.bashrc
}

function install_python2_5 {
	apt-get -y install python2.5
	apt-get -y install python-mysqldb python-pycurl
	ln -s /usr/bin/python2.5 /usr/bin/python2.6 
}

function install_python2_6 {
	mkdir -p /root/pythonAppScale
	cd /root/pythonAppScale
	wget http://appscale.cs.ucsb.edu/appscale_files/Python-2.6.tgz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD PYTHON2.6. CHECK LINK." ; exit; fi
	tar zxvf Python-2.6.tgz
	cd /root/pythonAppScale/Python-2.6/
	./configure
	make
	make install
	cd ~
}

function install_programming_tools2 {
	apt-get -y install cmake 
	apt-get -y install libboost-filesystem-dev libboost-serialization-dev libboost-thread-dev 
	apt-get -y install libboost-program-options-dev libboost-iostreams-dev libboost-python-dev 
	apt-get -y install liblog4cpp5-dev libexpat1-dev libreadline5-dev 
	apt-get -y install libncurses5-dev libevent-dev 
	apt-get -y install build-essential automake pkg-config doxygen graphviz rsync lsof
	apt-get -y install make tcl-dev libbz2-dev libreadline-dev libgdbm-dev python-tk byacc tk8.4-dev 
	apt-get -y install sun-java5-jdk ant 
	apt-get -y install libdb4.6++-dev	# for hardy .., for jaunty use libdb4.7++-dev.  
}

function remove_java_tools {
	apt-get -y remove gij ecj
}

function update_alternatives {
	update-alternatives --install /bin/sh sh /bin/dash 1
	update-alternatives --install /bin/sh sh /bin/bash 1
	update-alternatives --config sh
}

function make_root_dir {
	export APPSCALE_HOME=/root/appscale
	#echo "source /root/appscale/appscale.env" >> /root/.bashrc
	echo "export APPSCALE_HOME=/root/appscale" >> /root/.bashrc
	mkdir ${APPSCALE_HOME}
}

function set_pythonpath_for_python2_6 {
	echo "export PYTHONPATH=/usr/local/python-2.6/lib/python26.zip:/usr/local/python-2.6/lib/python2.6:/usr/local/python-2.6/lib/python2.6/plat-linux2:/usr/local/python-2.6/lib/python2.6/lib-tk:/usr/local/python-2.6/lib/python2.6/lib-dynload:/usr/local/python-2.6/lib/python2.6/site-packages:/usr/lib/python2.6/site-packages:/var/lib/python-support:/usr/share/python-support/python-yaml:/usr/share/python-support:/usr/share/python-support/python-m2crypto:/usr/share/python-support/python-soappy:/root/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py:/usr/lib/python-support/python-m2crypto/python2.6/M2Crypto/" >> /root/.bashrc
	source /root/.bashrc
}

function set_pythonpath_for_python2_5 { 
	echo "export PYTHONPATH=/usr/local/python-2.5/lib/python25.zip:/usr/local/python-2.5/lib/python2.5:/usr/local/python-2.5/lib/python2.5/plat-linux2:/usr/local/python-2.5/lib/python2.5/lib-tk:/usr/local/python-2.5/lib/python2.5/lib-dynload:/usr/local/python-2.5/lib/python2.5/site-packages:/usr/lib/python2.5/site-packages:/var/lib/python-support:/usr/share/python-support/python-yaml:/usr/share/python-support:/usr/share/python-support/python-m2crypto:/usr/share/python-support/python-soappy:/root/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py:/usr/lib/python-support/python-m2crypto/python2.5/M2Crypto/" >> /root/.bashrc
	source /root/.bashrc
}

function download_appscale_code {
	apt-get -y install bzr
	cd /root
	bzr branch lp:~appscale-maintainers/appscale/appscale
}

function install_thrift {
	cd ${APPSCALE_HOME}
	mkdir downloads
	cd ${APPSCALE_HOME}/downloads
	wget http://appscale.cs.ucsb.edu/appscale_files/thrift.tgz -O ${APPSCALE_HOME}/downloads/thrift.tgz
	if [ $? = 1 ]; then echo "UNABLE TO DOWNLOAD THRIFT. CHECK LINK." ; exit; fi

	tar zxfv thrift.tgz
	cd ${APPSCALE_HOME}/downloads/thrift
	./bootstrap.sh
	CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
	$CONFIG_SHELL ./configure --without-csharp --disable-gen-java --without-java
	make
	make install
	cd ${APPSCALE_HOME}/downloads/thrift/lib/py
	make install
	cd ${APPSCALE_HOME}/downloads/thrift/lib/rb
	make install
	cd ${APPSCALE_HOME}/downloads/thrift/lib/perl
	perl Makefile.PL
	make install
	echo "include /usr/local/lib" >> /etc/ld.so.conf
}

function install_thrift_hypertable {
	cd ${APPSCALE_HOME}/downloads
	wget http://appscale.cs.ucsb.edu/appscale_files/thrift-hypertable.tar.gz -O ${APPSCALE_HOME}/downloads/thrift-hypertable.tar.gz
	if [ $? = 1 ]; then echo "UNABLE TO DOWNLOAD THRIFT-HYPERTABLE. CHECK LINK." ; exit; fi

	tar zxfv thrift-hypertable.tar.gz
	cd ${APPSCALE_HOME}/downloads/thrift-hypertable
	./bootstrap.sh
	CONFIG_SHELL=/bin/bash; export CONFIG_SHELL
	$CONFIG_SHELL ./configure 
	make
	make install
	cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/py
	make install
	cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/rb
	make install
	cd ${APPSCALE_HOME}/downloads/thrift-hypertable/lib/perl
	perl Makefile.PL
	make install
}

function install_ruby_gem {
	cd ${APPSCALE_HOME}/downloads
	wget http://appscale.cs.ucsb.edu/appscale_files/rubygems-1.3.1.tgz -O ${APPSCALE_HOME}/downloads/rubygems-1.3.1.tgz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD RUBY GEMS. CHECK LINK." ; exit; fi

	tar zxvf rubygems-*.tgz
	cd ${APPSCALE_HOME}/downloads/rubygems-1.3.1
	ruby setup.rb
	ln -sf /usr/bin/gem1.8 /usr/bin/gem
	echo "export PATH=\${PATH}:/var/lib/gems/1.8/bin" >> /root/.bashrc
	export PATH=${PATH}:/var/lib/gems/1.8/bin
}

function install_god {
	gem update
	gem install god
}

function install_rails {
	gem install -v=2.0.2 rails
	apt-get -y install nginx haproxy
	gem install mongrel mongrel_cluster

	cd ${APPSCALE_HOME}
	cp AppLoadBalancer/config/haproxy.cfg /etc/haproxy/
	cp AppLoadBalancer/config/nginx.conf /etc/nginx/
	cp AppLoadBalancer/config/load-balancer.conf /etc/nginx/sites-enabled/

	cp /root/appscale/haproxy /etc/init.d/
	cd /etc/init.d
	chmod ugo+x haproxy
	update-rc.d haproxy defaults
}

function install_sigar {
	cd ${APPSCALE_HOME}/downloads
	wget http://appscale.cs.ucsb.edu/appscale_files/hyperic-sigar-1.6.0.tar.gz -O  ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0.tar.gz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOADi HYPERIC SIGAR. CHECK LINK." ; exit; fi

	tar -xzvf hyperic-sigar-1.6.0.tar.gz
	cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/include/*.h /usr/local/include
	# 64 BIT
	cp ${APPSCALE_HOME}/downloads/hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-amd64-linux.so hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-ia64-linux.so /usr/local/lib/
	# 32 BIT (comment the above line)
	#cp hyperic-sigar-1.6.0/sigar-bin/lib/libsigar-x86-linux.so /usr/local/lib/
	ldconfig
}

function install_capistrano {
	gem install -y capistrano
}

function install_hadoop {
	cd ${APPSCALE_HOME}/AppDB
	rm -rf hadoop-0.20.0
	wget http://appscale.cs.ucsb.edu/appscale_files/hadoop-0.20.0.tar.gz -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0.tar.gz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HADOOP 0.20.0. CHECK LINK." ; exit; fi

	tar xvzf hadoop-0.20.0.tar.gz
	cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
	echo "export APPSCALE_HOME=/root/appscale" >> ./conf/hadoop-env.sh
	echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> ./conf/hadoop-env.sh
	echo "export HADOOP_HOME=${APPSCALE_HOME}/AppDB/hadoop-0.20.0" >> ./conf/hadoop-env.sh
	echo "export HBASE_HOME=${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha" >> ./conf/hadoop-env.sh
	echo "export HADOOP_CLASSPATH=${HBASE_HOME}:${HBASE_HOME}/hbase/hbase-0.20.0-alpha.jar:${HBASE_HOME}/hbase/hbase-0.20.0-alpha-test.jar:${HBASE_HOME}/conf:${HBASE_HOME}/build/classes:${HADOOP_HOME}/build/classes" >> ./conf/hadoop-env.sh
	echo "export CLASSPATH=${CLASSPATH}:${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ./conf/hadoop-env.sh
	echo "export HADOOP_HEAPSIZE=2000" >> ./conf/hadoop-env.sh

	cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0
	wget http://issues.apache.org/jira/secure/attachment/12405513/hadoop-includes-2.patch -O ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/hadoop-includes-2.patch
	patch -p0 < hadoop-includes-2.patch
	cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/utils
	sh configure
	make

	sed -i "s/CXXFLAGS = -g/CXXFLAGS = -fPIC -g/g" ./Makefile
	make clean
	make
	make install
	cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/pipes
	sh configure
	make
	make install
	echo "${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/c++/install/lib" | tee -a /etc/ld.so.conf.d/hadoop.conf
	ldconfig          
}

function install_hypertable {
	cd ${APPSCALE_HOME}/AppDB/hypertable
	rm -rf src build 0.9.2.5
	mkdir -p src build
	cd ${APPSCALE_HOME}/AppDB/hypertable/src
	wget http://appscale.cs.ucsb.edu/appscale_files/hypertable-0.9.2.5-alpha-src.tar.gz -O ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha-src.tar.gz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HYPERTABLE 0.9.2.5. CHECK LINK." ; exit; fi

	tar xvzf hypertable-0.9.2.5-alpha-src.tar.gz
	export HYPERTABLE=${APPSCALE_HOME}/AppDB/hypertable
	export HADOOP=${APPSCALE_HOME}/AppDB/hadoop-0.20.0
	cd ${APPSCALE_HOME}/AppDB/hypertable/build
	cmake -DHADOOP_INCLUDE_PATH=${HADOOP}/src/c++/install/include/ -DHADOOP_LIB_PATH=${HADOOP}/src/c++/install/lib/ -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=${HYPERTABLE} -DJAVA_INCLUDE_PATH=/usr/lib/jvm/java-6-sun/include/ -DJAVA_INCLUDE_PATH2=/usr/lib/jvm/java-6-sun/include/linux/  ../src/hypertable-0.9.2.5-alpha

	cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableRangeMap.cc  ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableRangeMap.cc 
	cp ${APPSCALE_HOME}/AppDB/hypertable/hypertablefix/TableReader.cc ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/contrib/cc/MapReduce/TableReader.cc

	make -j 4 
	make install
	echo "${HYPERTABLE}/0.9.2.5/lib" | tee -a /etc/ld.so.conf.d/hypertable.conf
	ldconfig
}

function install_hbase {
	cd ${APPSCALE_HOME}/AppDB
	rm -fdr ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha
	cd ${APPSCALE_HOME}/AppDB/hbase
	wget http://appscale.cs.ucsb.edu/appscale_files/hbase-0.20.0-alpha.tar.gz -O ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha.tar.gz
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD HBASE 0.20.0-alpha. CHECK LINK." ; exit; fi

	tar zxvf hbase-0.20.0-alpha.tar.gz
	echo "export APPSCALE_HOME=/root/appscale" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
	echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
	echo "export HBASE_CLASSPATH=${APPSCALE_HOME}/AppDB/hadoop-0.20.0/build/classes" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
	echo "export HBASE_HEAPSIZE=2000" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh
	echo "export HBASE_MANAGES_ZK=FALSE" >> ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/conf/hbase-env.sh

	cp ${APPSCALE_HOME}/AppDB/hbase/hbasefix/DistributedFileSystem.java ${APPSCALE_HOME}/AppDB/hadoop-0.20.0/src/hdfs/org/apache/hadoop/hdfs/DistributedFileSystem.java 		
	cd ${APPSCALE_HOME}/AppDB/hadoop-0.20.0		
	ant jar
	cp build/hadoop-0.20.1-dev-core.jar ${APPSCALE_HOME}/AppDB/hbase/hbase-0.20.0-alpha/lib/hadoop-0.20.0-core.jar 
}

function install_init_appscale {
	cp /root/appscale/appscale /etc/init.d/
	cd /etc/init.d
	chmod ugo+x appscale
	update-rc.d appscale defaults
}

function install_ec2_tools {
	#On the machine from which you will upload and manipulate AppScale/Eucalyptus:
	sh ${APPSCALE_HOME}/ec2_scratch_install.sh
	echo "source /root/appscale/appscale.env" >> /root/.bashrc
	echo "export PATH=/usr/local/ec2-api-tools/bin/:\$PATH" >> /root/.bashrc
	echo "export EC2_HOME=/usr/local/ec2-api-tools" >> /root/.bashrc
	echo "export EC2_PRIVATE_KEY=/root/appscale/.appscale/certs/mykey.pem " >> /root/.bashrc
	echo "export EC2_CERT=/root/appscale/.appscale/certs/mycert.pem  " >> /root/.bashrc
	echo "export JAVA_HOME=/usr/lib/jvm/java-6-sun" >> /root/.bashrc
}

function install_cassandra {
	source /root/.bashrc
	local TARBALL=appscale_cassandra.06302009.tgz
	mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
	cd ${APPSCALE_HOME}/AppDB/cassandra
	wget http://appscale.cs.ucsb.edu/appscale_files/${TARBALL} -O  ${APPSCALE_HOME}/AppDB/cassandra/${TARBALL}
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD ${TARBALL}. CHECK LINK." ; exit; fi
	tar xzvf ${TARBALL}; rm -f ${TARBALL}
	cd ${APPSCALE_HOME}/AppDB/cassandra/cassandra
	ant build
	mkdir /var/cassandra
	chmod +x bin/cassandra
}

function install_voldemort {
	local TARBALL=appscale_voldemort.06302009.tgz
	mkdir -p ${APPSCALE_HOME}/AppDB/voldemort
	cd ${APPSCALE_HOME}/AppDB/voldemort
	wget http://appscale.cs.ucsb.edu/appscale_files/${TARBALL} -O ${APPSCALE_HOME}/AppDB/voldemort/${TARBALL}
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD ${TARBALL}. CHECK LINK." ; exit; fi
	tar xzvf ${TARBALL}; rm ${TARBALL}
	cd ${APPSCALE_HOME}/AppDB/voldemort/voldemort
	ant jar
	mkdir /var/voldemort
	chmod +x bin/voldemort
}

function install_mysql {
	# MySQL 64 bit
	local TARBALL=mysql-cluster-gpl-6.3.20-linux-x86_64-glibc23.tar.gz
	mkdir -p ${APPSCALE_HOME}/AppDB/mysql
	cd ${APPSCALE_HOME}/AppDB/mysql
	wget http://appscale.cs.ucsb.edu/appscale_files/${TARBALL} -O  ${APPSCALE_HOME}/AppDB/mysql/${TARBALL}
	if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD ${TARBALL}. CHECK LINK." ; exit; fi
	mv ${TARBALL} mysql.tar.gz

	apt-get -y remove mysql-server mysql-common mysql-client
}

function create_ssh_keys {
	ssh-keygen 
	cat /root/.ssh/id_rsa.pub > /root/.ssh/authorized_keys
}

function change_controller_for_hardy {
	cd ${APPSCALE_HOME}/AppController
	mkdir backup
	FILES=`ls *.rb`
	for file in ${FILES}; do
  	sed 's/python2.6/python2.5/g' ${file} > ${file}.new
  	mv ${file} backup
  	mv ${file}.new ${file}
	done
}

function change_python_path_in_djinnserver {
	local DJINN_SERVER=${APPSCALE_HOME}/AppController/djinnServer.rb
	sed 's/python2.6/python2.5/g' ${DJINN_SERVER} > /tmp/djinnServer.rb
	mv ${DJINN_SERVER} ${DJINN_SERVER}.org
	mv /tmp/djinnServer.rb ${DJINN_SERVER}
}

##############################################################################

# Start Install AppScale 
echo "Start Install AppScale .. "

export APPSCALE_HOME=/root/appscale

check_hardy
upgrade_distribution
make_etc_hosts
install_programming_tools | tee install_programming_tools.log
##install_python2_6 | tee install_python2_6.log
install_python2_5 | tee install_python2_5.log
install_programming_tools2 | tee install_programming_tools2.log
remove_java_tools
update_alternatives

download_appscale_code | tee download_appscale_code.log
make_root_dir

##set_pythonpath_for_python2_6
set_pythonpath_for_python2_5

install_thrift
install_thrift_hypertable

install_ruby_gem
install_god
install_rails
install_sigar
install_capistrano

install_init_appscale
install_ec2_tools

# install datastores 
install_hadoop | tee install_hadoop.log
install_hypertable | tee install_hypertable.log
install_hbase | tee install_hbase.log
install_cassandra | tee install_cassandra.log
install_voldemort | tee install_voldemort.log
install_mysql | tee install_mysql.log

#change_controller_for_hardy
change_python_path_in_djinnserver
create_ssh_keys

