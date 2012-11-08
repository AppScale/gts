package com.google.appengine.api.taskqueue.dev;


import java.io.IOException;
import java.lang.reflect.Type;
import java.text.DecimalFormat;
import java.util.Map;

import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueRetryParameters;
import com.google.appengine.api.urlfetch.URLFetchServicePb;
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import com.rabbitmq.client.AMQP;
import com.rabbitmq.client.AMQP.BasicProperties;
import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.DefaultConsumer;
import com.rabbitmq.client.Envelope;


public class RabbitMQclient
{

	private LocalTaskQueueCallback	taskQueueCallback;
	private Channel					publishChannel;
	private String					queueName;
	private String					exchangeName		= "rabbitMQExchange";
	private boolean					autoAck				= false;
	private Gson					deserializer		= new Gson();
	private Connection				conn;
	private final String			RETRY_COUNT_PARAM	= "retryCount";
	private final String			RETRY_DELAY_PARAM	= "retryDelayMs";

	public RabbitMQclient( String _queueName, LocalTaskQueueCallback taskQueueCallback )
	{
		this.queueName = _queueName;
		this.taskQueueCallback = taskQueueCallback;

		ConnectionFactory factory = new ConnectionFactory();
		factory.setHost("localhost");

		try
		{
			conn = factory.newConnection();
			publishChannel = conn.createChannel();
			publishChannel.exchangeDeclare(this.exchangeName, "direct", true);
			publishChannel.queueDeclare(this.queueName, true, false, true, null);
			publishChannel.queueBind(this.queueName, this.exchangeName, this.queueName);

			System.out.println("connection has been established.");
			publishChannel.basicConsume(this.queueName, this.autoAck, new DefaultConsumer(publishChannel)
			{

				@Override
				public void handleDelivery( String consumerTag, Envelope envelope, BasicProperties properties, byte[] body ) throws IOException
				{
					String payload = new String(body);
					Type taskParamType = new TypeToken<TaskParams>()
					{}.getType();
					TaskParams paramMap = deserializer.fromJson(payload, taskParamType);
					executeTask(paramMap);
					long deliveryTag = envelope.getDeliveryTag();
					publishChannel.basicAck(deliveryTag, false);
				}
			});
		}
		catch (IOException e)
		{
			e.printStackTrace();
		}

	}

	public Channel getPublishChannel()
	{
		return this.publishChannel;
	}

	public void enqueueTask( String queueName, String payload )
	{
		try
		{
			this.publishChannel.basicPublish(this.exchangeName, queueName, new AMQP.BasicProperties.Builder().deliveryMode(2).build(), payload.getBytes());
		}
		catch (IOException e)
		{
			e.printStackTrace();
		}
	}

	private void executeTask( TaskParams taskParams )
	{
		int backOffMss = taskParams.getRetryDelayMs();
		backOff(backOffMss);
		TaskQueueAddRequest req = new TaskQueueAddRequest();
		req.mergeFrom(taskParams.getTaskQueueAddRequestBuf());

		String serverUrl = taskParams.getServerUrl();
		int retryCount = taskParams.getRetryCount();
		String target = taskParams.getTarget();
		long firstTryMs = taskParams.getFirstTryMs();
		TaskQueueRetryParameters retryParam = new TaskQueueRetryParameters();
		if (retryParam != null && taskParams.getTaskQueueRetryParametersBuf() != null)
		{
			retryParam.mergeFrom(taskParams.getTaskQueueRetryParametersBuf());
		}
		String taskName = req.getTaskName();

		URLFetchServicePb.URLFetchRequest fetchReq = newFetchRequest(taskName, req, serverUrl, retryCount, target);
		if (firstTryMs == 0L)
		{
			firstTryMs = System.currentTimeMillis();
		}
		int status = this.taskQueueCallback.execute(fetchReq);
		if (((status < 200) || (status > 299)) && (canRetry(retryParam, firstTryMs, retryCount)))
		{
			// TODO - add retry logic
		}
		else
		{

		}
	}

	private void backOff( int backOffMss )
	{
		if (backOffMss != 0)
		{
			try
			{
				Thread.sleep(backOffMss);
			}
			catch (InterruptedException e)
			{
				System.out.println("Task Backoff Failed");
				e.printStackTrace();
			}
		}
	}

	private void reschedule( Map<String, Object> paramMap, int retryCount, TaskQueueRetryParameters params )
	{
		paramMap.put(RETRY_COUNT_PARAM, Integer.toString(retryCount + 1));
		int exponent = Math.min(retryCount - 1, params.getMaxDoublings());
		int linearSteps = retryCount - exponent;
		int minBackoffMs = (int)(params.getMinBackoffSec() * 1000.0D);
		int maxBackoffMs = (int)(params.getMaxBackoffSec() * 1000.0D);
		int backoffMs = minBackoffMs;
		if (exponent > 0)
		{
			backoffMs = (int)(backoffMs * Math.pow(2.0D, Math.min(1023, exponent)));
		}
		if (linearSteps > 1)
		{
			backoffMs *= linearSteps;
		}
		backoffMs = Math.min(maxBackoffMs, backoffMs);
		paramMap.put(RETRY_DELAY_PARAM, Integer.toString(backoffMs));

	}

	URLFetchServicePb.URLFetchRequest newFetchRequest( String taskName, TaskQueuePb.TaskQueueAddRequest addReq, String serverUrl, int retryCount, String target )
	{
		URLFetchServicePb.URLFetchRequest.Builder requestProto = URLFetchServicePb.URLFetchRequest.newBuilder();
		requestProto.setUrl(serverUrl + addReq.getUrl());

		if (addReq.hasBody())
		{
			requestProto.setPayload(ByteString.copyFrom(addReq.getBodyAsBytes()));
		}
		requestProto.setMethod(translateRequestMethod(addReq.getMethodEnum().name()));

		addHeadersToFetchRequest(requestProto, taskName, addReq, retryCount, target);

		if (requestProto.getMethod() == URLFetchServicePb.URLFetchRequest.RequestMethod.PUT)
		{
			requestProto.setFollowRedirects(false);
		}

		return requestProto.build();
	}

	static URLFetchServicePb.URLFetchRequest.RequestMethod translateRequestMethod( String methodName )
	{
		return URLFetchServicePb.URLFetchRequest.RequestMethod.valueOf(methodName);
	}

	private void addHeadersToFetchRequest( URLFetchServicePb.URLFetchRequest.Builder requestProto, String taskName, TaskQueuePb.TaskQueueAddRequest addReq, int retryCount, String target )
	{
		for (TaskQueuePb.TaskQueueAddRequest.Header header : addReq.headers())
		{
			requestProto.addHeader(buildHeader(header.getKey(), header.getValue()));
		}

		// TODO
		requestProto.addHeader(buildHeader("X-Google-DevAppserver-SkipAdminCheck", "true"));

		requestProto.addHeader(buildHeader("X-AppEngine-QueueName", addReq.getQueueName()));
		requestProto.addHeader(buildHeader("X-AppEngine-TaskName", taskName));
		requestProto.addHeader(buildHeader("X-AppEngine-TaskRetryCount", Integer.valueOf(retryCount).toString()));

		requestProto.addHeader(buildHeader("X-AppEngine-TaskETA", new DecimalFormat("0.000000").format(addReq.getEtaUsec() / 1000000.0D)));

		if (target != null) requestProto.addHeader(buildHeader("X-AppEngine-ServerName", target));
	}

	private URLFetchServicePb.URLFetchRequest.Header.Builder buildHeader( String key, String value )
	{
		URLFetchServicePb.URLFetchRequest.Header.Builder headerProto = URLFetchServicePb.URLFetchRequest.Header.newBuilder();
		headerProto.setKey(key);
		headerProto.setValue(value);
		return headerProto;
	}

	private boolean canRetry( TaskQueueRetryParameters retryParams, long firstTryMs, int retryCount )
	{
		if (retryParams != null)
		{
			int newRetryCount = retryCount + 1;
			long ageMs = System.currentTimeMillis() - firstTryMs;

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

			return false;
		}
		else
		{
			// don't retry if retry params aren't specified in queue xml
			return false;
		}

	}

	public void shutdown()
	{
		try
		{
			this.publishChannel.close();
			this.conn.close();
		}
		catch (IOException e)
		{
			e.printStackTrace();
		}
	}
}
