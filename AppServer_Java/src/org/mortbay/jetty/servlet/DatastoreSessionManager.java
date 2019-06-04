package org.mortbay.jetty.servlet;

import java.io.*;
import java.util.*;
import javax.servlet.http.*;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.datastore.*;
import org.mortbay.util.LazyList;


// AppScale: This is a naive implementation of datastore-backed sessions. There is a much more sophisticated
// implementation in the 1.9.66 SDK.
public class DatastoreSessionManager extends AbstractSessionManager {
    private final DatastoreService datastore;
    private static String kind = "_ah_SESSION";

    public DatastoreSessionManager(DatastoreService datastore) {
        this.datastore = datastore;
    }

    public Map getSessionMap() {
        throw new RuntimeException("Not supported.");
    }

    public int getSessions() {
        throw new RuntimeException("Not supported.");
    }

    protected void addSession(AbstractSessionManager.Session session) {
        this.datastore.put(encodeSessionAsEntity(session));
    }

    protected void addSession(AbstractSessionManager.Session session, boolean created) {
        synchronized(this._sessionIdManager) {
            this._sessionIdManager.addSession(session);
        }

        if (!created) {
            session.didActivate();
        } else if (this._sessionListeners != null) {
            HttpSessionEvent event = new HttpSessionEvent(session);

            for(int i = 0; i < LazyList.size(this._sessionListeners); ++i) {
                ((HttpSessionListener)LazyList.get(this._sessionListeners, i)).sessionCreated(event);
            }
        }
    }

    public AbstractSessionManager.Session getSession(String idInCluster) {
        Entity entity;
        try {
            entity = this.datastore.get(getSessionDatastoreKey(idInCluster));
        } catch (EntityNotFoundException error) {
            return null;
        }
        return decodeEntityAsSession(entity);
    }

    protected void invalidateSessions() {}

    protected AbstractSessionManager.Session newSession(HttpServletRequest request) {
        return new DatastoreSessionManager.Session(request);
    }

    protected void removeSession(String clusterId) {
        this.datastore.delete(getSessionDatastoreKey(clusterId));
    }

    private AbstractSessionManager.Session decodeEntityAsSession(Entity entity) {
        String clusterId = (String)entity.getProperty("_clusterId");
        long created = (long)entity.getProperty("_created");
        DatastoreSessionManager.Session session = new DatastoreSessionManager.Session(created, clusterId);
        session._invalid = (boolean)entity.getProperty("_invalid");

        Blob blob = (Blob)entity.getProperty("_values");
        if (blob != null) {
            try {
                ByteArrayInputStream bais = new ByteArrayInputStream(blob.getBytes());
                ObjectInputStream ois = new ObjectInputStream(bais);
                session._values = (HashMap<String, Object>)ois.readObject();
                ois.close();
                bais.close();
            } catch (ClassNotFoundException | IOException error) {
                throw new RuntimeException(error);
            }
        }

        return session;
    }

    private Entity encodeSessionAsEntity(AbstractSessionManager.Session session) {
        Entity entity = new Entity(getSessionDatastoreKey(session._clusterId));
        entity.setProperty("_clusterId", session._clusterId);
        entity.setProperty("_created", session._created);
        entity.setProperty("_invalid", session._invalid);
        if (session._values != null) {
            Blob blob;
            try {
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                ObjectOutputStream oos = new ObjectOutputStream(baos);
                oos.writeObject(session._values);
                oos.close();
                blob = new Blob(baos.toByteArray());
                baos.close();
            } catch (IOException error) {
                throw new RuntimeException(error);
            }
            entity.setProperty("_values", blob);
        }
        return entity;
    }

    private Key getSessionDatastoreKey(String clusterId) {
        String originalNamespace = NamespaceManager.get();
        try {
            NamespaceManager.set("");
            return KeyFactory.createKey(DatastoreSessionManager.kind, clusterId);
        } finally {
            NamespaceManager.set(originalNamespace);
        }
    }

    protected class Session extends AbstractSessionManager.Session {
        Session(HttpServletRequest request) {
            super(request);
        }

        Session(long created, String clusterId) {
            super(created, clusterId);
        }

        protected Map newAttributeMap() {
            return new HashMap(3);
        }

        public synchronized void removeAttribute(String name) {
            super.removeAttribute(name);
            DatastoreSessionManager.this.addSession(this);
        }

        public synchronized void setAttribute(String name, Object value) {
            super.setAttribute(name, value);
            DatastoreSessionManager.this.addSession(this);
        }
    }
}
