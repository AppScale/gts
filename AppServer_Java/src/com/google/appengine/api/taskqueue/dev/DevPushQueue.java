package com.google.appengine.api.taskqueue.dev;


import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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

import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueRetryParameters;
import com.google.appengine.api.taskqueue.dev.QueueStateInfo.TaskStateInfo;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.QueueXml;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;


class DevPushQueue extends DevQueue
{
	static final int						DEFAULT_BUCKET_SIZE	= 5;
	private final Scheduler					scheduler;
	private final String					baseUrl;
	private final Clock						clock;
	private final LocalTaskQueueCallback	callback;
	/*
	 * AppScale - added RabbitMQclient and name
	 */
	private String							rabbitMQQueueName;
	private RabbitMQclient					client;

	TaskQueuePb.TaskQueueMode.Mode getMode()
	{
		return TaskQueuePb.TaskQueueMode.Mode.PUSH;
	}

	DevPushQueue( QueueXml.Entry queueXmlEntry, Scheduler scheduler, String baseUrl, Clock clock, LocalTaskQueueCallback callback, RabbitMQclient client )
	{
		/*
		 * AppScale - added RabbitMQclient to constructor args and setting queue
		 * name and client
		 */
		super(queueXmlEntry);
		this.client = client;
		this.scheduler = scheduler;
		this.baseUrl = baseUrl;
		this.clock = clock;
		this.callback = callback;
		this.rabbitMQQueueName = "app_" + System.getProperty("APPLICATION_ID");

		if (queueXmlEntry.getRate() != null)
		{
			if (queueXmlEntry.getRate().intValue() == 0)
			{
				try
				{
					scheduler.pauseTriggerGroup(getQueueName());
				}
				catch (SchedulerException e)
				{
					throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue(), e.getMessage());
				}
			}
		}
		else
			throw new RuntimeException("Rate must be specified for push queue.");
	}

	private synchronized String scheduleTask( TaskQueuePb.TaskQueueAddRequest addRequest )
	{
		String taskName;
		if ((addRequest.hasTaskName()) && (!addRequest.getTaskName().equals("")))
		{
			taskName = addRequest.getTaskName();
		}
		else
			taskName = genTaskName();
		try
		{
			if (this.scheduler.getJobDetail(taskName, getQueueName()) != null) throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.TASK_ALREADY_EXISTS.getValue());
		}
		catch (SchedulerException e)
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue(), e.getMessage());
		}

		TaskQueuePb.TaskQueueRetryParameters retryParams = getRetryParameters(addRequest);
		long etaMillis = addRequest.getEtaUsec() / 1000L;
		SimpleTrigger trigger = new SimpleTrigger(taskName, getQueueName());
		trigger.setStartTime(new Date(etaMillis));
		JobDetail jd = newUrlFetchJobDetail(taskName, getQueueName(), addRequest, retryParams);
		try
		{
			logger.fine("PushQueue: scheduling a task: [" + taskName + "] queueName: [" + getQueueName() + "]");
			this.scheduler.scheduleJob(jd, trigger);
		}
		catch (SchedulerException e)
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue(), e.getMessage());
		}

		return taskName;
	}

	JobDetail newUrlFetchJobDetail( String taskName, String queueName, TaskQueuePb.TaskQueueAddRequest addRequest, TaskQueuePb.TaskQueueRetryParameters retryParams )
	{
		return new UrlFetchJobDetail(taskName, queueName, addRequest, this.baseUrl, this.callback, this.queueXmlEntry, retryParams);
	}

	TaskQueuePb.TaskQueueAddResponse add( TaskQueuePb.TaskQueueAddRequest addRequest )
	{
		logger.fine("PushQueue: adding a task in DevPushQueue");
		if (addRequest.getMode() != TaskQueuePb.TaskQueueMode.Mode.PUSH.getValue())
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_MODE.getValue());
		}
		if (!addRequest.getQueueName().equals(getQueueName()))
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_REQUEST.getValue());
		}
		/*
		 * AppScale - sending task to RabbitMQ instead of calling scheduleTask
		 * method
		 */
		logger.fine("PushQueue: sending addTaskRequest to rabbiMQ");
		String taskName = sendTaskToRabbitMQ(addRequest);

		TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();
		if ((!addRequest.hasTaskName()) || (addRequest.getTaskName().equals("")))
		{
			addRequest.setTaskName(taskName);
			addResponse.setChosenTaskName(taskName);
		}

		return addResponse;
	}

	private String sendTaskToRabbitMQ( TaskQueueAddRequest addRequest )
	{
		/*
		 * AppScale - added this method
		 */
		logger.fine("TaskQueueAddRequest being sent to RabbitMQ: [" + addRequest + "]");
		String taskName = getTaskName(addRequest);
		TaskParams taskParams = new TaskParams();
		taskParams.setFirstTryMs(0l);
		taskParams.setRetryCount(0);
		taskParams.setRetryDelayMs(0);
		taskParams.setServerUrl(this.baseUrl);
		taskParams.setTarget(this.queueXmlEntry.getTarget());
		taskParams.setTaskQueueAddRequestBuf(addRequest.toByteArray());
		TaskQueueRetryParameters retryParams = getRetryParameters(addRequest);
		if (retryParams != null)
		{
			taskParams.setTaskQueueRetryParametersBuf(retryParams.toByteArray());
		}

		Gson gson = new Gson();
		Type taskParamType = new TypeToken<TaskParams>()
		{}.getType();
		String payload = gson.toJson(taskParams, taskParamType);
		client.enqueueTask(this.rabbitMQQueueName, payload);
		return taskName;
	}

	private String getTaskName( TaskQueueAddRequest addRequest )
	{
		String taskName;
		if ((addRequest.hasTaskName()) && (!addRequest.getTaskName().equals("")))
		{
			taskName = addRequest.getTaskName();
		}
		else
			taskName = genTaskName();
		return taskName;
	}

	List<String> getSortedJobNames() throws SchedulerException
	{
		String[] jobNames = this.scheduler.getJobNames(getQueueName());
		List<String> jobNameList = Arrays.asList(jobNames);
		Collections.sort(jobNameList);
		return jobNameList;
	}

	QueueStateInfo getStateInfo()
	{
		ArrayList<TaskStateInfo> taskInfoList = new ArrayList<TaskStateInfo>();
		try
		{
			for (String jobName : getSortedJobNames())
			{
				UrlFetchJobDetail jd = (UrlFetchJobDetail)this.scheduler.getJobDetail(jobName, getQueueName());
				if (jd == null)
				{
					continue;
				}
				Trigger[] triggers = this.scheduler.getTriggersOfJob(jobName, getQueueName());
				if (triggers.length != 1)
				{
					throw new RuntimeException("Multiple triggers for task " + jobName + " in queue " + getQueueName());
				}

				long execTime = triggers[0].getStartTime().getTime();
				taskInfoList.add(new QueueStateInfo.TaskStateInfo(jd.getName(), execTime, jd.getAddRequest(), this.clock));
			}
		}
		catch (SchedulerException e)
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue());
		}

		Collections.sort(taskInfoList, new Comparator<QueueStateInfo.TaskStateInfo>()
		{
			public int compare( QueueStateInfo.TaskStateInfo t1, QueueStateInfo.TaskStateInfo t2 )
			{
				return Long.valueOf(t1.getEtaMillis()).compareTo(Long.valueOf(t2.getEtaMillis()));
			}
		});
		return new QueueStateInfo(this.queueXmlEntry, taskInfoList);
	}

	boolean deleteTask( String taskName )
	{
		try
		{
			return this.scheduler.deleteJob(taskName, getQueueName());
		}
		catch (SchedulerException e)
		{
		}
		throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue());
	}

	void flush()
	{
		try
		{
			for (String name : this.scheduler.getJobNames(getQueueName()))
				this.scheduler.deleteJob(name, getQueueName());
		}
		catch (SchedulerException e)
		{
			throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INTERNAL_ERROR.getValue());
		}
	}

	private JobExecutionContext getExecutionContext( UrlFetchJobDetail jobDetail )
	{
		Trigger trigger = new SimpleTrigger(jobDetail.getTaskName(), jobDetail.getQueueName());
		trigger.setJobDataMap(jobDetail.getJobDataMap());
		TriggerFiredBundle bundle = new TriggerFiredBundle(jobDetail, trigger, null, false, null, null, null, null);

		return new JobExecutionContext(this.scheduler, bundle, null);
	}

	boolean runTask( String taskName )
	{
		JobExecutionContext context;
		Job job;
		try
		{
			UrlFetchJobDetail jd = (UrlFetchJobDetail)this.scheduler.getJobDetail(taskName, getQueueName());
			if (jd == null)
			{
				return false;
			}
			context = getExecutionContext(jd);
			job = (Job)jd.getJobClass().newInstance();
		}
		catch (SchedulerException e)
		{
			return false;
		}
		catch (IllegalAccessException e)
		{
			return false;
		}
		catch (InstantiationException e)
		{
			return false;
		}
		try
		{
			logger.fine("PushQueue: running a task");
			job.execute(context);
		}
		catch (JobExecutionException e)
		{
			logger.log(Level.SEVERE, "Exception executing task " + taskName + " on queue " + getQueueName(), e);
		}
		catch (RuntimeException rte)
		{
			logger.log(Level.SEVERE, "Exception executing task " + taskName + " on queue " + getQueueName(), rte);
		}

		return true;
	}
}