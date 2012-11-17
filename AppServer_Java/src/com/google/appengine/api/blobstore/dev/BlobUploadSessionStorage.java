package com.google.appengine.api.blobstore.dev;


import java.util.logging.Logger;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityNotFoundException;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;
import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserServiceFactory;


public final class BlobUploadSessionStorage
{
    private static final Logger    logger       = Logger.getLogger(BlobUploadSessionStorage.class.getName());
    static final String            KIND         = "__BlobUploadSession__";
    static final String            SUCCESS_PATH = "success_path";
    private final DatastoreService datastoreService;

    /*
     * AppScale - removed unused class variables and added KIND variable
     */

    public BlobUploadSessionStorage()
    {
        this.datastoreService = DatastoreServiceFactory.getDatastoreService();
    }

    public String createSession( BlobUploadSession session )
    {
        logger.finer("createSession called in BlobUploadSessionStorage");
        String namespace = NamespaceManager.get();
        Entity entity;
        long time = System.currentTimeMillis();
        User user = UserServiceFactory.getUserService().getCurrentUser();
        try
        {
            NamespaceManager.set("");
            entity = new Entity(KIND);
        }
        finally
        {
            NamespaceManager.set(namespace);
        }

        /*
         * AppScale - added NGINX success path to entity
         */

        String path = "http://" + System.getProperty("NGINX_ADDR") + ":" + System.getProperty("NGINX_PORT") + session.getSuccessPath();
        logger.fine("success path has been set as [" + path + "]");
        entity.setProperty(SUCCESS_PATH, path);
        entity.setProperty("creation", time);
        entity.setProperty("user", user);
        entity.setProperty("state", "init");
        this.datastoreService.put(entity);

        return KeyFactory.keyToString(entity.getKey());
    }

    public BlobUploadSession loadSession( String sessionId )
    {
        logger.fine("loadSession called with sessionId [" + sessionId + "]");
        try
        {
            return convertFromEntity(this.datastoreService.get(getKeyForSession(sessionId)));
        }
        catch (EntityNotFoundException ex)
        {
            logger.severe("Caught EntityNotFoundException for sessionId [" + sessionId + "], message: [" + ex.getMessage() + "]");
        }
        return null;
    }

    public void deleteSession( String sessionId )
    {
        this.datastoreService.delete(new Key[] { getKeyForSession(sessionId) });
    }

    private BlobUploadSession convertFromEntity( Entity entity )
    {
        /*
         * AppScale - replaced method body
         */
        logger.finer("convertFromEntity called with entity [" + entity + "]");
        return new BlobUploadSession((String)entity.getProperty("success_path"));
    }

    private Key getKeyForSession( String sessionId )
    {
        logger.finer("getKeyForSession called with sessionId [" + sessionId + "]");
        String namespace = NamespaceManager.get();
        try
        {
            NamespaceManager.set("");
            Key localKey = KeyFactory.stringToKey(sessionId);
            logger.finer("Returning key [" + localKey + "] for sessionId [" + sessionId + "]");
            return localKey;
        }
        finally
        {
            NamespaceManager.set(namespace);
        }
    }
}
