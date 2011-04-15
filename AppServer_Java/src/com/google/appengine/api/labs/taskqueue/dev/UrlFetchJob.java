package com.google.appengine.api.labs.taskqueue.dev;

import java.util.Date;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.quartz.Job;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.quartz.Scheduler;
import org.quartz.SchedulerException;
import org.quartz.SimpleTrigger;
import org.quartz.Trigger;

import com.google.appengine.api.labs.taskqueue.TaskQueuePb;
import com.google.appengine.api.urlfetch.URLFetchServicePb;
import com.google.appengine.api.urlfetch.dev.LocalURLFetchService;
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServerEnvironment;

public class UrlFetchJob
  implements Job
{
  private static final Logger logger = Logger.getLogger(UrlFetchJob.class.getName());
  static final String X_GOOGLE_DEV_APPSERVER_SKIPADMINCHECK = "X-Google-DevAppserver-SkipAdminCheck";
  static final String X_APPENGINE_QUEUE_NAME = "X-AppEngine-QueueName";
  static final String X_APPENGINE_TASK_NAME = "X-AppEngine-TaskName";
  static final String X_APPENGINE_TASK_RETRY_COUNT = "X-AppEngine-TaskRetryCount";
  private static LocalURLFetchService fetchService;
  private static LocalServerEnvironment localServerEnvironment;
  private static Clock clock;

  static URLFetchServicePb.URLFetchRequest.RequestMethod translateRequestMethod(TaskQueuePb.TaskQueueAddRequest.RequestMethod rm)
  {
    return URLFetchServicePb.URLFetchRequest.RequestMethod.valueOf(rm.name());
  }

  public void execute(JobExecutionContext context)
    throws JobExecutionException
  {
    try
    {
      localServerEnvironment.waitForServerToStart();
    } catch (InterruptedException e) {
      throw new JobExecutionException("Interrupted while waiting for server to initialize.", e, false);
    }

    UrlFetchJobDetail jd = (UrlFetchJobDetail)context.getJobDetail();
    URLFetchServicePb.URLFetchRequest fetchReq = newFetchRequest(jd.getAddRequest(), jd.getServerUrl(), jd.getRetryCount());

    int status = execute(fetchReq);

    if (status != 200) {
      logger.info(String.format("Web hook at %s returned status code %d.  Rescheduling...", new Object[] { fetchReq.getUrl(), Integer.valueOf(status) }));

      reschedule(context.getScheduler(), context.getTrigger(), jd);
    }
  }

  private void reschedule(Scheduler scheduler, Trigger trigger, UrlFetchJobDetail jd) {
    jd.incrementRetryCount();
    int retryDelayMs = jd.incrementRetryDelayMs();

    SimpleTrigger newTrigger = new SimpleTrigger(trigger.getJobName(), trigger.getGroup());
    newTrigger.setStartTime(new Date(clock.getCurrentTime() + retryDelayMs));
    try
    {
      scheduler.unscheduleJob(trigger.getJobName(), trigger.getGroup());
      scheduler.scheduleJob(jd, newTrigger);
    } catch (SchedulerException e) {
      logger.log(Level.SEVERE, String.format("Reschedule of task %s failed.", new Object[] { jd.getAddRequest() }), e);
    }
  }

  int execute(URLFetchServicePb.URLFetchRequest fetchReq)
    throws JobExecutionException
  {
    LocalRpcService.Status status = new LocalRpcService.Status();
    return fetchService.fetch(status, fetchReq).getStatusCode();
  }

  URLFetchServicePb.URLFetchRequest newFetchRequest(TaskQueuePb.TaskQueueAddRequest addReq, String serverUrl, int retryCount)
  {
    URLFetchServicePb.URLFetchRequest.Builder requestProto = URLFetchServicePb.URLFetchRequest.newBuilder();
    requestProto.setUrl(serverUrl + addReq.getUrl());

    if (addReq.hasBody()) {
      requestProto.setPayload(ByteString.copyFrom(addReq.getBodyAsBytes()));
    }
    requestProto.setMethod(translateRequestMethod(addReq.getMethodEnum()));

    addHeadersToFetchRequest(requestProto, addReq, retryCount);

    if (requestProto.getMethod() == URLFetchServicePb.URLFetchRequest.RequestMethod.PUT)
    {
      requestProto.setFollowRedirects(false);
    }

    return requestProto.build();
  }

  private void addHeadersToFetchRequest(URLFetchServicePb.URLFetchRequest.Builder requestProto, TaskQueuePb.TaskQueueAddRequest addReq, int retryCount)
  {
    for (TaskQueuePb.TaskQueueAddRequest.Header header : addReq.headers()) {
      requestProto.addHeader(buildHeader(header.getKey(), header.getValue()));
    }

    requestProto.addHeader(buildHeader("X-Google-DevAppserver-SkipAdminCheck", "true"));

    requestProto.addHeader(buildHeader("X-AppEngine-QueueName", addReq.getQueueName()));
    requestProto.addHeader(buildHeader("X-AppEngine-TaskName", addReq.getTaskName()));
    requestProto.addHeader(buildHeader("X-AppEngine-TaskRetryCount", Integer.valueOf(retryCount).toString()));
  }

  private URLFetchServicePb.URLFetchRequest.Header.Builder buildHeader(String key, String value)
  {
    URLFetchServicePb.URLFetchRequest.Header.Builder headerProto = URLFetchServicePb.URLFetchRequest.Header.newBuilder();
    headerProto.setKey(key);
    headerProto.setValue(value);
    return headerProto;
  }

  static void initialize(LocalURLFetchService _fetchService, LocalServerEnvironment _localServerEnvironment, Clock _clock)
  {
    fetchService = _fetchService;
    localServerEnvironment = _localServerEnvironment;
    clock = _clock;
  }

  static LocalURLFetchService getFetchService() {
    return fetchService;
  }
}