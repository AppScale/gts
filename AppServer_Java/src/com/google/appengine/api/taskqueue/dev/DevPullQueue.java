package com.google.appengine.api.taskqueue.dev;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import com.google.appengine.api.taskqueue.QueueConstants;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.QueueXml;

public class DevPullQueue extends DevQueue {
    private Map<String, TaskQueuePb.TaskQueueAddRequest> taskMap = Collections.synchronizedMap(new HashMap<String, TaskQueuePb.TaskQueueAddRequest>());
    private Clock clock;

    TaskQueuePb.TaskQueueMode.Mode getMode() {
        return TaskQueuePb.TaskQueueMode.Mode.PULL;
    }

    DevPullQueue(QueueXml.Entry queueXmlEntry, AtomicInteger taskNameGenerator, Clock clock) {
        super(queueXmlEntry, taskNameGenerator);
        this.clock = clock;
    }

    synchronized TaskQueuePb.TaskQueueAddResponse add(TaskQueuePb.TaskQueueAddRequest addRequest) {
        System.out.println("PULL Queue: add a task request");
        if (addRequest.getMode() != TaskQueuePb.TaskQueueMode.Mode.PULL.getValue()) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_MODE.getValue());
        }
        if (!addRequest.getQueueName().equals(getQueueName())) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_REQUEST.getValue());
        }
        String taskName;
        if ((addRequest.hasTaskName()) && (!addRequest.getTaskName().equals(""))) {
            taskName = addRequest.getTaskName();
        } else {
            taskName = genTaskName();
        }
        if (this.taskMap.containsKey(taskName)) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_ALREADY_EXISTS.getValue());
        }
        this.taskMap.put(taskName, addRequest);

        TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();
        if ((!addRequest.hasTaskName()) || (addRequest.getTaskName().equals(""))) {
            addRequest.setTaskName(taskName);
            addResponse.setChosenTaskName(taskName);
        }

        return addResponse;
    }

    boolean deleteTask(String taskName) {
        return this.taskMap.remove(taskName) != null;
    }

    void flush() {
        this.taskMap.clear();
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
            QueueStateInfo.TaskStateInfo firstTask = (QueueStateInfo.TaskStateInfo) Collections
                    .min(taskInfoList, new Comparator<QueueStateInfo.TaskStateInfo>() {
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
            if (!Arrays.equals(taskTag, chosenTag))
                break;
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
        System.out.println("PULL Queue: actually run the task");
        return false;
    }

    long currentTimeMillis() {
        if (this.clock != null) {
            return this.clock.getCurrentTime();
        }
        return System.currentTimeMillis();
    }

    int availableTaskCount(List<QueueStateInfo.TaskStateInfo> tasks, long nowMillis) {
        int index = Collections
                .binarySearch(tasks, new QueueStateInfo.TaskStateInfo(null, nowMillis, null, null), new Comparator<QueueStateInfo.TaskStateInfo>() {
                    public int compare(QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2) {
                        return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
                    }
                });
        if (index < 0) {
            index = -index - 1;
        }
        return index;
    }

    synchronized List<TaskQueuePb.TaskQueueAddRequest> queryAndOwnTasks(double leaseSeconds, long maxTasks, boolean groupByTag, byte[] tag) {
        if ((leaseSeconds < 0.0D) || (leaseSeconds > QueueConstants.maxLease(TimeUnit.SECONDS))) {
            throw new IllegalArgumentException("Invalid value for lease time.");
        }
        if ((maxTasks <= 0L) || (maxTasks > QueueConstants.maxLeaseCount())) {
            throw new IllegalArgumentException("Invalid value for lease count.");
        }

        List<QueueStateInfo.TaskStateInfo> tasks = groupByTag ? getStateInfoByTag(tag).getTaskInfo() : getStateInfo()
                .getTaskInfo();

        long nowMillis = currentTimeMillis();
        int available = availableTaskCount(tasks, nowMillis);
        int resultSize = (int) Math.min(tasks.size(), Math.min(available, maxTasks));
        tasks = tasks.subList(0, resultSize);

        List<TaskQueuePb.TaskQueueAddRequest> result = new ArrayList<TaskQueuePb.TaskQueueAddRequest>();
        for (QueueStateInfo.TaskStateInfo task : tasks) {
            TaskQueuePb.TaskQueueAddRequest addRequest = task.getAddRequest();
            addRequest.setEtaUsec((long) (nowMillis * 1000.0D + leaseSeconds * 1000000.0D));
            result.add(addRequest);
        }

        return result;
    }

    synchronized TaskQueuePb.TaskQueueModifyTaskLeaseResponse modifyTaskLease(TaskQueuePb.TaskQueueModifyTaskLeaseRequest request) {
        TaskQueuePb.TaskQueueModifyTaskLeaseResponse response = new TaskQueuePb.TaskQueueModifyTaskLeaseResponse();

        TaskQueuePb.TaskQueueAddRequest task = (TaskQueuePb.TaskQueueAddRequest) this.taskMap
                .get(request.getTaskName());

        if (task == null) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.UNKNOWN_TASK.getValue());
        }

        if (task.getEtaUsec() != request.getEtaUsec()) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_LEASE_EXPIRED.getValue());
        }

        long timeNowUsec = System.currentTimeMillis() * 1000;
        if (task.getEtaUsec() < timeNowUsec) {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_LEASE_EXPIRED.getValue());
        }

        long requestLeaseUsec = (long) (request.getLeaseSeconds() * 1000000);
        long etaUsec = timeNowUsec + requestLeaseUsec;
        task.setEtaUsec(etaUsec);
        response.setUpdatedEtaUsec(etaUsec);
        return response;
    }
}