/**
 * 
 */
package com.google.appengine.api.datastore.dev;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.KeyStore;

import org.apache.http.HttpEntity;
import org.apache.http.HttpHost;
import org.apache.http.HttpResponse;
import org.apache.http.HttpVersion;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.HttpClient;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.conn.ClientConnectionManager;
import org.apache.http.conn.params.ConnManagerParams;
import org.apache.http.conn.scheme.PlainSocketFactory;
import org.apache.http.conn.scheme.Scheme;
import org.apache.http.conn.scheme.SchemeRegistry;
import org.apache.http.conn.ssl.SSLSocketFactory;
import org.apache.http.entity.ByteArrayEntity;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.impl.conn.tsccm.ThreadSafeClientConnManager;
import org.apache.http.params.BasicHttpParams;
import org.apache.http.params.HttpParams;
import org.apache.http.params.HttpProtocolParams;

import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserService;
import com.google.appengine.api.users.UserServiceFactory;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.RawMessage;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Request;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Response;

/**
 * @author puneet
 *
 */
public class HTTPClientDatastoreProxy {
	private static HttpClient httpClient = null;
	
	static {
		HttpParams params = new BasicHttpParams();
        ConnManagerParams.setMaxTotalConnections(params, 20);
        ConnManagerParams.setTimeout(params, 50000);
        HttpProtocolParams.setVersion(params, HttpVersion.HTTP_1_0);
        
        FileInputStream instream = null;
        try {
        	ResourceLoader res = ResourceLoader.getResouceLoader();
        	String keyStoreLocation = res.getKeyStorePath();
        	System.out.println("key location: "+ keyStoreLocation);

        	String keyStorePwd = res.getKetStorePwd();
        	System.out.println("password: "+ keyStorePwd);
        	
//        	if (System.getProperty(IConstants.KEY_STORE_PATH_PROPERTY_NAME) != null) {
//				keyStoreLocation = System
//						.getProperty(IConstants.KEY_STORE_PATH_PROPERTY_NAME);
//			}
        	instream = new FileInputStream(new File(keyStoreLocation));
        	KeyStore trustStore  = KeyStore.getInstance(KeyStore.getDefaultType());
            trustStore.load(instream, keyStorePwd.toCharArray());
            SSLSocketFactory socketFactory = new SSLSocketFactory(trustStore);
            socketFactory.setHostnameVerifier(SSLSocketFactory.ALLOW_ALL_HOSTNAME_VERIFIER);
            SchemeRegistry schemeRegistry = new SchemeRegistry();
            schemeRegistry.register(new Scheme("http", PlainSocketFactory.getSocketFactory(), 80));
            schemeRegistry.register(new Scheme("https", socketFactory, 443));
            ClientConnectionManager cm = new ThreadSafeClientConnManager(params, schemeRegistry);
            httpClient = new DefaultHttpClient(cm, params);
            //httpClient = new DefaultHttpClient();
            //httpClient.getParams().setParameter("http.socket.timeout", new Integer(50000));
            //httpClient.getParams().setParameter("http.protocol.version", HttpVersion.HTTP_1_0);
            //httpClient.getConnectionManager().getSchemeRegistry().register(new Scheme("http", PlainSocketFactory.getSocketFactory(), 80));
            //httpClient.getConnectionManager().getSchemeRegistry().register(new Scheme("https", socketFactory, 443));
            
        } catch (Exception e) {
			e.printStackTrace();
		} finally {
            try {
				instream.close();
			} catch (IOException e) {
				e.printStackTrace();
			}
        }

        
	}
	private String host;
	private int port;
	
	
	private String protocolPrefix = "http";
	private String appscaleVersion = System.getProperty("APP_SCALE_VERSION");
	public HTTPClientDatastoreProxy(String host,int port,boolean isSSL) {
		this.host=host;
		this.port=port;
	
		if(isSSL) {
			protocolPrefix = "https";
		}
	}
	public HTTPClientDatastoreProxy(String host,int port,boolean isSSL,String appscaleVersion) {
		this.host=host;
		this.port=port;
		this.appscaleVersion=appscaleVersion;
		if(isSSL) {
			protocolPrefix = "https";
		}
	}
	private static User getUser() {
		UserService userService = UserServiceFactory.getUserService();
		return userService.getCurrentUser();
	}
	public byte[] doPost(String appId, String method, ProtocolMessage msg) {
		
		HttpPost postMethod = new HttpPost("/");
		System.out.println(postMethod.getURI());
		System.out.println("Request line:" + postMethod.getRequestLine());
		postMethod.addHeader("protocolbuffertype", "Request");
		postMethod.addHeader("Content-type","application/x-www-form-urlencoded");
		
		ResponseHandler<byte[]> responseHandler = new ByteArrayResponseHandler();
		
		String nickName = "Naruto"; // default user name
		String authDomain = "NinjiaVillage";
		String email = "naruto@ninjiaVillage.com";
		User user = getUser();
		StringBuffer appData = new StringBuffer(appId + ":" + email + ":" + nickName
		+ ":" + authDomain);
		if (user != null) {
			nickName = user.getNickname();
			authDomain = user.getAuthDomain();
			email = user.getEmail();
		}
		if (appscaleVersion != null) {
			appData.append(":" + appscaleVersion);
		}
		
		Request remoteRequest =  new Request();
		remoteRequest.setMethod(method);
		remoteRequest.setServiceName("datastore_v3");
		RawMessage rawMessage = remoteRequest.getMutableRequest();
		System.out.println("merging from original message!");
		rawMessage.mergeFromOther(msg);
		System.out.println("after merging the request is: " + remoteRequest.toFlatString());
		
		Response remoteResponse = new Response();
		
		
		
		postMethod.addHeader("appdata",appData.toString());
		//appData.append("\r\n");
		try {
			ByteArrayOutputStream bao = new ByteArrayOutputStream();
			bao.write(remoteRequest.toByteArray());
			ByteArrayEntity entity = new ByteArrayEntity(bao.toByteArray());
			bao.close();
			postMethod.setEntity(entity);
			if(httpClient == null) {
				System.err.println("httpclient is null. shouldnt happen");
			}
			byte[] arr = httpClient.execute(new HttpHost(this.host,port,protocolPrefix),postMethod,responseHandler);
			System.out.println("Done httpclient execute");
			System.out.println("parsing from response from pb server");
			remoteResponse.parseFrom(arr);
			if (!remoteResponse.hasResponse())
				System.out.println("no response from server for: "+ method + " method!");
			if (remoteResponse.hasApplicationError()){
				System.out.println("application error in "+ method+ " method !"+ remoteResponse.getApplicationError().toFlatString());
			}
			if (remoteResponse.hasException()){
				System.out.println("exception in "+ method+ " method! "+ remoteResponse.getException().toFlatString());
			}
			if (remoteResponse.hasJavaException()){
				System.out.println("java exception in "+ method + " method! "+ remoteResponse.getJavaException());
			}
			
			return remoteResponse.getResponse().toByteArray();
			
		} catch (ClientProtocolException e) {
			e.printStackTrace();
		} catch (IOException e) {
			e.printStackTrace();
		}catch(Exception e) {
			e.printStackTrace();
		}
		return null;
	}

	private class ByteArrayResponseHandler implements ResponseHandler<byte[]>  {
	    public byte[] handleResponse(
	            HttpResponse response) throws ClientProtocolException, IOException {
	    	System.out.println("Inside response handler");
	    	
	    	try {
	        HttpEntity entity = response.getEntity();
	        if (entity != null) {
	            //return EntityUtils.toByteArray(entity);
	        	return inputStreamToArray(entity.getContent());
	        } else {
	            return null;
	        }
	    	}finally {
	    		response.getEntity().consumeContent();
	    	}
	    }
	}
	
	private byte[] inputStreamToArray(InputStream in) {
		// BufferedReader reader = new BufferedReader(new
		// InputStreamReader(in));
		// // instram.re
		// // DataInputStream dia = new DataInputStream(in);
		// // dia.re
		// reader.re
		int len;
		int size = 10240;
		byte[] buf = null;
		try {
			if (in instanceof ByteArrayInputStream) {

	
					System.out.println("is a bytearray");
				size = in.available();

				buf = new byte[size];
				len = in.read(buf, 0, size);
			} else {
	
					System.out.println("normal");
				ByteArrayOutputStream bos = new ByteArrayOutputStream();
				buf = new byte[size];
				long t1 = System.nanoTime();
				while ((len = in.read(buf, 0, size)) != -1) {
	
						System.out.println("get data len: " + len);
					bos.write(buf, 0, len);
				}
				long t2 = System.nanoTime();
	
					System.out.println("wait reading time: " + (t2 - t1)
							/ 1000000.0);
				buf = bos.toByteArray();
				// System.out.println(new String(buf));

			}
			// System.out.println(new String(buf));
			in.close();
		} catch (IOException e) {
			e.printStackTrace();
		}
		// System.out.println(new String(buf));
		return buf;
	}
}
