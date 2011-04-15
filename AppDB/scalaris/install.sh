echo "Installing scalaris"
apt-get -y install subversion
apt-get -y install erlang
apt-get -y install ant
cd /root/appscale/downloads/
# scalaris 0.2.0
svn checkout http://scalaris.googlecode.com/svn/trunk/ scalaris
cd scalaris
bash ./configure
# to change default port
patch -t -p 0 -i /root/appscale/AppDB/scalaris/patch/scalaris.patch
make
make install
ln -s /usr/local/etc/scalaris /etc/scalaris

cd /root/appscale/downloads/
svn checkout http://svn.json-rpc.org/trunk/python-jsonrpc
cd python-jsonrpc
# to support python 2.6
patch -t -p 0 -i /root/appscale/AppDB/scalaris/patch/python-jsonrpc.patch
python setup.py install
