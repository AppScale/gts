package com.google.appengine.api.blobstore.dev;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.blobstore.BlobInfo;
import com.google.appengine.api.blobstore.BlobInfoFactory;
import com.google.appengine.api.blobstore.BlobKey;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityNotFoundException;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;
import com.google.appengine.api.datastore.Query;
import java.util.Iterator;

public final class BlobInfoStorage {
    private final BlobInfoFactory blobInfoFactory = new BlobInfoFactory();
    private final DatastoreService datastoreService = DatastoreServiceFactory.getDatastoreService();

    public BlobInfo loadBlobInfo(BlobKey blobKey) {
        return this.blobInfoFactory.loadBlobInfo(blobKey);
    }

    public BlobInfo loadGsFileInfo(BlobKey blobKey) {
        String namespace = NamespaceManager.get();

        BlobInfo blobInfo;
        try {
            NamespaceManager.set("");
            Key key = KeyFactory.createKey((Key)null, "__GsFileInfo__", blobKey.getKeyString());

            try {
                Entity ex = this.datastoreService.get(key);
                blobInfo = (new BlobInfoFactory()).createBlobInfo(ex);
                return blobInfo;
            } catch (EntityNotFoundException e) {
                return null;
            }
        } finally {
            NamespaceManager.set(namespace);
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
