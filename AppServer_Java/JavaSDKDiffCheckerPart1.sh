echo "Enter first SDK version: "
read sdk1
echo "Enter second SDK version: "
read sdk2
echo "Downloading $sdk1..."
wget http://googleappengine.googlecode.com/files/appengine-java-sdk-$sdk1.zip
echo "Downloading $sdk2..."
wget http://googleappengine.googlecode.com/files/appengine-java-sdk-$sdk2.zip
echo "Unzipping $sdk1..."
unzip appengine-java-sdk-$sdk1.zip
echo "Unzipping $sdk2..."
unzip appengine-java-sdk-$sdk2.zip
echo "Unjarring appengine-api-stubs.jar for $sdk1"
cd appengine-java-sdk-$sdk1/lib/impl
jar -xvf appengine-api-stubs.jar
echo "Unjarring appengine-api-stubs.jar for $sdk2"
cd ../../../appengine-java-sdk-$sdk2/lib/impl
jar -xvf appengine-api-stubs.jar
cd ../../..
echo "Unjarring appengine-api-tools.jar for $sdk1"
cd appengine-java-sdk-$sdk1/lib
jar -xvf appengine-tools-api.jar
echo "Unjarring appengine-api-tools.jar for $sdk2"
cd ../../appengine-java-sdk-$sdk2/lib
jar -xvf appengine-tools-api.jar
cd ../..

echo "Zipping up files that we alter for AppScale"
path_to_sdk1api=appengine-java-sdk-$sdk1/lib/impl/com/google/appengine
path_to_sdk1tools=appengine-java-sdk-$sdk1/lib/com/google/appengine/tools/development
zip -r $sdk1-classFiles.zip $path_to_sdk1api/* $path_to_sdk1tools/*

path_to_sdk2api=appengine-java-sdk-$sdk2/lib/impl/com/google/appengine
path_to_sdk2tools=appengine-java-sdk-$sdk2/lib/com/google/appengine/tools/development
zip -r $sdk2-classFiles.zip $path_to_sdk2api/* $path_to_sdk2tools/*

echo "Removing appengine sdk folders because when copying source code back, it will have the same directory name"

rm -r appengine-java-sdk-$sdk1
rm -r appengine-java-sdk-$sdk2

echo "Done packaging the class files that need to be decompiled for AppScale. You can"
echo "find both in {version}-classFiles.zip. In JD-GUI, change options to not include" 
echo "line numbers and meta data. Open these zip files in JD-GUI, then choose"
echo "Save All Sources. Take these 2 new zip files and copy them back to this directory."
echo "Then run part 2 of this shell script. Use the default save name JD-GUI provides."
