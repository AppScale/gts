package com.google.appengine.api.log.dev;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.logservice.LogServicePb;
import com.google.apphosting.api.logservice.LogServicePb.LogModuleVersion;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TimeZone;
import java.util.logging.Handler;

// AppScale imports
import com.google.apphosting.api.ApiProxy.CallNotFoundException;
import com.google.gson.Gson;
import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.net.URL;
import java.net.URLConnection;
import java.util.HashMap;
import java.util.Map;
import javax.xml.bind.DatatypeConverter;

@ServiceProvider(LocalRpcService.class)
public class LocalLogService extends AbstractLocalRpcService
{
  public static final String PACKAGE = "logservice";
  private static final String DEFAULT_SERVER = "default";  
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

    Set requestedIds = null;
    if (!request.requestIds().isEmpty()) {
      requestedIds = new HashSet(request.requestIds());
    }

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

      if ((requestedIds == null) || (requestedIds.contains(thisLog.getRequestId())))
      {
        if ((!request.hasStartTime()) || 
          (request.getStartTime() <= thisLog.getEndTime()))
        {
          if ((!request.hasEndTime()) || 
            (request.getEndTime() > thisLog.getEndTime()))
          {
            if ((request.isIncludeIncomplete()) || (thisLog.isFinished()))
            {
              if ((request.versionIds().size() <= 0) || (request.versionIds().contains(thisLog.getVersionId())) || (!thisLog.hasVersionId()))
              {
                if ((request.moduleVersions().size() > 0) && ((thisLog.hasModuleId()) || (thisLog.hasVersionId())))
                {
                  boolean serverVersionMatch = false;
                  for (LogServicePb.LogModuleVersion moduleVersion : request.moduleVersions()) {
                    if ((thisLog.getModuleId().equals(moduleVersion.getModuleId())) && (thisLog.getVersionId().equals(moduleVersion.getVersionId())))
                    {
                      serverVersionMatch = true;
                    }

                  }

                  if (!serverVersionMatch);
                }
                else if (request.hasMinimumLogLevel())
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

  public void addRequestInfo(String appId, String versionId, String requestId, String ip, String nickname, long startTimeUsec, long endTimeUsec, String method, String resource, String httpVersion, String userAgent, boolean complete, Integer status, String referrer)
  {
    addRequestInfo(appId, "default", versionId, requestId, ip, nickname, startTimeUsec, endTimeUsec, method, resource, httpVersion, userAgent, complete, status, referrer);
  }

  public synchronized void addRequestInfo(String appId, String moduleId, String versionId, String requestId, String ip, String nickname, long startTimeUsec, long endTimeUsec, String method, String resource, String httpVersion, String userAgent, boolean complete, Integer status, String referrer)
  {
    LogServicePb.RequestLog log = findLogInLogMapOrAddNewLog(requestId);
    log.setAppId(appId);

    String majorVersionId = versionId.split("\\.")[0];
    if (moduleId.equals("default")) {
      log.setModuleId(moduleId);
    }
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

  public synchronized void addAppLogLine(String requestId, long time, int level, String message)
  {
    if (message == null)
    {
      return;
    }
    LogServicePb.LogLine line = new LogServicePb.LogLine();
    line.setTime(time);
    line.setLevel(level);
    line.setLogMessage(message);

    // Send the log to the Admin Console for later viewing
    HashMap<String, Object> logHash = new HashMap<String, Object>();
    logHash.put("timestamp", time / 1e6);
    logHash.put("level", level);
    logHash.put("message", message);
    HashMap<String, Object>[] logList = new HashMap[1];
    logList[0] = logHash;

    Gson gson = new Gson();
    HashMap<String, Object> data = new HashMap<String, Object>();
    data.put("service_name", System.getProperty("APPLICATION_ID"));
    data.put("logs", logList);
    data.put("host", System.getProperty("MY_IP_ADDRESS"));

    try {
        String jsonData = gson.toJson(data);
        String request = "https://" + System.getProperty("LOGIN_SERVER") + ":1443/logs/upload";
        URL url = new URL(request); 
        URLConnection connection = url.openConnection();
        connection.setDoOutput(true);

        OutputStreamWriter writer = new OutputStreamWriter(connection.getOutputStream());

        writer.write(jsonData);
        writer.flush();

        BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream()));

        writer.close();
        reader.close();
    } catch (IOException e) {
        System.out.println("[IOException] Failed to execute REST call to save log: " + e.getMessage());
    } catch (CallNotFoundException e) {
        // This is commented out because otherwise it floods the logs.
        //System.out.println("[CallNotFoundException] Failed to execute REST call to save log: " + e.getMessage());
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
