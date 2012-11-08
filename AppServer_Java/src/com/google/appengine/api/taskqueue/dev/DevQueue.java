package com.google.appengine.api.taskqueue.dev;


import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueMode.Mode;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueRetryParameters;
import com.google.apphosting.utils.config.QueueXml;
import com.google.apphosting.utils.config.QueueXml.Entry;
import com.google.apphosting.utils.config.QueueXml.RetryParameters;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Logger;


abstract class DevQueue
{
	protected static final Logger	logger				= Logger.getLogger(DevQueue.class.getName());
	protected final QueueXml.Entry	queueXmlEntry;
	static AtomicInteger			taskNameGenerator	= null;

	DevQueue( QueueXml.Entry queueXmlEntry )
	{
		this.queueXmlEntry = queueXmlEntry;
	}

	DevQueue( QueueXml.Entry queueXmlEntry, AtomicInteger taskNameGeneratorIn )
	{
		this.queueXmlEntry = queueXmlEntry;
		/*
		 * AppScale - setting taskNameGenerator
		 */
		taskNameGenerator = taskNameGeneratorIn;
	}

	static String genTaskName()
	{
		if (taskNameGenerator != null)
		{
			return "task" + taskNameGenerator.incrementAndGet();
		}
		return "task-" + UUID.randomUUID().toString();
	}

	abstract TaskQueuePb.TaskQueueAddResponse add( TaskQueuePb.TaskQueueAddRequest paramTaskQueueAddRequest );

	protected String getQueueName()
	{
		return this.queueXmlEntry.getName();
	}

	protected TaskQueuePb.TaskQueueRetryParameters getRetryParameters( TaskQueuePb.TaskQueueAddRequest addRequest )
	{
		if (addRequest.hasRetryParameters())
		{
			return addRequest.getRetryParameters();
		}
		QueueXml.RetryParameters retryParams = this.queueXmlEntry.getRetryParameters();
		if (retryParams == null)
		{
			return null;
		}

		TaskQueuePb.TaskQueueRetryParameters paramsPb = new TaskQueuePb.TaskQueueRetryParameters();
		if (retryParams.getRetryLimit() != null)
		{
			paramsPb.setRetryLimit(retryParams.getRetryLimit().intValue());
		}
		if (retryParams.getAgeLimitSec() != null)
		{
			paramsPb.setAgeLimitSec(retryParams.getAgeLimitSec().intValue());
		}
		if (retryParams.getMinBackoffSec() != null)
		{
			paramsPb.setMinBackoffSec(retryParams.getMinBackoffSec().doubleValue());
		}
		if (retryParams.getMaxBackoffSec() != null)
		{
			paramsPb.setMaxBackoffSec(retryParams.getMaxBackoffSec().doubleValue());
		}
		if (retryParams.getMaxDoublings() != null)
		{
			paramsPb.setMaxDoublings(retryParams.getMaxDoublings().intValue());
		}
		return paramsPb;
	}

	abstract QueueStateInfo getStateInfo();

	abstract boolean deleteTask( String paramString );

	abstract void flush();

	abstract TaskQueuePb.TaskQueueMode.Mode getMode();

	abstract boolean runTask( String paramString );
}
