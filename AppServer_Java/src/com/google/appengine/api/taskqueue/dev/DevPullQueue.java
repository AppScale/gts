package com.google.appengine.api.taskqueue.dev;


import java.util.ArrayList;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;

import org.quartz.Job;
import org.quartz.JobDetail;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.quartz.Scheduler;
import org.quartz.SchedulerException;
import org.quartz.SimpleTrigger;
import org.quartz.Trigger;
import org.quartz.spi.TriggerFiredBundle;

import com.google.appengine.api.taskqueue.QueueConstants;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueRetryParameters;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.QueueXml;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;


public class DevPullQueue extends DevQueue {
    private Map<String, TaskQueuePb.TaskQueueAddRequest> taskMap = Collections.synchronizedMap(new HashMap<String, TaskQueuePb.TaskQueueAddRequest>());
    private Clock clock;
    private double oneSecondInMilli = 1000;
    private double oneThousandSecondsInMilli = 1000000;
    private final Scheduler scheduler;
    private final String baseUrl;
    private final LocalTaskQueueCallback callback;
    private AppScaleTaskQueueClient client;


    TaskQueuePb.TaskQueueMode.Mode getMode() {
        return TaskQueuePb.TaskQueueMode.Mode.PULL;
    }

    DevPullQueue(QueueXml.Entry queueXmlEntry, Scheduler scheduler, String baseUrl, Clock clock, LocalTaskQueueCallback callback, AppScaleTaskQueueClient client) {
        super(queueXmlEntry);
        this.client = client;
        this.scheduler = scheduler;
        this.baseUrl = baseUrl;
        this.clock = clock;
        this.callback = callback;
    }

    synchronized TaskQueuePb.TaskQueueAddResponse add(TaskQueuePb.TaskQueueAddRequest addRequest) {
        String queueName = addRequest.getQueueName();
        if (addRequest.getMode() != TaskQueuePb.TaskQueueMode.Mode.PULL.getValue()) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_MODE.getValue());
        }
        if (!addRequest.getQueueName().equals(getQueueName())) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_REQUEST.getValue());
        }

        /*
         * AppScale - sending task to RabbitMQ instead of calling scheduleTask method
         */
        logger.log(Level.FINE, "PullQueue: sending AddRequest to TaskQueue server for " + queueName);
        TaskQueuePb.TaskQueueAddResponse addResponse = client.add(addRequest);
        return addResponse;
    }

    boolean deleteTask(String taskName) {
        return this.taskMap.remove(taskName) != null;
    }

    synchronized TaskQueuePb.TaskQueuePurgeQueueResponse purge(TaskQueuePb.TaskQueuePurgeQueueRequest purgeRequest) {
        String queueName = purgeRequest.getQueueName();
        if (!queueName.equals(getQueueName())) {
            throw new ApiProxy.ApplicationException(
                    TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_REQUEST.getValue());
        }

        logger.log(Level.FINE, "PullQueue: Sending PurgeQueueRequest to TaskQueue server for " + queueName);
        TaskQueuePb.TaskQueuePurgeQueueResponse purgeResponse = client.purge(purgeRequest);

        return purgeResponse;
    }

    QueueStateInfo getStateInfo() {
        ArrayList<QueueStateInfo.TaskStateInfo> taskInfoList = new ArrayList<QueueStateInfo.TaskStateInfo>();

        for (String taskName : getSortedTaskNames()) {
            TaskQueuePb.TaskQueueAddRequest addRequest = (TaskQueuePb.TaskQueueAddRequest) this.taskMap.get(taskName);
            if (addRequest == null) {
                continue;
            }
            long etaMillis = addRequest.getEtaUsec() / 1000L;
            taskInfoList.add(new QueueStateInfo.TaskStateInfo(taskName, etaMillis, addRequest, this.clock));
        }

        Collections.sort(taskInfoList, new Comparator<QueueStateInfo.TaskStateInfo>() {
            public int compare(QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2) {
                return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
            }
        });
        return new QueueStateInfo(this.queueXmlEntry, taskInfoList);
    }

    QueueStateInfo getStateInfoByTag(byte[] tag) {
        ArrayList<QueueStateInfo.TaskStateInfo> taskInfoList = new ArrayList<QueueStateInfo.TaskStateInfo>();

        for (String taskName : getSortedTaskNames()) {
            TaskQueuePb.TaskQueueAddRequest addRequest = (TaskQueuePb.TaskQueueAddRequest) this.taskMap.get(taskName);
            if (addRequest == null) {
                continue;
            }
            long etaMillis = addRequest.getEtaUsec() / 1000L;
            taskInfoList.add(new QueueStateInfo.TaskStateInfo(taskName, etaMillis, addRequest, this.clock));
        }
        if (tag == null) {
            QueueStateInfo.TaskStateInfo firstTask = (QueueStateInfo.TaskStateInfo) Collections.min(taskInfoList, new Comparator<QueueStateInfo.TaskStateInfo>() {
                public int compare(QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2) {
                    return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
                }
            });
            if (firstTask != null) {
                tag = firstTask.getTagAsBytes();
            }
        }
        final byte[] chosenTag = tag == null ? null : (byte[]) tag.clone();

        Collections.sort(taskInfoList, new Comparator<QueueStateInfo.TaskStateInfo>() {
            public int compare(QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2) {
                byte[] tag1 = t1.getTagAsBytes();
                byte[] tag2 = t2.getTagAsBytes();
                if (Arrays.equals(tag1, tag2)) {
                    return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
                }

                if (Arrays.equals(tag1, chosenTag)) {
                    return -1;
                }
                if (Arrays.equals(tag2, chosenTag)) {
                    return 1;
                }

                return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
            }
        });
        ArrayList<QueueStateInfo.TaskStateInfo> taggedTaskInfoList = new ArrayList<QueueStateInfo.TaskStateInfo>();
        for (QueueStateInfo.TaskStateInfo t : taskInfoList) {
            byte[] taskTag = t.getTagAsBytes();
            if (!Arrays.equals(taskTag, chosenTag)) break;
            taggedTaskInfoList.add(t);
        }

        return new QueueStateInfo(this.queueXmlEntry, taggedTaskInfoList);
    }

    List<String> getSortedTaskNames() {
        List<String> taskNameList = new ArrayList<String>(this.taskMap.keySet());
        Collections.sort(taskNameList);
        return taskNameList;
    }

    boolean runTask(String taskName) {
        return false;
    }

    long currentTimeMillis() {
        if (this.clock != null) {
            return this.clock.getCurrentTime();
        }
        return System.currentTimeMillis();
    }

    int availableTaskCount(List<QueueStateInfo.TaskStateInfo> tasks, long nowMillis) {
        int index = Collections.binarySearch(tasks, new QueueStateInfo.TaskStateInfo(null, nowMillis, null, null), new Comparator<QueueStateInfo.TaskStateInfo>() {
            public int compare(QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2) {
                return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
            }
        });
        if (index < 0) {
            index = -index - 1;
        }
        return index;
    }

    synchronized TaskQueuePb.TaskQueueQueryAndOwnTasksResponse queryAndOwnTasks(TaskQueuePb.TaskQueueQueryAndOwnTasksRequest request) {
        double leaseSeconds = request.getLeaseSeconds();
        long maxTasks = request.getMaxTasks();
        boolean groupByTag = request.isGroupByTag();
        byte[] tag = request.getTagAsBytes();
        String logMessage = "DevPullQueue.queryAndOwnTasks: " + "queue=" + request.getQueueName() +
                            " | leaseSeconds=" + leaseSeconds + " | maxTasks=" + maxTasks;
        logger.log(Level.FINE, logMessage);

        if ((leaseSeconds < 0.0D) || (leaseSeconds > QueueConstants.maxLease(TimeUnit.SECONDS))) {
            throw new IllegalArgumentException("Invalid value for lease time.");
        }
        if ((maxTasks <= 0L) || (maxTasks > QueueConstants.maxLeaseCount())) {
            throw new IllegalArgumentException("Invalid value for lease count.");
        }

        TaskQueuePb.TaskQueueQueryAndOwnTasksResponse response = client.lease(request);
        return response;
    }

    synchronized TaskQueuePb.TaskQueueModifyTaskLeaseResponse modifyTaskLease(TaskQueuePb.TaskQueueModifyTaskLeaseRequest request) {
        TaskQueuePb.TaskQueueModifyTaskLeaseResponse response = new TaskQueuePb.TaskQueueModifyTaskLeaseResponse();

        TaskQueuePb.TaskQueueAddRequest task = (TaskQueuePb.TaskQueueAddRequest) this.taskMap.get(request.getTaskName());

        if (task == null) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.UNKNOWN_TASK.getValue());
        }

        if (task.getEtaUsec() != request.getEtaUsec()) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_LEASE_EXPIRED.getValue());
        }

        long timeNowUsec = System.currentTimeMillis() * (long) oneSecondInMilli;
        if (task.getEtaUsec() < timeNowUsec) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_LEASE_EXPIRED.getValue());
        }

        long requestLeaseUsec = (long) (request.getLeaseSeconds() * oneThousandSecondsInMilli);
        long etaUsec = timeNowUsec + requestLeaseUsec;
        task.setEtaUsec(etaUsec);
        response.setUpdatedEtaUsec(etaUsec);
        return response;
    }
}