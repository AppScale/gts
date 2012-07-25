package com.google.appengine.api.taskqueue.dev;

import java.io.Serializable;

public class TaskParams implements Serializable {
    private Integer retryDelayMs;
    private String serverUrl;
    private Integer retryCount;
    private String target;
    private Long firstTryMs;
    private byte[] taskQueueAddRequestBuf;
    private byte[] taskQueueRetryParametersBuf;

    public Integer getRetryDelayMs() {
        return retryDelayMs;
    }

    public void setRetryDelayMs(Integer retryDelayMs) {
        this.retryDelayMs = retryDelayMs;
    }

    public String getServerUrl() {
        return serverUrl;
    }

    public void setServerUrl(String serverUrl) {
        this.serverUrl = serverUrl;
    }

    public Integer getRetryCount() {
        return retryCount;
    }

    public void setRetryCount(Integer retryCount) {
        this.retryCount = retryCount;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public Long getFirstTryMs() {
        return firstTryMs;
    }

    public void setFirstTryMs(Long firstTryMs) {
        this.firstTryMs = firstTryMs;
    }

    public byte[] getTaskQueueAddRequestBuf() {
        return taskQueueAddRequestBuf;
    }

    public void setTaskQueueAddRequestBuf(byte[] taskQueueAddRequestBuf) {
        this.taskQueueAddRequestBuf = taskQueueAddRequestBuf;
    }

    public byte[] getTaskQueueRetryParametersBuf() {
        return taskQueueRetryParametersBuf;
    }

    public void setTaskQueueRetryParametersBuf(byte[] taskQueueRetryParametersBuf) {
        this.taskQueueRetryParametersBuf = taskQueueRetryParametersBuf;
    }

}
