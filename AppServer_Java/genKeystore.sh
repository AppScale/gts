cd ${APPSCALE_HOME}/AppServer_Java
rm -rf tempKey
mkdir -p tempKey
cd tempKey
cp ${APPSCALE_HOME}/.appscale/certs/mycert.pem .
cp ${APPSCALE_HOME}/.appscale/certs/mykey.pem .
cp ../ImportKey.class .
openssl x509 -in mycert.pem -inform PEM -out cert.der -outform DER
openssl pkcs8 -topk8 -nocrypt -in mykey.pem -inform PEM -out key.der -outform DER
java ImportKey key.der cert.der
cd ../
cp /root/keystore.ImportKey .
