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

@ServiceProvider(LocalRpcService.class)
public final class LocalBlobstoreService extends AbstractLocalRpcService {
    private static final Logger logger = Logger
            .getLogger(LocalBlobstoreService.class.getName());
    public static final String BACKING_STORE_PROPERTY = "blobstore.backing_store";
    public static final String NO_STORAGE_PROPERTY = "blobstore.no_storage";
    public static final String PACKAGE = "blobstore";
    public static final String GOOGLE_STORAGE_KEY_PREFIX = "encoded_gs_key:";
    static final String UPLOAD_URL_PREFIX = "/_ah/upload/";
    private BlobStorage blobStorage;
    private BlobUploadSessionStorage uploadSessionStorage;
    // private String serverHostName;
    // private int serverPort;

    // add for AppScale
    private DatastoreService datastoreService;
    Blob blockCache = null;
    private String blockKeyCache;
    private static final String BLOB_PORT = "6106";
    public static final long MAX_BLOB_FETCH_SIZE = 1015808L;

    public String getPackage() {
        return "blobstore";
    }

    public void init(LocalServiceContext context, Map<String, String> properties) {
        this.uploadSessionStorage = new BlobUploadSessionStorage();
        datastoreService = DatastoreServiceFactory.getDatastoreService();
        if (datastoreService == null){
            System.out.println("datastoreService is null");
        }
        // String noStorage = (String)properties.get("blobstore.no_storage");
        // if ((noStorage != null) &&
        // (Boolean.valueOf(noStorage).booleanValue())) {
        // BlobStorageFactory.setMemoryBlobStorage();
        // } else {
        // String filePath = (String)properties.get("blobstore.backing_store");
        // File file;
        // if (filePath != null)
        // file = new File(filePath);
        // else {
        // file =
        // GenerationDirectory.getGenerationDirectory(context.getLocalServerEnvironment().getAppDir());
        // }
        //
        // file.mkdirs();
        // BlobStorageFactory.setFileBlobStorage(file);
        // }
        // this.blobStorage = BlobStorageFactory.getBlobStorage();
        // this.serverHostName =
        // context.getLocalServerEnvironment().getHostName();
        // this.serverPort = context.getLocalServerEnvironment().getPort();
        BlobStorageFactory.setDatastoreBlobStorage();
        this.blobStorage = BlobStorageFactory.getBlobStorage();
    }

    public void start() {
    }

    public void stop() {
        if ((this.blobStorage instanceof MemoryBlobStorage))
            ((MemoryBlobStorage) this.blobStorage).deleteAllBlobs();
    }

    public BlobstoreServicePb.CreateUploadURLResponse createUploadURL(
            LocalRpcService.Status status,
            BlobstoreServicePb.CreateUploadURLRequest request) {
        BlobUploadSession session = new BlobUploadSession(
                request.getSuccessPath());
        if (request.hasMaxUploadSizePerBlobBytes()) {
            session.setMaxUploadSizeBytesPerBlob(request
                    .getMaxUploadSizePerBlobBytes());
        }
        if (request.hasMaxUploadSizeBytes()) {
            session.setMaxUploadSizeBytes(request.getMaxUploadSizeBytes());
        }
        String sessionId = this.uploadSessionStorage.createSession(session);

        BlobstoreServicePb.CreateUploadURLResponse response = new BlobstoreServicePb.CreateUploadURLResponse();
        // String url = String.format("http://%s:%d%s%s", new Object[] {
        // this.serverHostName, Integer.valueOf(this.serverPort),
        // "/_ah/upload/", sessionId });
        String url = "http://" + System.getProperty("NGINX_ADDR") + ":"
                + BLOB_PORT + "/" + "_ah/upload/"
                + System.getProperty("APPLICATION_ID") + "/" + sessionId;
        response.setUrl(url);

        return response;
    }

    public ApiBasePb.VoidProto deleteBlob(LocalRpcService.Status status,
            final BlobstoreServicePb.DeleteBlobRequest request) {
        AccessController.doPrivileged(new PrivilegedAction<Object>() {
            public Object run() {
                for (String blobKeyString : request.blobKeys()) {
                    BlobKey blobKey = new BlobKey(blobKeyString);
                    if (LocalBlobstoreService.this.blobStorage.hasBlob(blobKey)) {
                        try {
                            LocalBlobstoreService.this.blobStorage
                                    .deleteBlob(blobKey);
                        } catch (IOException ex) {
                            LocalBlobstoreService.logger.log(Level.WARNING,
                                    "Could not delete blob: " + blobKey, ex);
                            throw new ApiProxy.ApplicationException(
                                    BlobstoreServicePb.BlobstoreServiceError.ErrorCode.INTERNAL_ERROR
                                            .ordinal(), ex.toString());
                        }
                    }
                }
                return null;
            }
        });
        return new ApiBasePb.VoidProto();
    }

    public BlobstoreServicePb.FetchDataResponse fetchData(
            LocalRpcService.Status status,
            BlobstoreServicePb.FetchDataRequest request) {
        if (request.getStartIndex() < 0L) {
            throw new ApiProxy.ApplicationException(
                    BlobstoreServicePb.BlobstoreServiceError.ErrorCode.DATA_INDEX_OUT_OF_RANGE
                            .ordinal(), "Start index must be >= 0.");
        }

        if (request.getEndIndex() < request.getStartIndex()) {
            throw new ApiProxy.ApplicationException(
                    BlobstoreServicePb.BlobstoreServiceError.ErrorCode.DATA_INDEX_OUT_OF_RANGE
                            .ordinal(), "End index must be >= startIndex.");
        }

        long fetchSize = request.getEndIndex() - request.getStartIndex() + 1L;
        if (fetchSize > MAX_BLOB_FETCH_SIZE) {
            throw new ApiProxy.ApplicationException(
                    BlobstoreServicePb.BlobstoreServiceError.ErrorCode.BLOB_FETCH_SIZE_TOO_LARGE
                            .ordinal(), "Blob fetch size too large.");
        }

        BlobstoreServicePb.FetchDataResponse response = new BlobstoreServicePb.FetchDataResponse();
        BlobKey blobKey = new BlobKey(request.getBlobKey());
        BlobInfo blobInfo = new BlobInfoFactory().loadBlobInfo(blobKey);
        if (blobInfo == null)
            throw new ApiProxy.ApplicationException(
                    BlobstoreServicePb.BlobstoreServiceError.ErrorCode.BLOB_NOT_FOUND
                            .ordinal(), "Blob not found.");
        long endIndex;
        if (request.getEndIndex() > blobInfo.getSize() - 1L)
            endIndex = blobInfo.getSize() - 1L;
        else {
            endIndex = request.getEndIndex();
        }
        System.out.println("pass1");
        if (request.getStartIndex() > endIndex) {
            response.setData("");
            System.out.println("pass2");
        } else {
            long startIndex = request.getStartIndex();
            endIndex = request.getEndIndex();
            long block_count = startIndex / MAX_BLOB_FETCH_SIZE;
            long block_modulo = startIndex % MAX_BLOB_FETCH_SIZE;

            long block_count_end = endIndex / MAX_BLOB_FETCH_SIZE;

            String block_key = blobKey.getKeyString() + "__" + block_count;
            Key key = KeyFactory.createKey("__BlobChunk__", block_key);
            System.out.println("pass3");
            if (this.blockKeyCache != key.toString()) {
                Entity entity;
                try {
                    System.out.println("key is: " + key.getName());
                    entity = datastoreService.get(key);
                    // logger.info(entity.toString());
                    // logger.info("block: " + entity.getProperty("block"));
                    System.out.println("pass4");
                    this.blockCache = (Blob) entity.getProperty("block");
                    this.blockKeyCache = key.toString();

                } catch (EntityNotFoundException e) {
                    e.printStackTrace();
                }
            }
            System.out.println("pass4");
            byte[] bytes = blockCache.getBytes();
            // # Matching boundaries, start and end are within one fetch
            if (block_count_end == block_count) {
                // Is there enough data to satisfy fetch_size bytes?

                if ((bytes.length - block_modulo) >= fetchSize) {
                    System.out.println("pass6");
                    byte[] data = Arrays.copyOfRange(bytes, (int) block_modulo,
                            (int) (block_modulo + fetchSize));
                    response.setDataAsBytes(data);
                    return response;

                } else {// Return whatever is left, not fetch_size amount
                    System.out.println("pass7");
                    byte[] data = Arrays.copyOfRange(bytes, (int) block_modulo,
                            bytes.length);
                    response.setDataAsBytes(data);
                    return response;
                }
            }
            byte[] data = Arrays.copyOfRange(bytes, (int) block_modulo,
                    bytes.length);
            int data_size = data.length;

            // Must fetch the next block
            block_key = blobKey.getKeyString() + "__" + (block_count + 1);
            Key key2 = KeyFactory.createKey("__BlobChunk__", block_key);
            System.out.println("pass8");
            try {
                System.out.println("pass9");
                Entity block2 = datastoreService.get(key);
                // logger.info(block2.toString());
                // logger.info("block: " + block2.getProperty("block"));
                this.blockCache = (Blob) block2.getProperty("block");
                this.blockKeyCache = key2.toString();

            } catch (EntityNotFoundException e) {
                e.printStackTrace();
            }
            System.out.println("pass10");
            byte[] newData = new byte[(int) (fetchSize)];
            System.arraycopy(data, 0, newData, 0, data_size);
            System.arraycopy(blockCache, 0, newData, data_size,
                    (int) (fetchSize - data_size));
            response.setDataAsBytes(newData);
        }
        return response;
    }

    public BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse createEncodedGoogleStorageKey(
            LocalRpcService.Status status,
            BlobstoreServicePb.CreateEncodedGoogleStorageKeyRequest request) {
        String encoded = Base64.encodeWebSafe(request.getFilename().getBytes(),
                true);

        BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse response = new BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse();
        response.setBlobKey("encoded_gs_key:" + encoded);
        return response;
    }
}