package com.google.appengine.api.taskqueue.dev;

import java.util.UUID;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.BufferedReader;
import java.io.FileReader;
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

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Request;
import com.google.apphosting.utils.remoteapi.RemoteApiPb.Response;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest.Header;
import com.google.apphosting.utils.config.AppEngineWebXml;

public class AppScaleTaskQueueClient
{
    private static final Logger logger                            = Logger.getLogger(AppScaleTaskQueueClient.class.getName());

    private DefaultHttpClient   client                              = null;
    private String              url                                 = null;
    private String              appId                               = null;
    private final int           port                                = 64839;
    private final int           MAX_TOTAL_CONNECTIONS               = 200;
    private final int           MAX_CONNECTIONS_PER_ROUTE           = 20;
    private final int           MAX_CONNECTIONS_PER_ROUTE_LOCALHOST = 80;
    private final int           INPUT_STREAM_SIZE                   = 10240;
    private final String        APPDATA_HEADER                      = "AppData";
    private final String        SERVICE_NAME                        = "taskqueue";
    private final String        PROTOCOL_BUFFER_HEADER              = "ProtocolBufferType";
    private final String        PROTOCOL_BUFFER_VALUE               = "Request";
    private final String        TASKQUEUE_IP_FILE                   = "/etc/appscale/rabbitmq_ip";

    public AppScaleTaskQueueClient()
    {
        SchemeRegistry schemeRegistry = new SchemeRegistry();
        schemeRegistry.register(new Scheme("http", PlainSocketFactory.getSocketFactory(), port));
        ThreadSafeClientConnManager connManager = new ThreadSafeClientConnManager(schemeRegistry);
        connManager.setMaxTotal(MAX_TOTAL_CONNECTIONS);
        connManager.setDefaultMaxPerRoute(MAX_CONNECTIONS_PER_ROUTE);
        String host = getTaskQueueIp();
        url = "http://" + host + ":" + port + "/";
        HttpHost localhost = new HttpHost(url);
        connManager.setMaxForRoute(new HttpRoute(localhost), MAX_CONNECTIONS_PER_ROUTE_LOCALHOST);
        
        client = new DefaultHttpClient(connManager);
        appId = getAppId();
    }

    public TaskQueuePb.TaskQueueAddResponse add(TaskQueuePb.TaskQueueAddRequest addRequest)
    {
        System.out.println("Add called, url: " + url + " , appId: " + appId);
        //update some of the AddRequest params
        addRequest.setAppId(appId);
        String taskPath = addRequest.getUrl();
        String appScaleTaskPath = "http://" + getNginxHost() + ":" + getNginxPort() + taskPath;
        addRequest.setUrl(appScaleTaskPath);
        System.out.println("Modified request: " + addRequest);
        //Create a PB request
        Request request = new Request();
        request.setMethod("Add");
        request.setServiceName(SERVICE_NAME);
        request.setRequestAsBytes(addRequest.toByteArray());
        Response response = sendRequest(request);
        TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();
        addResponse.parseFrom(response.getResponseAsBytes());
        System.out.println("TQ Add got response: " + addResponse);
        return addResponse;         
    }
   
    private Response sendRequest(Request request)
    {
        System.out.println("In SendRequest");
        HttpPost post = new HttpPost(url);
        post.addHeader(PROTOCOL_BUFFER_HEADER, PROTOCOL_BUFFER_VALUE);
        String tag = appId;
        post.addHeader(APPDATA_HEADER, tag);
        ByteArrayOutputStream bao = new ByteArrayOutputStream();
        try
        {
            bao.write(request.toByteArray());
            ByteArrayEntity entity = new ByteArrayEntity(bao.toByteArray());
            post.setEntity(entity);
            bao.close();
        }
        catch (IOException e)
        {
	    System.out.println("caught ioexception");
            logger.severe("Failed to create TaskQueue request due to IOException: " + e.getMessage());
            return null;
        }

        Response remoteResponse = new Response();
        ByteArrayResponseHandler handler = new ByteArrayResponseHandler();
        try
        {
            byte[] bytes = client.execute(post, handler);
            remoteResponse.parseFrom(bytes);
        }
        catch (ClientProtocolException e)
        {
            System.out.println("caught cpe exception");
            logger.severe("Failed to send TaskQueue request due to ClientProtocolException: " + e.getMessage());
        }
        catch (IOException e)
        {
            System.out.println("caught ioexception");
            logger.severe("Failed to send TaskQueue request due to IOException: " + e.getMessage());
        }
        System.out.println("returning remoteresponse: " + remoteResponse);
        return remoteResponse;
    }
    
    private String getNginxHost()
    {
        String nginxHost = System.getProperty("NGINX_ADDR");
        return nginxHost;
    }

    private String getNginxPort()
    {
        String nginxPort = System.getProperty("NGINX_PORT");
        return nginxPort;
    }

    private String getAppId()
    {
        String appId = System.getProperty("APPLICATION_ID");
        System.out.println("ApplicationId is: " + appId);
        return appId;
    }

    private String getTaskQueueIp()
    {   
        String ip = "";
        try
        {
            BufferedReader br = new BufferedReader(new FileReader(TASKQUEUE_IP_FILE));
            ip = br.readLine(); 
            br.close();
        }
        catch(Exception e)
        {
            logger.severe("Error getting ip from taskqueue ip file: " + e.getMessage());
        }
        return ip;
    }

    class ByteArrayResponseHandler implements ResponseHandler<byte[]>
    {

        public byte[] handleResponse( HttpResponse response ) throws ClientProtocolException, IOException
        {
            HttpEntity entity = response.getEntity();
            if (entity != null)
            {
                InputStream inputStream = entity.getContent();
                try
                {
                    return inputStreamToArray(inputStream);
                }
                finally
                {
                    entity.getContent().close();
                }
            }
            System.out.println("entity was null");
            return new byte[] {};
        }
    }

    private byte[] inputStreamToArray( InputStream in )
    {
        int len;
        int size = INPUT_STREAM_SIZE;
        byte[] buf = null;
        try
        {
            if (in instanceof ByteArrayInputStream)
            {
                size = in.available();
                buf = new byte[size];
                len = in.read(buf, 0, size);
            }
            else
            {
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                buf = new byte[size];
                while ((len = in.read(buf, 0, size)) != -1)
                {
                    bos.write(buf, 0, len);
                }
                buf = bos.toByteArray();

            }
            in.close();
        }
        catch (IOException e)
        {
            e.printStackTrace();
        }
        return buf;
    }
}
