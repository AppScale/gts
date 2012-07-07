package com.google.appengine.api.taskqueue.dev;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLEncoder;

import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;


public class AppScaleRunTask extends Thread {

    String ip = System.getProperty("MY_IP_ADDRESS");
    String port = System.getProperty("MY_PORT");
    String method;
    String url;
    String body;

    public AppScaleRunTask(TaskQueuePb.TaskQueueAddRequest addRequest) {
        System.out.println("sending a task request...");
        System.out.println("ip is: " + ip);
        System.out.println("port is: " + port);

        System.out.println("the requested url: " + addRequest.getUrl());
        url = addRequest.getUrl();
        System.out.println("the requested body: " + addRequest.getBody());

        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.DELETE
                .getValue())
            method = "DELETE";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.GET
                .getValue())
            method = "GET";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.POST
                .getValue())
            method = "POST";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.PUT
                .getValue())
            method = "PUT";
        if (addRequest.getMethod() == TaskQueueAddRequest.RequestMethod.HEAD
                .getValue())
            method = "HEAD";
        System.out.println("the requested method: " + method);
        body = addRequest.getBody();

    }

    @Override
    public void run() {
        System.out.println("opening connection: " + "http://" + this.ip + ":"
                + this.port + this.url);
        URL u;
        HttpURLConnection con = null;
        OutputStreamWriter wr = null;
        BufferedReader rd = null;
        try {
            u = new URL("http://" + this.ip + ":" + this.port + this.url);
            con = (HttpURLConnection) u.openConnection();
            con.setRequestMethod(this.method);

            // Construct data
            String[] data1 = this.body.split("&");

            String data = new String();
            for (int i = 0; i < data1.length; i++) {
                String[] subdata = data1[i].split("=");
                if (i != 0)
                    data += "&";
                data += URLEncoder.encode(subdata[0], "UTF-8") + "="
                        + URLEncoder.encode(subdata[1], "UTF-8");
            }

            System.out.println("the data to post: " + data);

            // Send data

            con.setDoOutput(true);
            wr = new OutputStreamWriter(con.getOutputStream());
            wr.write(data);
            wr.flush();

            // Get the response
            rd = new BufferedReader(new InputStreamReader(con.getInputStream()));
            String line;
            while ((line = rd.readLine()) != null) {
                System.out.println(line);
            }
            // wr.close();

        } catch (MalformedURLException e) {
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            try {
                if (rd != null)
                    rd.close();
                if (wr != null)
                    wr.close();
                if (con != null)
                    con.disconnect();
            } catch (IOException e) {
                e.printStackTrace();
            }

        }
    }

}
