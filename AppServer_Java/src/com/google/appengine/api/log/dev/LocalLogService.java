package com.google.appengine.api.log.dev;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.logservice.LogServicePb;
/*import com.google.apphosting.api.logservice.LogServicePb.LogLine;
import com.google.apphosting.api.logservice.LogServicePb.LogOffset;
import com.google.apphosting.api.logservice.LogServicePb.LogReadRequest;
import com.google.apphosting.api.logservice.LogServicePb.LogReadResponse;
import com.google.apphosting.api.logservice.LogServicePb.RequestLog; */
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.LinkedList;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.logging.Handler;

// AppScale imports
import com.google.gson.Gson;
import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.net.MalformedURLException;
import java.net.ProtocolException;
import java.net.URL;
import java.net.URLConnection;
import java.util.HashMap;
import java.net.HttpURLConnection;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.HostnameVerifier;
import org.apache.http.conn.ssl.X509HostnameVerifier;
/*
import com.google.appengine.api.urlfetch.HTTPHeader;
import com.google.appengine.api.urlfetch.HTTPMethod;
import com.google.appengine.api.urlfetch.HTTPRequest;
import com.google.appengine.api.urlfetch.URLFetchService;
import com.google.appengine.api.urlfetch.URLFetchServiceFactory;
*/
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.security.cert.X509Certificate;
import java.security.SecureRandom;
import org.apache.http.conn.ssl.SSLSocketFactory;
import javax.net.ssl.SSLContext;
import java.security.KeyManagementException;

import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.impl.conn.SingleClientConnManager;
import org.apache.http.conn.ClientConnectionManager;
import org.apache.http.conn.scheme.Scheme;
import org.apache.http.conn.scheme.SchemeRegistry;
import org.apache.http.entity.StringEntity;
import java.security.NoSuchAlgorithmException;
import javax.security.cert.CertificateException;
import javax.xml.bind.DatatypeConverter;

@ServiceProvider(LocalRpcService.class)
public class LocalLogService extends AbstractLocalRpcService
{
  public static final String PACKAGE = "logservice";
  private static final ThreadLocal<Long> threadLocalRsponseSize = new ThreadLocal();

  private final LinkedList<LogServicePb.RequestLog> logs = new LinkedList();
  private static final int MAX_NUM_LOGS = 1000;

  public String getPackage()
  {
    return "logservice";
  }

  public synchronized LogServicePb.LogReadResponse read(LocalRpcService.Status status, LogServicePb.LogReadRequest request)
  {
    LogServicePb.LogReadResponse response = new LogServicePb.LogReadResponse();
    Integer index = Integer.valueOf(0);

    if (request.hasOffset()) {
      index = null;
      int requestToFind = Integer.parseInt(request.getOffset().getRequestId());
      for (int i = 0; i < this.logs.size(); i++) {
        int thisRequestId = Integer.parseInt(((LogServicePb.RequestLog)this.logs.get(i)).getRequestId());
        if (requestToFind > thisRequestId) {
          index = Integer.valueOf(i);
          break;
        }

      }

      if (index == null) {
        return response;
      }
    }

    int numResultsFetched = 0;
    for (int i = index.intValue(); i < this.logs.size(); i++) {
      LogServicePb.RequestLog thisLog = null;
      int j = 0;
      for (LogServicePb.RequestLog log : this.logs) {
        if (i == j) {
          thisLog = log;
          break;
        }
        j++;
      }

      if ((!request.hasStartTime()) || 
        (request.getStartTime() <= thisLog.getEndTime()))
      {
        if ((!request.hasEndTime()) || 
          (request.getEndTime() > thisLog.getEndTime()))
        {
          if ((request.isIncludeIncomplete()) || (thisLog.isFinished()))
          {
            if ((!thisLog.hasVersionId()) || (request.versionIds().contains(thisLog.getVersionId())))
            {
              if (request.hasMinimumLogLevel())
              {
                boolean logLevelMatched = false;

                for (LogServicePb.LogLine line : thisLog.lines()) {
                  if (line.getLevel() >= request.getMinimumLogLevel()) {
                    logLevelMatched = true;
                    break;
                  }

                }

                if (!logLevelMatched);
              }
              else
              {
                if (request.isIncludeAppLogs()) {
                  response.addLog(thisLog);
                }
                else
                {
                  LogServicePb.RequestLog logCopy = (LogServicePb.RequestLog)thisLog.clone();
                  logCopy.clearLine();
                  response.addLog(logCopy);
                }

                numResultsFetched++;
                if (numResultsFetched >= request.getCount())
                {
                  if (i + 1 >= this.logs.size()) break;
                  String nextOffset = ((LogServicePb.RequestLog)this.logs.get(i)).getRequestId();
                  LogServicePb.LogOffset offset = new LogServicePb.LogOffset();
                  offset.setRequestId(nextOffset);
                  response.setOffset(offset);
                  break;
                }
              }
            }
          }
        }
      }
    }
    return response;
  }

  public synchronized void registerResponseSize(long responseSize)
  {
    threadLocalRsponseSize.set(Long.valueOf(responseSize));
  }

  @VisibleForTesting
  public synchronized Long getResponseSize() {
    return (Long)threadLocalRsponseSize.get();
  }

  public synchronized void clearResponseSize()
  {
    threadLocalRsponseSize.remove();
  }

  public synchronized void addRequestInfo(String appId, String versionId, String requestId, String ip, String nickname, long startTimeUsec, long endTimeUsec, String method, String resource, String httpVersion, String userAgent, boolean complete, Integer status, String referrer)
  {
    LogServicePb.RequestLog log = findLogInLogMapOrAddNewLog(requestId);
    log.setAppId(appId);

    String majorVersionId = versionId.split("\\.")[0];
    log.setVersionId(majorVersionId);
    log.setStartTime(startTimeUsec);
    log.setEndTime(endTimeUsec);
    if (ip != null) {
      log.setIp(ip);
    }

    if (nickname != null) {
      log.setNickname(nickname);
    }

    log.setLatency(endTimeUsec - startTimeUsec);
    log.setMcycles(0L);
    log.setMethod(method);
    log.setResource(resource);
    log.setHttpVersion(httpVersion);
    Long responseSize = getResponseSize();
    log.setResponseSize(responseSize == null ? 0L : responseSize.longValue());

    log.setCombined(formatCombinedLog(ip, nickname, endTimeUsec, method, resource, httpVersion, status, responseSize, referrer, userAgent));

    if (userAgent != null) {
      log.setUserAgent(userAgent);
    }

    log.setFinished(complete);
  }

  public synchronized void addAppLogLine(String requestId, long time, int level, String message) throws MalformedURLException, IOException, KeyManagementException, NoSuchAlgorithmException
  {
    if (message == null)
    {
      return;
    }
    LogServicePb.LogLine line = new LogServicePb.LogLine();
    line.setTime(time);
    line.setLevel(level);
    line.setLogMessage(message);

    // CGB
    HashMap<String, Object> logHash = new HashMap<String, Object>();
    System.out.println("time is " + time / 1e6);
    logHash.put("timestamp", time / 1e6);
    logHash.put("level", level);
    logHash.put("message", message);
    HashMap<String, Object>[] logList = new HashMap[1];
    logList[0] = logHash;
    

    Gson gson = new Gson();
    HashMap<String, Object> data = new HashMap<String, Object>();
    data.put("service_name", "appid");
    data.put("host", "192.168.10.2");
    data.put("logs", logList);

    /*
    SSLContext sslContext = SSLContext.getInstance("SSL");

    // set up a TrustManager that trusts everything
    sslContext.init(null, new TrustManager[] { new X509TrustManager() {
            public X509Certificate[] getAcceptedIssuers() {
                    return null;
            }

            public void checkClientTrusted(X509Certificate[] certs,
                            String authType) {
            }

            public void checkServerTrusted(X509Certificate[] certs,
                            String authType) {
            }
    } }, new SecureRandom());

    SSLSocketFactory sf = new SSLSocketFactory(sslContext);
    Scheme httpsScheme = new Scheme("https", 443, sf);
    SchemeRegistry schemeRegistry = new SchemeRegistry();
    schemeRegistry.register(httpsScheme);

    // apache HttpClient version >4.2 should use BasicClientConnectionManager
    ClientConnectionManager cm = new SingleClientConnManager(schemeRegistry);
    HttpClient client = new DefaultHttpClient(cm);
    */

    /*
    HostnameVerifier hostnameVerifier = org.apache.http.conn.ssl.SSLSocketFactory.ALLOW_ALL_HOSTNAME_VERIFIER;

    DefaultHttpClient client = new DefaultHttpClient();

    SchemeRegistry registry = new SchemeRegistry();
    SSLSocketFactory socketFactory = SSLSocketFactory.getSocketFactory();
    socketFactory.setHostnameVerifier((X509HostnameVerifier) hostnameVerifier);
    registry.register(new Scheme("https", socketFactory, 443));
    SingleClientConnManager mgr = new SingleClientConnManager(client.getParams(), registry);
    DefaultHttpClient httpClient = new DefaultHttpClient(mgr, client.getParams());

    // Set verifier     
    HttpsURLConnection.setDefaultHostnameVerifier(hostnameVerifier);
    */

    /*
DefaultHttpClient base = new DefaultHttpClient();
SSLContext ctx = SSLContext.getInstance("TLS");
X509TrustManager tm = new X509TrustManager() {

    public void checkClientTrusted(X509Certificate[] xcs, String string) {
    }

    public void checkServerTrusted(X509Certificate[] xcs, String string) {
    }

    public X509Certificate[] getAcceptedIssuers() {
        return null;
    }
};
ctx.init(null, new TrustManager[]{tm}, null);
SSLSocketFactory ssf = new SSLSocketFactory(ctx);
ssf.setHostnameVerifier(SSLSocketFactory.ALLOW_ALL_HOSTNAME_VERIFIER);
ClientConnectionManager ccm = base.getConnectionManager();
SchemeRegistry sr = ccm.getSchemeRegistry();
sr.register(new Scheme("https", ssf, 443));

DefaultHttpClient client = new DefaultHttpClient(ccm, base.getParams());

    HttpPost httpPost = new HttpPost("https://192.168.10.2:443/logs/upload");
    StringEntity entity = new StringEntity(gson.toJson(data), "UTF-8");
    entity.setContentType("application/json");
    httpPost.setEntity(entity);
    //HttpClient client = new DefaultHttpClient();
    client.execute(httpPost);
    */

    /*
    URLConnection connection = new URL("https://192.168.10.2:443/logs/upload").openConnection();
    connection.setDoOutput(true);  // Triggers POST.
    connection.setRequestProperty("Content-Type", "application-json");
    OutputStream output = null;
    try {
      output = connection.getOutputStream();
      output.write(gson.toJson(data).getBytes());
    } finally {
      if (output != null) try { output.close(); } catch (IOException logOrIgnore) {}
    }
    InputStream response = connection.getInputStream();
    */

    /*
    HttpURLConnection connection = (HttpURLConnection) new URL("https://192.168.10.2:443/logs/upload").openConnection();
    connection.setDoOutput(true);
    //connection.setRequestMethod("POST");
    connection.setRequestProperty("Content-Type", "application-json");
    OutputStream output = connection.getOutputStream();
    output.write(gson.toJson(data).getBytes());
    output.close();
    //OutputStreamWriter post = new OutputStreamWriter(connection.getOutputStream());
    //post.write(gson.toJson(data));
    //post.flush();
    //post.close();
    //connection.connect();
    InputStream response = connection.getInputStream();
    */

    /*URL url = new URL("https://192.168.10.2:443/logs/upload");
    HTTPRequest request = new HTTPRequest(url, HTTPMethod.POST);
    request.setHeader(new HTTPHeader("Content-Type", "application-json"));
    request.setPayload(gson.toJson(data).getBytes());
    URLFetchService fetcher = URLFetchServiceFactory.getURLFetchService();
    fetcher.fetch(request);
    */
      InputStream inStream = null;
      BufferedInputStream buf = null;
      InputStreamReader inStreamReader = null;
      BufferedReader bufferedReader = null;
      Runtime r = Runtime.getRuntime();
      String result = null;
      String base64Data = DatatypeConverter.printBase64Binary(gson.toJson(data).getBytes());
      try
      {
          System.out.println("trying to exec command: " + "python /root/appscale/AppServer_Java/src/com/google/appengine/api/log/dev/log_sender.py " + base64Data);
          Process p = r.exec("python /root/appscale/AppServer_Java/src/com/google/appengine/api/log/dev/log_sender.py " + base64Data);
          inStream = p.getInputStream();
          buf = new BufferedInputStream(inStream);
          inStreamReader = new InputStreamReader(buf);
          bufferedReader = new BufferedReader(inStreamReader);

          String outputLine;
          while ((outputLine = bufferedReader.readLine()) != null)
          {
              result = outputLine;
          }

          if (p.waitFor() != 0)
          {
              System.out.println("Executing python script returned unexpected value: " + p.waitFor());
          }
      }
      catch(Exception e)
      {
          System.out.println("Failed to execute REST call to save log: " + e.getMessage());
      }

    LogServicePb.RequestLog log = findLogInLogMapOrAddNewLog(requestId);
    log.addLine(line);
  }

  private synchronized LogServicePb.RequestLog findLogInLogMapOrAddNewLog(String requestId) {
    if (requestId == null) {
      requestId = "null";
    }

    for (int i = 0; i < this.logs.size(); i++) {
      LogServicePb.RequestLog possibleLog = (LogServicePb.RequestLog)this.logs.get(i);
      if (possibleLog.getRequestId().equals(requestId)) {
        return possibleLog;
      }

    }

    LogServicePb.RequestLog log = new LogServicePb.RequestLog();
    log.setRequestId(requestId);
    LogServicePb.LogOffset offset = new LogServicePb.LogOffset();
    offset.setRequestId(requestId);
    log.setOffset(offset);
    this.logs.addFirst(log);

    if (this.logs.size() > 1000) {
      this.logs.removeLast();
    }

    return log;
  }

  private String formatCombinedLog(String ip, String nickname, long endTimeUsec, String method, String resource, String httpVersion, Integer status, Long responseSize, String referrer, String userAgent)
  {
    String result = String.format("%1$s - %2$s [%3$s] \"%4$s %5$s %6$s\" %7$s %8$s %9$s %10$s", new Object[] { formatOptionalString(ip), formatOptionalString(nickname), formatTime(endTimeUsec), method, resource, httpVersion, formatOptionalInteger(status), formatResponseSize(responseSize), formatOptionalQuotedString(referrer), formatOptionalQuotedString(userAgent) });

    return result;
  }

  private String formatTime(long timeUsec)
  {
    SimpleDateFormat format = new SimpleDateFormat("d/MMM/yyyy:hh:mm:ss Z", Locale.ENGLISH);

    TimeZone zone = TimeZone.getTimeZone("PST");
    format.setTimeZone(zone);
    return format.format(new Date(timeUsec / 1000L));
  }

  private String formatOptionalQuotedString(String value)
  {
    if ((value == null) || (value.length() == 0)) {
      return "-";
    }
    return "\"" + value + "\"";
  }

  private String formatOptionalString(String value)
  {
    if ((value == null) || (value.length() == 0)) {
      return "-";
    }
    return value;
  }

  private String formatOptionalInteger(Integer value)
  {
    if (value == null) {
      return "-";
    }
    return value.toString();
  }

  private String formatResponseSize(Long responseSize)
  {
    if (responseSize == null) {
      return "-";
    }
    return Long.toString(responseSize.longValue());
  }

  public Handler getLogHandler() {
    return new DevLogHandler(this);
  }

  public synchronized void clear()
  {
    this.logs.clear();
  }
}
