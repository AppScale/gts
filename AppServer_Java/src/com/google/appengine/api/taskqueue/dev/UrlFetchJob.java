package com.google.appengine.api.taskqueue.dev;


import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest.Header;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest.RequestMethod;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueRetryParameters;
// AppScale - imported URLFetchServicePb
import com.google.appengine.api.urlfetch.URLFetchServicePb;
import com.google.appengine.api.urlfetch.URLFetchServicePb.URLFetchRequest;
import com.google.appengine.api.urlfetch.URLFetchServicePb.URLFetchRequest.Builder;
// AppScale - removed imports colliding with URLFetchRequest
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalServerEnvironment;
//AppScale - imported QueueXml
import com.google.apphosting.utils.config.QueueXml;
import com.google.apphosting.utils.config.QueueXml.Entry;
import java.text.DecimalFormat;
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


public class UrlFetchJob implements Job
{
	private static final Logger				logger									= Logger.getLogger(UrlFetchJob.class.getName());
	static final String						X_GOOGLE_DEV_APPSERVER_SKIPADMINCHECK	= "X-Google-DevAppserver-SkipAdminCheck";
	static final String						X_APPENGINE_QUEUE_NAME					= "X-AppEngine-QueueName";
	static final String						X_APPENGINE_TASK_NAME					= "X-AppEngine-TaskName";
	static final String						X_APPENGINE_TASK_RETRY_COUNT			= "X-AppEngine-TaskRetryCount";
	static final String						X_APPENGINE_TASK_EXECUTION_COUNT		= "X-AppEngine-TaskExecutionCount";
	static final String						X_APPENGINE_TASK_ETA					= "X-AppEngine-TaskETA";
	static final String						X_APPENGINE_SERVER_NAME					= "X-AppEngine-ServerName";
	static final String						X_APPENGINE_TASK_PREVIOUS_RESPONSE		= "X-AppEngine-TaskPreviousResponse";
	private static LocalServerEnvironment	localServerEnvironment;
	private static Clock					clock;

	static URLFetchServicePb.URLFetchRequest.RequestMethod translateRequestMethod( TaskQueuePb.TaskQueueAddRequest.RequestMethod rm )
	{
		return URLFetchServicePb.URLFetchRequest.RequestMethod.valueOf(rm.name());
	}

	public void execute( JobExecutionContext context ) throws JobExecutionException
	{
		try
		{
			localServerEnvironment.waitForServerToStart();
		}
		catch (InterruptedException e)
		{
			throw new JobExecutionException("Interrupted while waiting for server to initialize.", e, false);
		}

		Trigger trigger = context.getTrigger();
		UrlFetchJobDetail jd = (UrlFetchJobDetail)context.getJobDetail();
		URLFetchServicePb.URLFetchRequest fetchReq = newFetchRequest(jd.getTaskName(), jd.getAddRequest(), jd.getServerUrl(), jd.getRetryCount(), jd.getQueueXmlEntry(), jd.getPreviousResponse());

		long firstTryMs = jd.getFirstTryMs();
		if (firstTryMs == 0L)
		{
			firstTryMs = clock.getCurrentTime();
		}
		int status = jd.getCallback().execute(fetchReq);

		if (((status < 200) || (status > 299)) && (canRetry(jd, firstTryMs)))
		{
			logger.info(String.format("Web hook at %s returned status code %d.  Rescheduling...", new Object[] { fetchReq.getUrl(), Integer.valueOf(status) }));

			reschedule(context.getScheduler(), trigger, jd, firstTryMs, status);
		}
		else
		{
			try
			{
				context.getScheduler().unscheduleJob(trigger.getName(), trigger.getGroup());
			}
			catch (SchedulerException e)
			{
				logger.log(Level.SEVERE, String.format("Unsubscription of task %s failed.", new Object[] { jd.getAddRequest() }), e);
			}
		}
	}

	private boolean canRetry( UrlFetchJobDetail jd, long firstTryMs )
	{
		TaskQueuePb.TaskQueueRetryParameters retryParams = jd.getRetryParameters();
		if (retryParams != null)
		{
			int newRetryCount = jd.getRetryCount() + 1;
			long ageMs = clock.getCurrentTime() - firstTryMs;

			if ((retryParams.hasRetryLimit()) && (retryParams.hasAgeLimitSec()))
			{
				return (retryParams.getRetryLimit() >= newRetryCount) || (retryParams.getAgeLimitSec() * 1000L >= ageMs);
			}

			if (retryParams.hasRetryLimit())
			{
				return retryParams.getRetryLimit() >= newRetryCount;
			}
			if (retryParams.hasAgeLimitSec())
			{
				return retryParams.getAgeLimitSec() * 1000L >= ageMs;
			}
		}
		return true;
	}

	private void reschedule( Scheduler scheduler, Trigger trigger, UrlFetchJobDetail jd, long firstTryMs, int previousResponse )
	{
		UrlFetchJobDetail newJobDetail = jd.retry(firstTryMs, previousResponse);

		SimpleTrigger newTrigger = new SimpleTrigger(trigger.getName(), trigger.getGroup());
		newTrigger.setStartTime(new Date(clock.getCurrentTime() + newJobDetail.getRetryDelayMs()));
		try
		{
			scheduler.unscheduleJob(trigger.getName(), trigger.getGroup());
			scheduler.scheduleJob(newJobDetail, newTrigger);
		}
		catch (SchedulerException e)
		{
			logger.log(Level.SEVERE, String.format("Reschedule of task %s failed.", new Object[] { jd.getAddRequest() }), e);
		}
	}

	URLFetchServicePb.URLFetchRequest newFetchRequest( String taskName, TaskQueuePb.TaskQueueAddRequest addReq, String serverUrl, int retryCount, QueueXml.Entry queueXmlEntry, int previousResponse )
	{
		URLFetchServicePb.URLFetchRequest.Builder requestProto = URLFetchServicePb.URLFetchRequest.newBuilder();
		requestProto.setUrl(serverUrl + addReq.getUrl());

		if (addReq.hasBody())
		{
			requestProto.setPayload(ByteString.copyFrom(addReq.getBodyAsBytes()));
		}
		requestProto.setMethod(translateRequestMethod(addReq.getMethodEnum()));

		addHeadersToFetchRequest(requestProto, taskName, addReq, retryCount, queueXmlEntry, previousResponse);

		if (requestProto.getMethod() == URLFetchServicePb.URLFetchRequest.RequestMethod.PUT)
		{
			requestProto.setFollowRedirects(false);
		}

		return requestProto.build();
	}

	private void addHeadersToFetchRequest( URLFetchServicePb.URLFetchRequest.Builder requestProto, String taskName, TaskQueuePb.TaskQueueAddRequest addReq, int retryCount, QueueXml.Entry queueXmlEntry, int previousResponse )
	{
		for (TaskQueuePb.TaskQueueAddRequest.Header header : addReq.headers())
		{
			requestProto.addHeader(buildHeader(header.getKey(), header.getValue()));
		}

		requestProto.addHeader(buildHeader("X-Google-DevAppserver-SkipAdminCheck", "true"));

		requestProto.addHeader(buildHeader("X-AppEngine-QueueName", addReq.getQueueName()));
		requestProto.addHeader(buildHeader("X-AppEngine-TaskName", taskName));
		requestProto.addHeader(buildHeader("X-AppEngine-TaskRetryCount", Integer.valueOf(retryCount).toString()));

		requestProto.addHeader(buildHeader("X-AppEngine-TaskETA", new DecimalFormat("0.000000").format(addReq.getEtaUsec() / 1000000.0D)));

		if (queueXmlEntry.getTarget() != null)
		{
			requestProto.addHeader(buildHeader("X-AppEngine-ServerName", queueXmlEntry.getTarget()));
		}
		requestProto.addHeader(buildHeader("X-AppEngine-TaskExecutionCount", Integer.valueOf(retryCount).toString()));

		if (previousResponse > 0) requestProto.addHeader(buildHeader("X-AppEngine-TaskPreviousResponse", Integer.valueOf(previousResponse).toString()));
	}

	private URLFetchServicePb.URLFetchRequest.Header.Builder buildHeader( String key, String value )
	{
		URLFetchServicePb.URLFetchRequest.Header.Builder headerProto = URLFetchServicePb.URLFetchRequest.Header.newBuilder();
		headerProto.setKey(key);
		headerProto.setValue(value);
		return headerProto;
	}

	/*
	 * AppScale - had to add underscores to arguments, otherwise it doesn't initialize correctly and
	 * throws a nullpointer on task execution.
	 */
	static void initialize( LocalServerEnvironment _localServerEnvironment, Clock _clock )
	{
		localServerEnvironment = _localServerEnvironment;
		clock = _clock;
	}
}