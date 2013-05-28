package com.google.appengine.api.blobstore;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;

import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.utils.servlet.MultipartMimeUtils;

import java.io.IOException;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;

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
    static final String UPLOADED_BLOBINFO_ATTR = "com.google.appengine.api.blobstore.upload.blobinfos";
    static final String CREATION_DATE_FORMAT = "yyyy-MM-dd HH:mm:ss.SSS";

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
        System.out.println("AAA");
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

    public Map<String, List<BlobInfo>> getBlobInfos(HttpServletRequest request)
  {
    Map attributes = (Map)request.getAttribute("com.google.appengine.api.blobstore.upload.blobinfos");

    if (attributes == null) {
      throw new IllegalStateException("Must be called from a blob upload callback request.");
    }
    Map blobInfos = new HashMap(attributes.size());
    for (Map.Entry attr : (Set<Map.Entry>)attributes.entrySet()) {
      List blobs = new ArrayList(((List)attr.getValue()).size());
      for (Map info : (List<Map>)attr.getValue()) {
        BlobKey key = new BlobKey((String)info.get("key"));
        String contentType = (String)info.get("content-type");
        Date creationDate = parseCreationDate((String)info.get("creation-date"));
        String filename = (String)info.get("filename");
        int size = Integer.parseInt((String)info.get("size"));
        String md5Hash = (String)info.get("md5-hash");
        blobs.add(new BlobInfo(key, contentType, creationDate, filename, size, md5Hash));
      }
      blobInfos.put(attr.getKey(), blobs);
    }
    return blobInfos;
  }

  public Map<String, List<FileInfo>> getFileInfos(HttpServletRequest request)
  {
    Map attributes = (Map)request.getAttribute("com.google.appengine.api.blobstore.upload.blobinfos");

    if (attributes == null) {
      throw new IllegalStateException("Must be called from a blob upload callback request.");
    }
    Map fileInfos = new HashMap(attributes.size());
    for (Map.Entry attr : (Set<Map.Entry>)attributes.entrySet()) {
      List files = new ArrayList(((List)attr.getValue()).size());
      for (Map info : (List<Map>)attr.getValue()) {
        String contentType = (String)info.get("content-type");
        Date creationDate = parseCreationDate((String)info.get("creation-date"));
        String filename = (String)info.get("filename");
        int size = Integer.parseInt((String)info.get("size"));
        String md5Hash = (String)info.get("md5-hash");
        String gsObjectName = null;
        if (info.containsKey("gs-name")) {
          gsObjectName = (String)info.get("gs-name");
        }
        files.add(new FileInfo(contentType, creationDate, filename, size, md5Hash, gsObjectName));
      }

      fileInfos.put(attr.getKey(), files);
    }
    return fileInfos;
  }

  @VisibleForTesting
  protected static Date parseCreationDate(String date) {
    Date creationDate = null;
    try {
      date = date.trim().substring(0, "yyyy-MM-dd HH:mm:ss.SSS".length());
      SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS");
      dateFormat.setLenient(false);
      creationDate = dateFormat.parse(date);
    } catch (IndexOutOfBoundsException e) {
    } catch (ParseException e) {
    }
    return creationDate;
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
                    + " is larger " + "than maximum size " + 1015808
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
