package com.google.appengine.api.labs.taskqueue.dev;

import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Collections;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.quartz.Scheduler;
import org.quartz.SchedulerException;
import org.quartz.impl.StdSchedulerFactory;

import com.google.appengine.api.taskqueue.InternalFailureException;
import com.google.appengine.api.taskqueue.QueueConstants;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.urlfetch.dev.LocalURLFetchService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.QueueXml;
import com.google.apphosting.utils.config.QueueXmlReader;

@ServiceProvider(LocalRpcService.class)
public final class LocalTaskQueue implements LocalRpcService {
	private static final Logger logger = Logger.getLogger(LocalTaskQueue.class
			.getName());
	public static final String PACKAGE = "taskqueue";
	public static final String DISABLE_AUTO_TASK_EXEC_PROP = "task_queue.disable_auto_task_execution";
	public static final String QUEUE_XML_PATH_PROP = "task_queue.queue_xml_path";
	private final Map<String, DevQueue> queues = Collections
			.synchronizedMap(new TreeMap<String, DevQueue>());
	private final AtomicInteger taskNameGenerator = new AtomicInteger(0);
	private QueueXml queueXml;
	private Scheduler scheduler;
	private boolean disableAutoTaskExecution = false;
	private LocalServerEnvironment localServerEnvironment;
	private Clock clock;

	public void init(LocalServiceContext context, Map<String, String> properties) {
		this.localServerEnvironment = context.getLocalServerEnvironment();
		this.clock = context.getClock();

		final String queueXmlPath = (String) properties
				.get("task_queue.queue_xml_path");
		QueueXmlReader reader;
		if (queueXmlPath != null) {
			reader = new QueueXmlReader(this.localServerEnvironment.getAppDir()
					.getPath()) {
				public String getFilename() {
					return queueXmlPath;
				}
			};
		} else
			reader = new QueueXmlReader(this.localServerEnvironment.getAppDir()
					.getPath());

		this.queueXml = reader.readQueueXml();

		logger.log(Level.INFO, "LocalTaskQueue is initialized");
		if (Boolean.valueOf(
				(String) properties
						.get("task_queue.disable_auto_task_execution"))
				.booleanValue()) {
			this.disableAutoTaskExecution = true;
			logger.log(Level.INFO, "Automatic task execution is disabled.");
		}
	}

	void setQueueXml(QueueXml queueXml) {
		this.queueXml = queueXml;
	}

	public void start() {
		AccessController.doPrivileged(new PrivilegedAction<Object>() {
			public Object run() {
				LocalTaskQueue.this.start_();
				return null;
			}
		});
	}

	private void start_() {
		Thread shutdownHook = new Thread() {
			public void run() {
				LocalTaskQueue.this.stop();
			}

		};
		Runtime.getRuntime().addShutdownHook(shutdownHook);

		LocalURLFetchService fetchService = new LocalURLFetchService();
		fetchService.init(null, new HashMap());

		fetchService.setTimeoutInMs(30000);

		fetchService.start();
		UrlFetchJob.initialize(fetchService, this.localServerEnvironment,
				this.clock);

		this.scheduler = startScheduler(this.disableAutoTaskExecution);
		String baseUrl = getBaseUrl(this.localServerEnvironment);

		if (this.queueXml != null) {
			for (QueueXml.Entry entry : this.queueXml.getEntries()) {
				this.queues.put(entry.getName(), new DevQueue(entry,
						this.taskNameGenerator, this.scheduler, baseUrl,
						this.clock));
			}

		}

		if (this.queues.get("default") == null) {
			QueueXml.Entry entry = QueueXml.defaultEntry();
			this.queues.put(entry.getName(),
					new DevQueue(entry, this.taskNameGenerator, this.scheduler,
							baseUrl, this.clock));
		}

		logger.info("Local task queue initialized with base url " + baseUrl);
	}

	static String getBaseUrl(LocalServerEnvironment localServerEnvironment) {
		return String.format("http://%s:%d", new Object[] {
				localServerEnvironment.getAddress(),
				Integer.valueOf(localServerEnvironment.getPort()) });
	}

	public void stop() {
		this.queues.clear();
		stopScheduler(this.scheduler);
		UrlFetchJob.getFetchService().stop();
	}

	public Integer getMaxApiRequestSize() {
		return Integer.valueOf(33554432);
	}

	public Double getDefaultDeadline(boolean isOfflineRequest) {
		return Double.valueOf(30.0D);
	}

	public Double getMaximumDeadline(boolean isOfflineRequest) {
		return Double.valueOf(30.0D);
	}

	public String getPackage() {
		return "taskqueue";
	}

	private long currentTimeMillis() {
		return this.clock.getCurrentTime();
	}

	private long currentTimeUsec() {
		return (currentTimeMillis() * 1000L);
	}

	TaskQueuePb.TaskQueueServiceError.ErrorCode validateAddRequest(
			TaskQueuePb.TaskQueueAddRequest addRequest) {
		String taskName = addRequest.getTaskName();
		if ((taskName != null)
				&& (taskName.length() != 0)
				&& (!(QueueConstants.TASK_NAME_PATTERN.matcher(taskName)
						.matches()))) {
			return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_TASK_NAME;
		}

		String queueName = addRequest.getQueueName();
		if ((queueName == null)
				|| (queueName.length() == 0)
				|| (!(QueueConstants.QUEUE_NAME_PATTERN.matcher(queueName)
						.matches()))) {
			return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_NAME;
		}

		String url = addRequest.getUrl();
		if ((!(addRequest.hasUrl())) || (url.length() == 0)
				|| (url.charAt(0) != '/')
				|| (url.length() > QueueConstants.maxUrlLength())) {
			return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_URL;
		}
		if (addRequest.getEtaUsec() < 0L) {
			return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_ETA;
		}

		if (addRequest.getEtaUsec() - currentTimeUsec() > getMaxEtaDeltaUsec()) {
			return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_ETA;
		}

		return TaskQueuePb.TaskQueueServiceError.ErrorCode.OK;
	}

	static long getMaxEtaDeltaUsec() {
		return (QueueConstants.getMaxEtaDeltaMillis() * 1000L);
	}

	public TaskQueuePb.TaskQueueAddResponse add(LocalRpcService.Status status,
			TaskQueuePb.TaskQueueAddRequest addRequest) {
		TaskQueuePb.TaskQueueBulkAddRequest bulkRequest = new TaskQueuePb.TaskQueueBulkAddRequest();
		TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();

		bulkRequest.addAddRequest().copyFrom(addRequest);
		TaskQueuePb.TaskQueueBulkAddResponse bulkResponse = bulkAdd(status,
				bulkRequest);

		if (bulkResponse.taskResultSize() != 1) {
			throw new InternalFailureException(String.format(
					"expected 1 result from BulkAdd(), got %d",
					new Object[] { Integer.valueOf(bulkResponse
							.taskResultSize()) }));
		}

		int result = bulkResponse.getTaskResult(0).getResult();

		if (result != TaskQueuePb.TaskQueueServiceError.ErrorCode.OK.getValue())
			throw new ApiProxy.ApplicationException(result);
		if (bulkResponse.getTaskResult(0).hasChosenTaskName()) {
			addResponse.setChosenTaskName(bulkResponse.getTaskResult(0)
					.getChosenTaskName());
		}

		return addResponse;
	}

	public TaskQueuePb.TaskQueueBulkAddResponse bulkAdd(
			LocalRpcService.Status status,
			TaskQueuePb.TaskQueueBulkAddRequest bulkAddRequest) {
		TaskQueuePb.TaskQueueBulkAddResponse bulkAddResponse = new TaskQueuePb.TaskQueueBulkAddResponse();

		if (bulkAddRequest.addRequestSize() == 0) {
			return bulkAddResponse;
		}

		bulkAddRequest = (TaskQueuePb.TaskQueueBulkAddRequest) bulkAddRequest
				.clone();
		DevQueue queue = getQueueByName(bulkAddRequest.getAddRequest(0)
				.getQueueName());

		Map<TaskQueuePb.TaskQueueBulkAddResponse.TaskResult, String> chosenNames = new IdentityHashMap<TaskQueuePb.TaskQueueBulkAddResponse.TaskResult, String>();

		boolean errorFound = false;

		for (TaskQueuePb.TaskQueueAddRequest addRequest : bulkAddRequest
				.addRequests()) {
			runAppScaleTask(addRequest);

//			TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult = bulkAddResponse
//					.addTaskResult();
//			TaskQueuePb.TaskQueueServiceError.ErrorCode error = validateAddRequest(addRequest);
//			if (error == TaskQueuePb.TaskQueueServiceError.ErrorCode.OK) {
//				if ((!(addRequest.hasTaskName()))
//						|| (addRequest.getTaskName().equals(""))) {
//					addRequest = addRequest.setTaskName(queue.genTaskName());
//					chosenNames.put(taskResult, addRequest.getTaskName());
//				}
//
//				taskResult
//						.setResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.SKIPPED
//								.getValue());
//			} else {
//				taskResult.setResult(error.getValue());
//				errorFound = true;
//			}
		}

//		if (errorFound) {
//			return bulkAddResponse;
//		}
//
//		if (bulkAddRequest.getAddRequest(0).hasTransaction()) {
//			try {
//				ApiProxy.makeSyncCall("datastore_v3", "addActions",
//						bulkAddRequest.toByteArray());
//			} catch (ApiProxy.ApplicationException exception) {
//				throw new ApiProxy.ApplicationException(
//						exception.getApplicationError()
//								+ TaskQueuePb.TaskQueueServiceError.ErrorCode.DATASTORE_ERROR
//										.getValue(), exception.getErrorDetail());
//			}
//
//		} else {
//			for (int i = 0; i < bulkAddRequest.addRequestSize(); ++i) {
//				TaskQueuePb.TaskQueueAddRequest addRequest = bulkAddRequest
//						.getAddRequest(i);
//				TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult = bulkAddResponse
//						.getTaskResult(i);
//				try {
//					queue.add(addRequest);
//				} catch (ApiProxy.ApplicationException exception) {
//					taskResult.setResult(exception.getApplicationError());
//				}
//			}
//		}
//
//		for (TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult : bulkAddResponse
//				.taskResults()) {
//			if (taskResult.getResult() == TaskQueuePb.TaskQueueServiceError.ErrorCode.SKIPPED
//					.getValue()) {
//				taskResult
//						.setResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.OK
//								.getValue());
//				if (chosenNames.containsKey(taskResult)) {
//					taskResult.setChosenTaskName((String) chosenNames
//							.get(taskResult));
//				}
//			}
//		}

		return bulkAddResponse;
	}

	private void runAppScaleTask(final TaskQueueAddRequest addRequest) {
		AccessController.doPrivileged(new PrivilegedAction<Object>() {
			public Object run() {
				System.out.println("running appscale task!");
				new AppScaleRunTask(addRequest).run();
				return null;
			}
		});
	}

	public Map<String, QueueStateInfo> getQueueStateInfo() {
		TreeMap<String, QueueStateInfo> queueStateInfo = new TreeMap<String, QueueStateInfo>();

		for (Map.Entry<String, DevQueue> entry : this.queues.entrySet()) {
			String queueName = (String) entry.getKey();
			queueStateInfo.put(queueName, ((DevQueue) entry.getValue())
					.getStateInfo());
		}

		return queueStateInfo;
	}

	private DevQueue getQueueByName(String queueName) {
		DevQueue queue = (DevQueue) this.queues.get(queueName);
		if (queue == null) {
			throw new ApiProxy.ApplicationException(
					TaskQueuePb.TaskQueueServiceError.ErrorCode.UNKNOWN_QUEUE
							.getValue(), queueName);
		}
		return queue;
	}

	public void flushQueue(String queueName) {
		DevQueue queue = getQueueByName(queueName);
		queue.flush();
	}

	public boolean deleteTask(String queueName, String taskName) {
		DevQueue queue = getQueueByName(queueName);
		return queue.deleteTask(taskName);
	}

	static Scheduler startScheduler(boolean disableAutoTaskExecution) {
		try {
			Scheduler scheduler = StdSchedulerFactory.getDefaultScheduler();

			if (!(disableAutoTaskExecution)) {
				System.out.println("scheduler not start, since this is the local version, " +
						" all jobs start immediately!");
			//	scheduler.start();
			}
			return scheduler;
		} catch (SchedulerException e) {
			throw new RuntimeException(e);
		}
	}

	static void stopScheduler(Scheduler scheduler) {
		try {
			scheduler.shutdown(false);
		} catch (SchedulerException e) {
			throw new RuntimeException(e);
		}
	}

	public boolean runTask(String queueName, String taskName) {
		DevQueue queue = getQueueByName(queueName);
		return queue.runTask(taskName);
	}
}
