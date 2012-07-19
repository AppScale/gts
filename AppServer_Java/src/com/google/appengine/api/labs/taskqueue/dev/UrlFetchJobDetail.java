package com.google.appengine.api.labs.taskqueue.dev;

import org.quartz.JobDataMap;
import org.quartz.JobDetail;

import com.google.appengine.api.taskqueue.TaskQueuePb;

class UrlFetchJobDetail extends JobDetail
{
  /**
	 * 
	 */
	private static final long serialVersionUID = 1L;
private static final String ADD_REQUEST_PROP = "addRequest";
  private static final String SERVER_URL = "serverUrl";
  private static final String RETRY_COUNT = "retryCount";
  private static final String RETRY_DELAY_MS = "retryDelayMs";
  private static final int INITIAL_RETRY_DELAY_MS = 100;
  private static final int MAX_RETRY_DELAY_MS = 3600000;

  UrlFetchJobDetail(String taskName, String queueName, TaskQueuePb.TaskQueueAddRequest addRequest, String url)
  {
    this(taskName, queueName, addRequest, url, UrlFetchJob.class);
  }

  UrlFetchJobDetail(String taskName, String queueName, TaskQueuePb.TaskQueueAddRequest addRequest, String url, Class<? extends UrlFetchJob> jobClass)
  {
    super(taskName, queueName, jobClass);
    JobDataMap dataMap = getJobDataMap();
    dataMap.put("addRequest", addRequest);
    dataMap.put("serverUrl", url);
    dataMap.put("retryCount", 0);

    dataMap.put("retryDelayMs", 50);
  }

  TaskQueuePb.TaskQueueAddRequest getAddRequest() {
    return ((TaskQueuePb.TaskQueueAddRequest)getJobDataMap().get("addRequest"));
  }

  String getServerUrl() {
    return ((String)getJobDataMap().get("serverUrl"));
  }

  int getRetryCount() {
    return ((Integer)getJobDataMap().get("retryCount")).intValue();
  }

  int getRetryDelayMs() {
    return ((Integer)getJobDataMap().get("retryDelayMs")).intValue();
  }

  int incrementRetryCount()
  {
    int newRetryCount = getRetryCount() + 1;
    getJobDataMap().put("retryCount", newRetryCount);
    return newRetryCount;
  }

  int incrementRetryDelayMs()
  {
    int newRetryDelayMs = Math.min(getRetryDelayMs() * 2, getMaxRetryDelayMs());
    getJobDataMap().put("retryDelayMs", newRetryDelayMs);
    return newRetryDelayMs;
  }

  int getMaxRetryDelayMs()
  {
    return 3600000;
  }
}
