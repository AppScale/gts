package com.google.appengine.api.labs.taskqueue.dev;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.quartz.Job;
import org.quartz.JobDetail;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.quartz.Scheduler;
import org.quartz.SchedulerException;
import org.quartz.SimpleTrigger;
import org.quartz.Trigger;
import org.quartz.spi.TriggerFiredBundle;

import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.QueueXml;

class DevQueue {
	private static final Logger logger = Logger.getLogger(DevQueue.class
			.getName());
	static final int DEFAULT_BUCKET_SIZE = 5;
	private final QueueXml.Entry queueXmlEntry;
	private final AtomicInteger taskNameGenerator;
	private final Scheduler scheduler;
	private final String baseUrl;
	private final Clock clock;

	DevQueue(QueueXml.Entry queueXmlEntry, AtomicInteger taskNameGenerator,
			Scheduler scheduler, String baseUrl, Clock clock) {
		this.taskNameGenerator = taskNameGenerator;
		this.queueXmlEntry = queueXmlEntry;
		this.scheduler = scheduler;
		this.baseUrl = baseUrl;
		this.clock = clock;
		if ((queueXmlEntry.getRate() == null)
				|| (queueXmlEntry.getRate().intValue() != 0)) {
			return;
		}

		try {
			scheduler.pauseTriggerGroup(getQueueName());
		} catch (SchedulerException e) {
			throw new ApiProxy.ApplicationException(
					TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR
							.getValue(), e.getMessage());
		}
	}

	private synchronized String scheduleTask(
			TaskQueuePb.TaskQueueAddRequest addRequest) {
		String taskName;
		if ((addRequest.hasTaskName())
				&& (!(addRequest.getTaskName().equals("")))) {
			taskName = addRequest.getTaskName();
		} else
			taskName = genTaskName();
		try {
			if (this.scheduler.getJobDetail(taskName, getQueueName()) != null)
				throw new ApiProxy.ApplicationException(
						TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_ALREADY_EXISTS
								.getValue());
		} catch (SchedulerException e) {
			throw new ApiProxy.ApplicationException(
					TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR
							.getValue(), e.getMessage());
		}

		long etaMillis = addRequest.getEtaUsec() / 1000L;
		SimpleTrigger trigger = new SimpleTrigger(taskName, getQueueName());
		trigger.setStartTime(new Date(etaMillis));
		JobDetail jd = newUrlFetchJobDetail(taskName, getQueueName(),
				addRequest);
		try {
			this.scheduler.scheduleJob(jd, trigger);
		} catch (SchedulerException e) {
			throw new ApiProxy.ApplicationException(
					TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR
							.getValue(), e.getMessage());
		}

		return taskName;
	}

	JobDetail newUrlFetchJobDetail(String taskName, String queueName,
			TaskQueuePb.TaskQueueAddRequest addRequest) {
		return new UrlFetchJobDetail(taskName, queueName, addRequest,
				this.baseUrl);
	}

	String genTaskName() {
		Integer newId = Integer.valueOf(this.taskNameGenerator
				.incrementAndGet());
		return "task" + newId.toString();
	}

	TaskQueuePb.TaskQueueAddResponse add(
			TaskQueuePb.TaskQueueAddRequest addRequest) {
		String taskName = scheduleTask(addRequest);

		TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();
		if ((addRequest.hasTaskName())
				&& (!(addRequest.getTaskName().equals("")))) {
			return addResponse;
		}
		addResponse.setChosenTaskName(taskName);
		return addResponse;
	}

	private String getQueueName() {
		return this.queueXmlEntry.getName();
	}

	private List<String> getSortedJobNames() throws SchedulerException {
		String[] jobNames = this.scheduler.getJobNames(getQueueName());
		List<String> jobNameList = Arrays.asList(jobNames);
		Collections.sort(jobNameList);
		return jobNameList;
	}

	QueueStateInfo getStateInfo() {
		ArrayList<QueueStateInfo.TaskStateInfo> taskInfoList = new ArrayList<QueueStateInfo.TaskStateInfo>();
		try {
			for (String jobName : getSortedJobNames()) {
				UrlFetchJobDetail jd = (UrlFetchJobDetail) this.scheduler
						.getJobDetail(jobName, getQueueName());
				if (jd == null) {
					continue;
				}

				Trigger[] triggers = this.scheduler.getTriggersOfJob(jobName,
						getQueueName());
				if (triggers.length != 1) {
					throw new RuntimeException("Multiple triggers for task "
							+ jobName + " in queue " + getQueueName());
				}

				long execTime = triggers[0].getStartTime().getTime();
				taskInfoList.add(new QueueStateInfo.TaskStateInfo(jd.getName(),
						execTime, jd.getAddRequest(), this.clock));
			}
		} catch (SchedulerException e) {
			throw new RuntimeException(e);
		}

		Collections.sort(taskInfoList,
				new Comparator<QueueStateInfo.TaskStateInfo>() {
					public int compare(QueueStateInfo.TaskStateInfo t1,
							QueueStateInfo.TaskStateInfo t2) {
						return Long.valueOf(t1.getEtaMillis()).compareTo(
								Long.valueOf(t2.getEtaMillis()));
					}
				});
		return new QueueStateInfo(this.queueXmlEntry, taskInfoList);
	}

	boolean deleteTask(String taskName) {
		try {
			return this.scheduler.deleteJob(taskName, getQueueName());
		} catch (SchedulerException e) {
			throw new RuntimeException(e);
		}
	}

	void flush() {
		try {
			for (String name : this.scheduler.getJobNames(getQueueName()))
				this.scheduler.deleteJob(name, getQueueName());
		} catch (SchedulerException e) {
			throw new RuntimeException(e);
		}
	}

	private JobExecutionContext getExecutionContext(JobDetail jobDetail) {
		Trigger trigger = new SimpleTrigger();
		trigger.setJobDataMap(jobDetail.getJobDataMap());
		TriggerFiredBundle bundle = new TriggerFiredBundle(jobDetail, trigger,
				null, false, null, null, null, null);

		return new JobExecutionContext(this.scheduler, bundle, null);
	}

	boolean runTask(String taskName) {
		JobExecutionContext context;
		Job job;
		try {
			UrlFetchJobDetail jd = (UrlFetchJobDetail) this.scheduler
					.getJobDetail(taskName, getQueueName());
			if (jd == null) {
				return false;
			}
			context = getExecutionContext(jd);
			job = (Job) jd.getJobClass().newInstance();
		} catch (SchedulerException e) {
			return false;
		} catch (IllegalAccessException e) {
			return false;
		} catch (InstantiationException e) {
			return false;
		}
		try {
			job.execute(context);
		} catch (JobExecutionException e) {
			logger.log(Level.SEVERE, "Exception executing task " + taskName
					+ " on queue " + getQueueName(), e);
		} catch (RuntimeException rte) {
			logger.log(Level.SEVERE, "Exception executing task " + taskName
					+ " on queue " + getQueueName(), rte);
		}

		deleteTask(taskName);
		return true;
	}
}
