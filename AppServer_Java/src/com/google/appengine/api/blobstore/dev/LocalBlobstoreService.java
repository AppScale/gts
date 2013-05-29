package com.google.appengine.api.blobstore.dev;


import java.io.IOException;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Arrays;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.google.appengine.api.blobstore.BlobInfo;
import com.google.appengine.api.blobstore.BlobInfoFactory;
import com.google.appengine.api.blobstore.BlobKey;
import com.google.appengine.api.blobstore.BlobstoreServicePb;
import com.google.appengine.api.datastore.Blob;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityNotFoundException;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;
import com.google.appengine.repackaged.com.google.common.util.Base64;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiProxy;
import com.google.appengine.repackaged.com.google.common.io.BaseEncoding;

@ServiceProvider(LocalRpcService.class)
public final class LocalBlobstoreService extends AbstractLocalRpcService
{
    private static final Logger      logger                    = Logger.getLogger(LocalBlobstoreService.class.getName());
    public static final String       BACKING_STORE_PROPERTY    = "blobstore.backing_store";
    public static final String       NO_STORAGE_PROPERTY       = "blobstore.no_storage";
    public static final String       PACKAGE                   = "blobstore";
    public static final String       GOOGLE_STORAGE_KEY_PREFIX = "encoded_gs_key:";
    static final String              UPLOAD_URL_PREFIX         = "/_ah/upload/";
    private BlobStorage              blobStorage;
    private BlobUploadSessionStorage uploadSessionStorage;
    /*
     * AppScale - removed serverHostName and serverPort declarations
     */

    /*
     * AppScale - added declarations below
     */
    private DatastoreService         datastoreService;
    Blob                             blockCache                = null;
    private String                   blockKeyCache;
    private static final String      BLOB_PORT                 = "6106";
    public static final long         MAX_BLOB_FETCH_SIZE       = 1015808L;

    public String getPackage()
    {
        return "blobstore";
    }

    public void init( LocalServiceContext context, Map<String, String> properties )
    {
        /*
         * AppScale - replaced body of init method
         */
        logger.fine("Initializing blobstore service");
        this.uploadSessionStorage = new BlobUploadSessionStorage();
        datastoreService = DatastoreServiceFactory.getDatastoreService();
        if (datastoreService == null)
        {
            logger.severe("DatastoreService is null, blobstore may have issues");
        }
        BlobStorageFactory.setDatastoreBlobStorage();
        this.blobStorage = BlobStorageFactory.getBlobStorage();
    }

    public void start()
    {}

    public void stop()
    {
        if ((this.blobStorage instanceof MemoryBlobStorage)) ((MemoryBlobStorage)this.blobStorage).deleteAllBlobs();
    }

    public BlobstoreServicePb.CreateUploadURLResponse createUploadURL( LocalRpcService.Status status, BlobstoreServicePb.CreateUploadURLRequest request )
    {
        BlobUploadSession session = new BlobUploadSession(request.getSuccessPath());
        if (request.hasMaxUploadSizePerBlobBytes())
        {
            session.setMaxUploadSizeBytesPerBlob(request.getMaxUploadSizePerBlobBytes());
        }
        if (request.hasMaxUploadSizeBytes())
        {
            session.setMaxUploadSizeBytes(request.getMaxUploadSizeBytes());
        }
        String sessionId = this.uploadSessionStorage.createSession(session);

        /*
         * AppScale - changed upload URL to NGINX address and port
         */
        BlobstoreServicePb.CreateUploadURLResponse response = new BlobstoreServicePb.CreateUploadURLResponse();
        String url = "http://" + System.getProperty("NGINX_ADDR") + ":" + BLOB_PORT + "/" + "_ah/upload/" + System.getProperty("APPLICATION_ID") + "/" + sessionId;
        logger.fine("UploadURL set to [" + url + "]");
        response.setUrl(url);

        return response;
    }

    public ApiBasePb.VoidProto deleteBlob( LocalRpcService.Status status, final BlobstoreServicePb.DeleteBlobRequest request )
    {
        logger.fine("deleteBlob called with request [" + request + "]");
        AccessController.doPrivileged(new PrivilegedAction<Object>()
        {
            public Object run()
            {
                for (String blobKeyString : request.blobKeys())
                {
                    BlobKey blobKey = new BlobKey(blobKeyString);
                    if (LocalBlobstoreService.this.blobStorage.hasBlob(blobKey))
                    {
                        try
                        {
                            LocalBlobstoreService.this.blobStorage.deleteBlob(blobKey);
                        }
                        catch (IOException ex)
                        {
                            LocalBlobstoreService.logger.log(Level.WARNING, "Could not delete blob: " + blobKey, ex);
                            throw new ApiProxy.ApplicationException(BlobstoreServicePb.BlobstoreServiceError.ErrorCode.INTERNAL_ERROR.getValue(), ex.toString());
                        }
                    }
                }
                return null;
            }
        });
        return new ApiBasePb.VoidProto();
    }

    public BlobstoreServicePb.FetchDataResponse fetchData( LocalRpcService.Status status, BlobstoreServicePb.FetchDataRequest request )
    {
        /*
         * AppScale - changed fetchData method to use AppScale implementation
         */
        logger.finer("fetchData called");
        if (request.getStartIndex() < 0L)
        {
            throw new ApiProxy.ApplicationException(BlobstoreServicePb.BlobstoreServiceError.ErrorCode.DATA_INDEX_OUT_OF_RANGE.getValue(), "Start index must be >= 0.");
        }

        if (request.getEndIndex() < request.getStartIndex())
        {
            throw new ApiProxy.ApplicationException(BlobstoreServicePb.BlobstoreServiceError.ErrorCode.DATA_INDEX_OUT_OF_RANGE.getValue(), "End index must be >= startIndex.");
        }

        long fetchSize = request.getEndIndex() - request.getStartIndex() + 1L;
        if (fetchSize > MAX_BLOB_FETCH_SIZE)
        {
            throw new ApiProxy.ApplicationException(BlobstoreServicePb.BlobstoreServiceError.ErrorCode.BLOB_FETCH_SIZE_TOO_LARGE.getValue(), "Blob fetch size too large.");
        }

        BlobstoreServicePb.FetchDataResponse response = new BlobstoreServicePb.FetchDataResponse();
        BlobKey blobKey = new BlobKey(request.getBlobKey());
        BlobInfo blobInfo = new BlobInfoFactory().loadBlobInfo(blobKey);
        if (blobInfo == null) throw new ApiProxy.ApplicationException(BlobstoreServicePb.BlobstoreServiceError.ErrorCode.BLOB_NOT_FOUND.getValue(), "Blob not found.");
        long endIndex;
        if (request.getEndIndex() > blobInfo.getSize() - 1L)
            endIndex = blobInfo.getSize() - 1L;
        else
        {
            endIndex = request.getEndIndex();
        }
        if (request.getStartIndex() > endIndex)
        {
            response.setData("");
        }
        else
        {
            long startIndex = request.getStartIndex();
            endIndex = request.getEndIndex();
            long block_count = startIndex / MAX_BLOB_FETCH_SIZE;
            long block_modulo = startIndex % MAX_BLOB_FETCH_SIZE;

            long block_count_end = endIndex / MAX_BLOB_FETCH_SIZE;

            String block_key = blobKey.getKeyString() + "__" + block_count;
            Key key = KeyFactory.createKey("__BlobChunk__", block_key);
            if (this.blockKeyCache != key.toString())
            {
                Entity entity;
                try
                {
                    entity = datastoreService.get(key);
                    this.blockCache = (Blob)entity.getProperty("block");
                    this.blockKeyCache = key.toString();

                }
                catch (EntityNotFoundException e)
                {
                    e.printStackTrace();
                }
            }
            byte[] bytes = blockCache.getBytes();
            // # Matching boundaries, start and end are within one fetch
            if (block_count_end == block_count)
            {
                // Is there enough data to satisfy fetch_size bytes?

                if ((bytes.length - block_modulo) >= fetchSize)
                {
                    byte[] data = Arrays.copyOfRange(bytes, (int)block_modulo, (int)(block_modulo + fetchSize));
                    response.setDataAsBytes(data);
                    return response;

                }
                else
                {// Return whatever is left, not fetch_size amount
                    byte[] data = Arrays.copyOfRange(bytes, (int)block_modulo, bytes.length);
                    response.setDataAsBytes(data);
                    return response;
                }
            }
            byte[] data = Arrays.copyOfRange(bytes, (int)block_modulo, bytes.length);
            int data_size = data.length;

            // Must fetch the next block
            block_key = blobKey.getKeyString() + "__" + (block_count + 1);
            Key key2 = KeyFactory.createKey("__BlobChunk__", block_key);
            try
            {
                Entity block2 = datastoreService.get(key);
                this.blockCache = (Blob)block2.getProperty("block");
                this.blockKeyCache = key2.toString();

            }
            catch (EntityNotFoundException e)
            {
                e.printStackTrace();
            }
            byte[] newData = new byte[(int)(fetchSize)];
            System.arraycopy(data, 0, newData, 0, data_size);
            System.arraycopy(blockCache, 0, newData, data_size, (int)(fetchSize - data_size));
            response.setDataAsBytes(newData);
        }
        return response;
    }

    public BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse createEncodedGoogleStorageKey( LocalRpcService.Status status, BlobstoreServicePb.CreateEncodedGoogleStorageKeyRequest request )
    {
        String encoded = BaseEncoding.base64Url().omitPadding().encode(request.getFilename().getBytes());
        BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse response = new BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse();
        response.setBlobKey(GOOGLE_STORAGE_KEY_PREFIX + encoded);
        return response;
    }
}
