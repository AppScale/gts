package com.google.appengine.api.taskqueue.dev;


import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLEncoder;
import java.util.logging.Logger;

import com.google.appengine.api.memcache.dev.LocalMemcacheService;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;


public class AppScaleRunTask extends Thread
{

    private static final Logger logger = Logger.getLogger(AppScaleRunTask.class.getName());
    String                      ip     = System.getProperty("MY_IP_ADDRESS");
    String                      port   = System.getProperty("MY_PORT");
    String                      method;
    String                      url;
    String                      body;

    public AppScaleRunTask( TaskQueuePb.TaskQueueAddRequest addRequest )
    {
        logger.fine("Sending a task request, ip is [" + ip + "], port is [" + port + "]");
        logger.fine("The requested body: " + addRequest.getBody());
        logger.fine("The requested url: " + addRequest.getUrl());

        url = addRequest.getUrl();

        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.DELETE.getValue()) method = "DELETE";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.GET.getValue()) method = "GET";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.POST.getValue()) method = "POST";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.PUT.getValue()) method = "PUT";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.HEAD.getValue()) method = "HEAD";

        logger.fine("The requested method: " + method);
        body = addRequest.getBody();
    }

    @Override
    public void run()
    {
        logger.info("Opening connection: " + "http://" + this.ip + ":" + this.port + this.url + "in AppScaleRunTask");
        URL u;
        HttpURLConnection con = null;
        OutputStreamWriter wr = null;
        BufferedReader rd = null;
        try
        {
            u = new URL("http://" + this.ip + ":" + this.port + this.url);
            con = (HttpURLConnection)u.openConnection();
            con.setRequestMethod(this.method);

            // Construct data
            String[] data1 = this.body.split("&");

            String data = new String();
            for (int i = 0; i < data1.length; i++)
            {
                String[] subdata = data1[i].split("=");
                if (i != 0) data += "&";
                data += URLEncoder.encode(subdata[0], "UTF-8") + "=" + URLEncoder.encode(subdata[1], "UTF-8");
            }

            logger.fine("The data to post: " + data);

            // Send data

            con.setDoOutput(true);
            wr = new OutputStreamWriter(con.getOutputStream());
            wr.write(data);
            wr.flush();

            // Get the response
            rd = new BufferedReader(new InputStreamReader(con.getInputStream()));
            String line;
            while ((line = rd.readLine()) != null)
            {
                System.out.println(line);
            }
            // wr.close();

        }
        catch (MalformedURLException e)
        {
            e.printStackTrace();
        }
        catch (IOException e)
        {
            e.printStackTrace();
        }
        finally
        {
            try
            {
                if (rd != null) rd.close();
                if (wr != null) wr.close();
                if (con != null) con.disconnect();
            }
            catch (IOException e)
            {
                e.printStackTrace();
            }

        }
    }

}
