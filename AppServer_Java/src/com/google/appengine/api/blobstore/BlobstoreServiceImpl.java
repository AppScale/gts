package com.google.appengine.api.blobstore;

import java.io.IOException;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Logger;

import javax.mail.BodyPart;
import javax.mail.MessagingException;
import javax.mail.internet.ContentType;
import javax.mail.internet.MimeMultipart;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.servlet.MultipartMimeUtils;

class BlobstoreServiceImpl implements BlobstoreService {
    private static final Logger logger = Logger.getLogger(BlobstoreServiceImpl.class.getName());
    static final String PACKAGE = "blobstore";
    static final String SERVE_HEADER = "X-AppEngine-BlobKey";
    static final String UPLOADED_BLOBKEY_ATTR = "com.google.appengine.api.blobstore.upload.blobkeys";
    static final String BLOB_RANGE_HEADER = "X-AppEngine-BlobRange";

    public String createUploadUrl(String successPath) {
        if (successPath == null) {
            throw new NullPointerException("Success path must not be null.");
        }
        BlobstoreServicePb.CreateUploadURLRequest request = new BlobstoreServicePb.CreateUploadURLRequest();
        request.setSuccessPath(successPath);
        byte[] responseBytes;
        try {
            responseBytes = ApiProxy.makeSyncCall("blobstore", "CreateUploadURL", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 1:
                throw new IllegalArgumentException("The resulting URL was too long.");
            case 2:
                throw new BlobstoreFailureException("An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException("An unexpected error occurred.", ex);
        }

        BlobstoreServicePb.CreateUploadURLResponse response = new BlobstoreServicePb.CreateUploadURLResponse();
        response.mergeFrom(responseBytes);
        return response.getUrl();
    }

    public void serve(BlobKey blobKey, HttpServletResponse response) {
        serve(blobKey, (ByteRange) null, response);
    }

    public void serve(BlobKey blobKey, String rangeHeader, HttpServletResponse response) {
        serve(blobKey, ByteRange.parse(rangeHeader), response);
    }

    public void serve(BlobKey blobKey, ByteRange byteRange, HttpServletResponse response) {
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
            throw new UnsupportedRangeFormatException("Cannot accept multiple range headers.");
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
            byte[] responseBytes = ApiProxy.makeSyncCall("blobstore", "DeleteBlob", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 2:
                throw new BlobstoreFailureException("An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException("An unexpected error occurred.", ex);
        }
    }

    public Map<String, BlobKey> getUploadedBlobs(HttpServletRequest request) {
        Map<String, String> attributes = (Map<String, String>) request
                .getAttribute("com.google.appengine.api.blobstore.upload.blobkeys");
        //logger.info("enter try");

        HashMap<String, BlobKey> uploadedBlobs = new HashMap<String, BlobKey>();

        MimeMultipart parts;
        try {
            parts = MultipartMimeUtils.parseMultipartRequest(request);
            int count = parts.getCount();
            for (int i = 0; i < count; i++) {
                BodyPart p = parts.getBodyPart(i);
                if (p.getFileName() != null) {
                    p.getDescription();
                    //logger.info("filename: " + p.getFileName());
                    //logger.info("content-type: " + p.getContentType());
                    String fileFieldName = MultipartMimeUtils.getFieldName(p);
                    //logger.info("field name: " + fileFieldName);
                    ContentType c = new ContentType(p.getContentType());
                    // ParameterList pList = c.getParameterList();
                    // logger.info("params in contenttype");
                    // Enumeration names = pList.getNames();
                    // while (names.hasMoreElements()) {
                    //
                    // logger.info("name: " + names.nextElement().toString());
                    // }
                    // Enumeration headers = p.getAllHeaders();
                    // while (headers.hasMoreElements()) {
                    // logger.info("iterations");
                    // p.get
                    // InternetHeaders h = (InternetHeaders)
                    // headers.nextElement();
                    // Enumeration iheaders = h.getAllHeaders();
                    // while (iheaders.hasMoreElements()) {
                    // logger.info(iheaders.nextElement().toString());
                    // }
                    // // String n = h.get;
                    // // String v = h.getValue();
                    // // logger.info(h + " : " + v);
                    // }
                    // if (p.getFileName().length() > 0) {
                    //
                    // }
                    String blobKey = c.getParameter("blob-key");
                    String originalContentType = p.getContentType();
                    uploadedBlobs.put(fileFieldName, new BlobKey(blobKey));

                } else {
                    String fieldName = MultipartMimeUtils.getFieldName(p);
                    //logger.info("field: " + fieldName);
                }
            }

        } catch (IOException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
        } catch (MessagingException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
        }
        // if (attributes == null) {
        // logger.info("no com.google.appengine.api.blobstore.upload.blobkeys attribute");
        // // throw new
        // //
        // IllegalStateException("Must be called from a blob upload callback request.");
        // }
        // logger.info("content type: " + request.getContentType());
        // logger.info("content path: " + request.getContextPath());
        // logger.info("content encoding: " + request.getCharacterEncoding());
        //
        // Enumeration headerNames = request.getHeaderNames();
        // while (headerNames.hasMoreElements()) {
        // logger.info("header: " + headerNames.nextElement().toString());
        // }
        //
        // Enumeration attributeNames = request.getAttributeNames();
        // while (attributeNames.hasMoreElements()) {
        // logger.info("attributeName: " +
        // attributeNames.nextElement().toString());
        // }
        //
        // Enumeration paramNames = request.getParameterNames();
        // while (paramNames.hasMoreElements()) {
        // logger.info("param: " + paramNames.nextElement().toString());
        // }
        //
        // Map<String, BlobKey> blobKeys = new HashMap<String,
        // BlobKey>(attributes.size());
        // for (Map.Entry<String, String> attr : attributes.entrySet()) {
        // blobKeys.put(attr.getKey(), new BlobKey(attr.getValue()));
        // }
        // return blobKeys;
        return uploadedBlobs;
    }

    public byte[] fetchData(BlobKey blobKey, long startIndex, long endIndex) {
        if (startIndex < 0L) {
            throw new IllegalArgumentException("Start index must be >= 0.");
        }

        if (endIndex < startIndex) {
            throw new IllegalArgumentException("End index must be >= startIndex.");
        }

        long fetchSize = endIndex - startIndex + 1L;
        if (fetchSize > 1015808L) {
            throw new IllegalArgumentException("Blob fetch size " + fetchSize + " it larger " + "than maximum size "
                    + 1015808 + " bytes.");
        }
        BlobstoreServicePb.FetchDataRequest request = new BlobstoreServicePb.FetchDataRequest();
        request.setBlobKey(blobKey.getKeyString());
        request.setStartIndex(startIndex);
        request.setEndIndex(endIndex);
        byte[] responseBytes;
        try {
            responseBytes = ApiProxy.makeSyncCall("blobstore", "FetchData", request.toByteArray());
        } catch (ApiProxy.ApplicationException ex) {
            switch (ex.getApplicationError()) {
            case 3:
                throw new SecurityException("This application does not have access to that blob.");
            case 4:
                throw new IllegalArgumentException("Blob not found.");
            case 2:
                throw new BlobstoreFailureException("An internal blobstore error occured.");
            }
            throw new BlobstoreFailureException("An unexpected error occurred.", ex);
        }

        BlobstoreServicePb.FetchDataResponse response = new BlobstoreServicePb.FetchDataResponse();
        response.mergeFrom(responseBytes);
        return response.getDataAsBytes();
    }
}
