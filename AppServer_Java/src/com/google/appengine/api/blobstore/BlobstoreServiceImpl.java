package com.google.appengine.api.blobstore;

import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.utils.servlet.MultipartMimeUtils;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;

import javax.mail.BodyPart;
import javax.mail.MessagingException;
import javax.mail.internet.ContentType;
import javax.mail.internet.MimeMultipart;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

class BlobstoreServiceImpl implements BlobstoreService {
    static final String PACKAGE = "blobstore";
    static final String SERVE_HEADER = "X-AppEngine-BlobKey";
    static final String UPLOADED_BLOBKEY_ATTR = "com.google.appengine.api.blobstore.upload.blobkeys";
    static final String BLOB_RANGE_HEADER = "X-AppEngine-BlobRange";

    public String createUploadUrl(String successPath) {
        return createUploadUrl(successPath,
                UploadOptions.Builder.withDefaults());
    }

    public String createUploadUrl(String successPath,
            UploadOptions uploadOptions) {
        if (successPath == null) {
            throw new NullPointerException("Success path must not be null.");
        }

        BlobstoreServicePb.CreateUploadURLRequest request = new BlobstoreServicePb.CreateUploadURLRequest();
        request.setSuccessPath(successPath);

        if (uploadOptions.hasMaxUploadSizeBytesPerBlob()) {
            request.setMaxUploadSizePerBlobBytes(uploadOptions
                    .getMaxUploadSizeBytesPerBlob());
        }

        if (uploadOptions.hasMaxUploadSizeBytes())
            request.setMaxUploadSizeBytes(uploadOptions.getMaxUploadSizeBytes());
        byte[] responseBytes;
        try {
            responseBytes = ApiProxy.makeSyncCall("blobstore",
                    "CreateUploadURL", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 1:
                throw new IllegalArgumentException(
                        "The resulting URL was too long.");
            case 2:
                throw new BlobstoreFailureException(
                        "An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException(
                    "An unexpected error occurred.", ex);
        }

        BlobstoreServicePb.CreateUploadURLResponse response = new BlobstoreServicePb.CreateUploadURLResponse();
        response.mergeFrom(responseBytes);
        return response.getUrl();
    }

    public void serve(BlobKey blobKey, HttpServletResponse response) {
        serve(blobKey, (ByteRange) null, response);
    }

    public void serve(BlobKey blobKey, String rangeHeader,
            HttpServletResponse response) {
        serve(blobKey, ByteRange.parse(rangeHeader), response);
    }

    public void serve(BlobKey blobKey, ByteRange byteRange,
            HttpServletResponse response) {
        if (response.isCommitted()) {
            throw new IllegalStateException("Response was already committed.");
        }

        response.setStatus(200);
        response.setHeader("X-AppEngine-BlobKey", blobKey.getKeyString());
        if (byteRange != null)
            response.setHeader("X-AppEngine-BlobRange", byteRange.toString());
    }

    public ByteRange getByteRange(HttpServletRequest request) {
        Enumeration rangeHeaders = request.getHeaders("range");
        if (!rangeHeaders.hasMoreElements()) {
            return null;
        }

        String rangeHeader = (String) rangeHeaders.nextElement();
        if (rangeHeaders.hasMoreElements()) {
            throw new UnsupportedRangeFormatException(
                    "Cannot accept multiple range headers.");
        }

        return ByteRange.parse(rangeHeader);
    }

    public void delete(BlobKey[] blobKeys) {
        BlobstoreServicePb.DeleteBlobRequest request = new BlobstoreServicePb.DeleteBlobRequest();
        for (BlobKey blobKey : blobKeys) {
            request.addBlobKey(blobKey.getKeyString());
        }

        if (request.blobKeySize() == 0) {
            return;
        }

        try {
            byte[] responseBytes = ApiProxy.makeSyncCall("blobstore",
                    "DeleteBlob", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 2:
                throw new BlobstoreFailureException(
                        "An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException(
                    "An unexpected error occurred.", ex);
        }
    }

    @Deprecated
    public Map<String, BlobKey> getUploadedBlobs(HttpServletRequest request) {
        Map<String, List<BlobKey>> blobKeys = getUploads(request);
        Map<String, BlobKey> result = new HashMap<String, BlobKey>(
                blobKeys.size());

        for (Map.Entry<String, List<BlobKey>> entry : blobKeys.entrySet()) {
            if (!(entry.getValue()).isEmpty()) {
                result.put(entry.getKey(), (entry.getValue()).get(0));
            }
        }
        return result;
    }

    public Map<String, List<BlobKey>> getUploads(HttpServletRequest request) {
//        Map attributes = (Map) request
//                .getAttribute("com.google.appengine.api.blobstore.upload.blobkeys");

     //   if (attributes == null) {
     //       throw new IllegalStateException(
     //               "Must be called from a blob upload callback request.");
     //   }
        Map<String, List<BlobKey>> blobKeys = new HashMap<String, List<BlobKey>>();
        MimeMultipart parts;
        try {
            parts = MultipartMimeUtils.parseMultipartRequest(request);
            int count = parts.getCount();
            for (int i = 0; i < count; i++) {
                BodyPart p = parts.getBodyPart(i);
                if (p.getFileName() != null) {
                    String fileFieldName = MultipartMimeUtils.getFieldName(p);
                    ContentType c = new ContentType(p.getContentType());
                    String blobKey = c.getParameter("blob-key");
                    List<BlobKey> blobKeyList = blobKeys.get(fileFieldName);
                    if (blobKeyList == null){
                        blobKeyList = new ArrayList<BlobKey>();
                    }
                    blobKeyList.add(new BlobKey(blobKey));
                    blobKeys.put(fileFieldName, blobKeyList);
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        } catch (MessagingException e) {
            e.printStackTrace();
        }
        return blobKeys;
    }

    public byte[] fetchData(BlobKey blobKey, long startIndex, long endIndex) {
        if (startIndex < 0L) {
            throw new IllegalArgumentException("Start index must be >= 0.");
        }

        if (endIndex < startIndex) {
            throw new IllegalArgumentException(
                    "End index must be >= startIndex.");
        }

        long fetchSize = endIndex - startIndex + 1L;
        if (fetchSize > 1015808L) {
            throw new IllegalArgumentException("Blob fetch size " + fetchSize
                    + " it larger " + "than maximum size " + 1015808
                    + " bytes.");
        }
        BlobstoreServicePb.FetchDataRequest request = new BlobstoreServicePb.FetchDataRequest();
        request.setBlobKey(blobKey.getKeyString());
        request.setStartIndex(startIndex);
        request.setEndIndex(endIndex);
        byte[] responseBytes;
        try {
            responseBytes = ApiProxy.makeSyncCall("blobstore", "FetchData",
                    request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 3:
                throw new SecurityException(
                        "This application does not have access to that blob.");
            case 4:
                throw new IllegalArgumentException("Blob not found.");
            case 2:
                throw new BlobstoreFailureException(
                        "An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException(
                    "An unexpected error occurred.", ex);
        }

        BlobstoreServicePb.FetchDataResponse response = new BlobstoreServicePb.FetchDataResponse();
        response.mergeFrom(responseBytes);
        return response.getDataAsBytes();
    }

    public BlobKey createGsBlobKey(String filename) {
        if (!filename.startsWith("/gs/")) {
            throw new IllegalArgumentException(
                    "Google storage filenames must be prefixed with /gs/");
        }
        BlobstoreServicePb.CreateEncodedGoogleStorageKeyRequest request = new BlobstoreServicePb.CreateEncodedGoogleStorageKeyRequest();
        request.setFilename(filename);
        byte[] responseBytes;
        try {
            responseBytes = ApiProxy.makeSyncCall("blobstore",
                    "CreateEncodedGoogleStorageKey", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 2:
                throw new BlobstoreFailureException(
                        "An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException(
                    "An unexpected error occurred.", ex);
        }

        BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse response = new BlobstoreServicePb.CreateEncodedGoogleStorageKeyResponse();
        response.mergeFrom(responseBytes);
        return new BlobKey(response.getBlobKey());
    }
}