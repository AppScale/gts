package com.google.appengine.api.blobstore.dev;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.blobstore.BlobInfo;
import com.google.appengine.api.blobstore.BlobInfoFactory;
import com.google.appengine.api.blobstore.BlobKey;
import com.google.appengine.api.blobstore.BlobstoreFailureException;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityNotFoundException;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;
import com.google.appengine.api.datastore.Query;

import com.google.appengine.repackaged.com.google.common.io.BaseEncoding;

import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Iterator;
import java.util.Locale;

public final class BlobInfoStorage {
    private final BlobInfoFactory blobInfoFactory = new BlobInfoFactory();
    private final DatastoreService datastoreService = DatastoreServiceFactory.getDatastoreService();

    public BlobInfo loadBlobInfo(BlobKey blobKey) {
        return this.blobInfoFactory.loadBlobInfo(blobKey);
    }

    public BlobInfo loadGsFileInfo(BlobKey blobKey) {
        URL gcsURL = urlForGCSBlobKey(blobKey);

        String[] pathParts = gcsURL.getPath().split("/");
        StringBuilder objectNameBuilder = new StringBuilder();
        for (int i = 2; i < pathParts.length; i++) {
            if (i > 2)
                objectNameBuilder.append("/");
            objectNameBuilder.append(pathParts[i]);
        }
        String objectName = objectNameBuilder.toString();

        HttpURLConnection conn;
        try {
            conn = (HttpURLConnection) gcsURL.openConnection();
            conn.setRequestMethod("HEAD");
            int respCode = conn.getResponseCode();

            if (respCode == HttpURLConnection.HTTP_NOT_FOUND)
                throw new IllegalArgumentException(gcsURL.toString() + " not found.");

            if (respCode != HttpURLConnection.HTTP_OK)
                throw new BlobstoreFailureException("Error fetching " + gcsURL.toString());

            String contentType = conn.getHeaderField("Content-Type");

            // TODO: Get timeCreated from the JSON API instead.
            DateFormat dateFormat = new SimpleDateFormat("EEE, dd MMM yyyy kk:mm:ss z", Locale.ENGLISH);
            String lastModified = conn.getHeaderField("Last-Modified");
            Date created = dateFormat.parse(lastModified);

            Long size = Long.parseLong(conn.getHeaderField("x-goog-stored-content-length"));
            String md5 = conn.getHeaderField("ETag").replace("\"", "");
            return new BlobInfo(blobKey, contentType, created, objectName, size, md5);
        } catch (IOException ex) {
            throw new BlobstoreFailureException("Error fetching " + gcsURL.toString());
        } catch (java.text.ParseException ex) {
            throw new BlobstoreFailureException(ex.toString());
        }
    }

    public static URL urlForGCSBlobKey(BlobKey blobKey) {
        if (System.getenv(LocalBlobstoreService.GCS_HOST_VAR) == null)
            throw new IllegalArgumentException(LocalBlobstoreService.GCS_HOST_VAR + " not set.");
        String gcsHost = System.getenv(LocalBlobstoreService.GCS_HOST_VAR);
        String gcsPath;

        if (!blobKey.getKeyString().contains(":"))
            throw new IllegalArgumentException("Invalid GCS BlobKey: " + blobKey.getKeyString());
        String blobKeyBase64 = blobKey.getKeyString().split(":")[1];

        try {
            byte[] decodedKey = BaseEncoding.base64().decode(blobKeyBase64);
            gcsPath = new String(decodedKey, "UTF-8");
        } catch (UnsupportedEncodingException ex) {
            throw new IllegalArgumentException("Unable to decode blobKey: " + blobKey.getKeyString());
        }

        String[] pathParts = gcsPath.split("/");
        if (pathParts.length < 4)
            throw new IllegalArgumentException("Invalid GCS path: " + gcsPath);

        String bucketName = pathParts[2];

        // Object names can contain slashes.
        StringBuilder objectNameBuilder = new StringBuilder();
        for (int i = 3; i < pathParts.length; i++) {
            if (i > 3)
                objectNameBuilder.append("/");
            objectNameBuilder.append(pathParts[i]);
        }
        String objectName = objectNameBuilder.toString();

        try {
            return new URL(gcsHost + "/" + bucketName + "/" + objectName);
        } catch (MalformedURLException ex) {
            throw new IllegalArgumentException("Invalid GCS url: " + gcsHost + "/" + bucketName + "/" + objectName);
        }
    }

    public void saveBlobInfo(BlobInfo blobInfo) {
        String namespace = NamespaceManager.get();

        try {
            NamespaceManager.set("");
            Entity entity = new Entity("__BlobInfo__", blobInfo.getBlobKey().getKeyString());
            entity.setProperty("content_type", blobInfo.getContentType());
            entity.setProperty("creation", blobInfo.getCreation());
            entity.setProperty("filename", blobInfo.getFilename());
            entity.setProperty("size", blobInfo.getSize());
            entity.setProperty("md5_hash", blobInfo.getMd5Hash());
            this.datastoreService.put(entity);
        } finally {
            NamespaceManager.set(namespace);
        }

    }

    public void deleteBlobInfo(BlobKey blobKey) {
        this.datastoreService.delete(this.getMetadataKeyForBlobKey(blobKey));
    }

    protected Key getMetadataKeyForBlobKey(BlobKey blobKey) {
        String namespace = NamespaceManager.get();

        try {
            NamespaceManager.set("");
            if(blobKey.getKeyString().startsWith(LocalBlobstoreService.GOOGLE_STORAGE_KEY_PREFIX)) {
                return KeyFactory.createKey("__GsFileInfo__", blobKey.getKeyString());
            }

            return KeyFactory.createKey("__BlobInfo__", blobKey.getKeyString());
        } finally {
            NamespaceManager.set(namespace);
        }
    }

    void deleteAllBlobInfos() {
        String namespace = NamespaceManager.get();

        Query q;
        try {
            NamespaceManager.set("");
            q = new Query("__BlobInfo__");
        } finally {
            NamespaceManager.set(namespace);
        }

        Iterator entities = this.datastoreService.prepare(q).asIterable().iterator();

        while(entities.hasNext()) {
            Entity e = (Entity)entities.next();
            this.datastoreService.delete(e.getKey());
        }

    }
}
