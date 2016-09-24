echo "Enter version of first sdk"
read sdk1
echo "Enter version of second sdk"
read sdk2

#This is the list of all the files we edit for AppScale. Add to this list if there are new files that we change. 
sdk1prefix=appengine-java-sdk-$sdk1
sdk2prefix=appengine-java-sdk-$sdk2
toolspath=/lib/com/google/appengine/tools/development
apipath=/lib/impl/com/google/appengine/api
sdk1files=( $sdk1prefix$toolspath/DevAppServerMain.java $sdk1prefix$apipath/blobstore/dev/BlobStorageFactory.java $sdk1prefix$apipath/blobstore/dev/BlobUploadSessionStorage.java $sdk1prefix$apipath/blobstore/dev/LocalBlobstoreService.java $sdk1prefix$apipath/datastore/dev/LocalDatastoreJob.java $sdk1prefix$apipath/datastore/dev/LocalDatastoreService.java $sdk1prefix$apipath/memcache/dev/LRU\$Chainable.java $sdk1prefix$apipath/memcache/dev/LocalMemcacheService$CacheEntry.java $sdk1prefix$apipath/memcache/dev/LocalMemcacheService\$Key.java $sdk1prefix$apipath/memcache/dev/LocalMemcacheService.java $sdk1prefix$apipath/taskqueue/dev/DevPullQueue.java $sdk1prefix$apipath/taskqueue/dev/DevPushQueue.java $sdk1prefix$apipath/taskqueue/dev/DevQueue.java $sdk1prefix$apipath/taskqueue/dev/LocalTaskQueue.java $sdk1prefix$apipath/taskqueue/dev/UrlFetchJob.java $sdk1prefix$apipath/users/dev/LocalLoginServlet.java $sdk1prefix$apipath/users/dev/LocalLogoutServlet.java $sdk1prefix$apipath/users/dev/LocalUserService.java $sdk1prefix$apipath/users/dev/LoginCookieUtils.java )

sdk2files=( $sdk2prefix$toolspath/DevAppServerMain.java $sdk2prefix$apipath/blobstore/dev/BlobStorageFactory.java $sdk2prefix$apipath/blobstore/dev/BlobUploadSessionStorage.java $sdk2prefix$apipath/blobstore/dev/LocalBlobstoreService.java $sdk2prefix$apipath/datastore/dev/LocalDatastoreJob.java $sdk2prefix$apipath/datastore/dev/LocalDatastoreService.java $sdk2prefix$apipath/memcache/dev/LRU\$Chainable.java $sdk2prefix$apipath/memcache/dev/LocalMemcacheService$CacheEntry.java $sdk2prefix$apipath/memcache/dev/LocalMemcacheService\$Key.java $sdk2prefix$apipath/memcache/dev/LocalMemcacheService.java $sdk2prefix$apipath/taskqueue/dev/DevPullQueue.java $sdk2prefix$apipath/taskqueue/dev/DevPushQueue.java $sdk2prefix$apipath/taskqueue/dev/DevQueue.java $sdk2prefix$apipath/taskqueue/dev/LocalTaskQueue.java $sdk2prefix$apipath/taskqueue/dev/UrlFetchJob.java $sdk2prefix$apipath/users/dev/LocalLoginServlet.java $sdk2prefix$apipath/users/dev/LocalLogoutServlet.java $sdk2prefix$apipath/users/dev/LocalUserService.java $sdk2prefix$apipath/users/dev/LoginCookieUtils.java )

arraylen=${#sdk1files[@]}

echo "Unzipping $sdk1 source"
unzip $sdk1-classFiles.src.zip
echo "Unzipping $sdk2 source" 
unzip $sdk2-classFiles.src.zip

echo "Diffing the files we care about"
#Now we're going to diff all the java files we care about
#and append the diffs to a file if there is any difference
resultfile=DiffResults.txt      
difffile=Diffs.txt
echo "" > $difffile
echo "" > $resultfile

for ((i=0; i<$arraylen; i++))
do
   echo "Comparing ${sdk1files[$i]} to ${sdk2files[$i]}"
   diff -q ${sdk1files[$i]} ${sdk2files[$i]}
   diffresult=$?
   if [ $diffresult -eq 0 ]
      then
         echo "No differences for ${sdk2files[$i]}" >> $resultfile
         echo "" >> $resultfile
   elif [ $diffresult -eq 1 ]
      then
         echo "DIFFERENCES FOUND for ${sdk2files[$i]}" >> $resultfile
         echo "" >> $resultfile
         diff -y -E -b -w ${sdk1files[$i]} ${sdk2files[$i]} >> $difffile
         echo "" >> $difffile
         echo "" >> $difffile
   else
      echo "ERROR diffing ${sdk1files[$i]} and ${sdk2files[$i]}" >> $resultfile
      echo "" >> $resultfile
   fi
done

echo "Finished comparing sdk's. Check $resultfile for general results and $difffile for detailed diffs"
