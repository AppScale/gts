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

      BlobInfo var5;
      try {
         NamespaceManager.set("");
         Key key = KeyFactory.createKey((Key)null, "__GsFileInfo__", blobKey.getKeyString());

         try {
            Entity ex = this.datastoreService.get(key);
            var5 = (new BlobInfoFactory()).createBlobInfo(ex);
            return var5;
         } catch (EntityNotFoundException var9) {
            var5 = null;
         }
      } finally {
         NamespaceManager.set(namespace);
      }

      return var5;
   }

   public void saveBlobInfo(BlobInfo blobInfo) {
      String namespace = NamespaceManager.get();

      try {
         NamespaceManager.set("");
         Entity entity = new Entity("__BlobInfo__", blobInfo.getBlobKey().getKeyString());
         entity.setProperty("content_type", blobInfo.getContentType());
         entity.setProperty("creation", blobInfo.getCreation());
         entity.setProperty("filename", blobInfo.getFilename());
         entity.setProperty("size", Long.valueOf(blobInfo.getSize()));
         entity.setProperty("md5_hash", blobInfo.getMd5Hash());
         this.datastoreService.put(entity);
      } finally {
         NamespaceManager.set(namespace);
      }

   }

   public void deleteBlobInfo(BlobKey blobKey) {
      this.datastoreService.delete(new Key[]{this.getMetadataKeyForBlobKey(blobKey)});
   }

   protected Key getMetadataKeyForBlobKey(BlobKey blobKey) {
      String namespace = NamespaceManager.get();

      Key var3;
      try {
         NamespaceManager.set("");
         if(blobKey.getKeyString().startsWith("encoded_gs_key:")) {
            var3 = KeyFactory.createKey("__GsFileInfo__", blobKey.getKeyString());
            return var3;
         }

         var3 = KeyFactory.createKey("__BlobInfo__", blobKey.getKeyString());
      } finally {
         NamespaceManager.set(namespace);
      }

      return var3;
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

      Iterator i$ = this.datastoreService.prepare(q).asIterable().iterator();

      while(i$.hasNext()) {
         Entity e = (Entity)i$.next();
         this.datastoreService.delete(new Key[]{e.getKey()});
      }

   }
}
