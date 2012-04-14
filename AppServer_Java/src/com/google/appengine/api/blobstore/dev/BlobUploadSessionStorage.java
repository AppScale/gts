package com.google.appengine.api.blobstore.dev;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityNotFoundException;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;
import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserServiceFactory;

public final class BlobUploadSessionStorage {
    static final String KIND = "__BlobUploadSession__";
    static final String SUCCESS_PATH = "success_path";
    private final DatastoreService datastoreService;

    public BlobUploadSessionStorage() {
        this.datastoreService = DatastoreServiceFactory.getDatastoreService();
    }

    public String createSession(BlobUploadSession session) {
        String namespace = NamespaceManager.get();
        Entity entity;
        long time = System.currentTimeMillis();
        User user = UserServiceFactory.getUserService().getCurrentUser();
        try {
            NamespaceManager.set("");
            entity = new Entity(KIND);
        } finally {
            NamespaceManager.set(namespace);
        }

        String path = "http://" + System.getProperty("SERVER_NAME") + ":" + System.getProperty("NGINX_PORT")
                + session.getSuccessPath();
        entity.setProperty(SUCCESS_PATH, path);
        entity.setProperty("creation", time);
        entity.setProperty("user", user);
        entity.setProperty("state", "init");
        this.datastoreService.put(entity);

        return KeyFactory.keyToString(entity.getKey());
    }

    public BlobUploadSession loadSession(String sessionId) {
        try {
            return convertFromEntity(this.datastoreService.get(getKeyForSession(sessionId)));
        } catch (EntityNotFoundException ex) {
        }
        return null;
    }

    public void deleteSession(String sessionId) {
        this.datastoreService.delete(new Key[] { getKeyForSession(sessionId) });
    }

    private BlobUploadSession convertFromEntity(Entity entity) {
        return new BlobUploadSession((String) entity.getProperty("success_path"));
    }

    private Key getKeyForSession(String sessionId) {
        String namespace = NamespaceManager.get();
        try {
            NamespaceManager.set("");
            Key localKey = KeyFactory.stringToKey(sessionId);
            return localKey;
        } finally {
            NamespaceManager.set(namespace);
        }
    }
}
