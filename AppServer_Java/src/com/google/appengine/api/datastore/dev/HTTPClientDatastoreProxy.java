package com.google.appengine.api.datastore.dev;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.apache.http.HttpEntity;
import org.apache.http.HttpHost;
import org.apache.http.HttpResponse;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.conn.routing.HttpRoute;
import org.apache.http.conn.scheme.PlainSocketFactory;
import org.apache.http.conn.scheme.Scheme;
import org.apache.http.conn.scheme.SchemeRegistry;
import org.apache.http.entity.ByteArrayEntity;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.impl.conn.tsccm.ThreadSafeClientConnManager;

import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserService;
import com.google.appengine.api.users.UserServiceFactory;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Request;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Response;

public class HTTPClientDatastoreProxy {

    private static final Logger logger = Logger.getLogger(HTTPClientDatastoreProxy.class.getName());

    DefaultHttpClient client = null;
    String url = null;

    public HTTPClientDatastoreProxy(String host, int port, boolean isSSL) {
    	SchemeRegistry schemeRegistry = new SchemeRegistry();
    	schemeRegistry.register(
    	         new Scheme("http", PlainSocketFactory.getSocketFactory(), port));
    	ThreadSafeClientConnManager cm = new ThreadSafeClientConnManager(schemeRegistry);
//    	 Increase max total connection to 200
    	cm.setMaxTotal(200);
//    	 Increase default max connection per route to 20
    	cm.setDefaultMaxPerRoute(20);
//    	 Increase max connections for localhost:80 to 50
        //logger.log(Level.INFO, "http client started");
        url = "http://" + host + ":" + port + "/";
        HttpHost localhost = new HttpHost(url);
        cm.setMaxForRoute(new HttpRoute(localhost), 50);
        client = new DefaultHttpClient(cm);
        //logger.log(Level.INFO, "connecting to pb server at: " + url);
    }

    public void doPost(String appId, String method, ProtocolMessage<?> request, ProtocolMessage<?> response) {
        HttpPost post = new HttpPost(url);
        post.addHeader("ProtocolBufferType", "Request");
        String tag = appId;
        User user = getUser();
        if (user != null) {
            tag += ":" + user.getEmail();
            tag += ":" + user.getNickname();
            tag += ":" + user.getAuthDomain();
        }
        post.addHeader("AppData", tag);

        Request remoteRequest = new Request();
        remoteRequest.setMethod(method);
        remoteRequest.setServiceName("datastore_v3");
        remoteRequest.setRequestAsBytes(request.toByteArray());

        ByteArrayOutputStream bao = new ByteArrayOutputStream();
        try {
            bao.write(remoteRequest.toByteArray());
            ByteArrayEntity entity = new ByteArrayEntity(bao.toByteArray());
            post.setEntity(entity);
            bao.close();
        } catch (IOException e1) {
            e1.printStackTrace();
        }

        Response remoteResponse = new Response();
        try {
            byte[] bytes = client.execute(post, new ByteArrayResponseHandler());
            remoteResponse.parseFrom(bytes);
            //logger.log(Level.INFO, "raw bytes");
            //logger.log(Level.INFO, new String(bytes));
        } catch (ClientProtocolException e) {
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        }
        if (!remoteResponse.hasResponse())
            logger.log(Level.WARNING, "no response from server for: " + method + " method!");
        if (remoteResponse.hasApplicationError()) {
            logger.log(Level.WARNING, "application error in " + method + " method !"
            + remoteResponse.getApplicationError().toFlatString());
        }
        if (remoteResponse.hasException()) {
            logger.log(Level.WARNING, "exception in " + method + " method! " + remoteResponse.getException());
        }
        if (remoteResponse.hasJavaException()) {
            logger.log(Level.WARNING, "java exception in " + method + " method! " + remoteResponse.getJavaException());
        }
        response.parseFrom(remoteResponse.getResponseAsBytes());
    }

    private User getUser() {
        UserService userService = UserServiceFactory.getUserService();
        return userService.getCurrentUser();
    }

    private class ByteArrayResponseHandler implements ResponseHandler<byte[]> {

        public byte[] handleResponse(HttpResponse response) throws ClientProtocolException, IOException {
        	HttpEntity entity = response.getEntity();
        	if (entity != null) {
        		InputStream inputStream = entity.getContent();
        		try {
                    return inputStreamToArray(inputStream);
        		} finally {
        			entity.getContent().close();
                }
            }
        	return new byte[]{};
        }
    }

    private byte[] inputStreamToArray(InputStream in) {
        int len;
        int size = 10240;
        byte[] buf = null;
        try {
            if (in instanceof ByteArrayInputStream) {
                size = in.available();
                buf = new byte[size];
                len = in.read(buf, 0, size);
            } else {
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                buf = new byte[size];
                // long t1 = System.nanoTime();
                while ((len = in.read(buf, 0, size)) != -1) {
                    bos.write(buf, 0, len);
                }
                // long t2 = System.nanoTime();
                buf = bos.toByteArray();

            }
            in.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
        return buf;
    }
}
