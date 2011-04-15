package com.google.appengine.api.labs.taskqueue.dev;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;

import com.google.appengine.api.labs.taskqueue.TaskQueuePb;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.utils.config.QueueXml;

public final class QueueStateInfo
{
  private final QueueXml.Entry entry;
  private final List<TaskStateInfo> taskInfo;

  public QueueStateInfo(QueueXml.Entry entry, List<TaskStateInfo> taskInfo)
  {
    this.entry = entry;
    this.taskInfo = taskInfo;
  }

  public QueueXml.Entry getEntry() {
    return this.entry;
  }

  public int getBucketSize() {
    if (this.entry.getBucketSize() == null) {
      return 5;
    }
    return this.entry.getBucketSize().intValue();
  }

  public List<TaskStateInfo> getTaskInfo() {
    return this.taskInfo;
  }

  public int getCountTasks() {
    return this.taskInfo.size();
  }

  public int getCountUnfinishedTasks() {
    return this.taskInfo.size();
  }

  public Date getOldestTaskEta() {
    if (this.taskInfo.size() == 0) {
      return null;
    }
    return new Date(((TaskStateInfo)this.taskInfo.get(0)).getEtaMillis());
  }

  public static final class HeaderWrapper
  {
    private final TaskQueuePb.TaskQueueAddRequest.Header delegate;

    private HeaderWrapper(TaskQueuePb.TaskQueueAddRequest.Header delegate)
    {
      this.delegate = delegate;
    }

    public String getKey() {
      return this.delegate.getKey();
    }

    public String getValue() {
      return this.delegate.getValue();
    }
  }

  public static final class TaskStateInfo
  {
    private final String taskName;
    private final long etaMillis;
    private final TaskQueuePb.TaskQueueAddRequest addRequest;
    private final Clock clock;

    public TaskStateInfo(String taskName, long etaMillis, TaskQueuePb.TaskQueueAddRequest addRequest, Clock clock)
    {
      this.taskName = taskName;
      this.etaMillis = etaMillis;
      this.addRequest = addRequest;
      this.clock = clock;
    }

    public String getTaskName() {
      return this.taskName;
    }

    public long getEtaMillis() {
      return this.etaMillis;
    }

    public Date getEta() {
      return new Date(this.etaMillis);
    }

    public double getEtaDelta() {
      double delta = this.etaMillis - this.clock.getCurrentTime();
      return (delta / 1000.0D);
    }

    public String getMethod() {
      return TaskQueuePb.TaskQueueAddRequest.RequestMethod.valueOf(this.addRequest.getMethod()).name();
    }

    public String getUrl() {
      return this.addRequest.getUrl();
    }

    public String getBody() {
      return this.addRequest.getBody();
    }

    public List<QueueStateInfo.HeaderWrapper> getHeaders() {
      if (this.addRequest.headers() == null) {
        return Collections.emptyList();
      }

      List wrappedHeaders = new ArrayList();
      for (TaskQueuePb.TaskQueueAddRequest.Header header : this.addRequest.headers()) {
        wrappedHeaders.add(new QueueStateInfo.HeaderWrapper(header));
      }
      return wrappedHeaders;
    }

    TaskQueuePb.TaskQueueAddRequest getAddRequest()
    {
      return this.addRequest;
    }
  }
}