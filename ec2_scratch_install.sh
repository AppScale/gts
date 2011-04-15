# EC2 Scratch Install Section
cd /root/
mkdir temp
cd temp
wget http://appscale.cs.ucsb.edu/appscale_files/ec2-api-tools-1.3-30349.zip
if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD EC2 API TOOLS.
CHECK LINK." ; exit; fi
wget http://appscale.cs.ucsb.edu/appscale_files/ec2-ami-tools-1.3-26357.zip
if [ $? = 1 ]; then echo "FAILURE: UNABLE TO DOWNLOAD EC2 API TOOLS.
CHECK LINK." ; exit; fi

apt-get -y install unzip
unzip ec2-api-tools-1.3-30349.zip
unzip ec2-ami-tools-1.3-26357.zip
apt-get -y remove unzip

mv ec2-api-tools-1.3-30349 ec2-api-tools
mv ec2-ami-tools-1.3-26357/* ec2-api-tools/ # should say directory not empty for bin and lib, that's fine
mv ec2-ami-tools-1.3-26357/bin/* ec2-api-tools/bin/
mv ec2-ami-tools-1.3-26357/lib/* ec2-api-tools/lib/
mv ec2-api-tools /usr/local/
rm -rf /root/temp

