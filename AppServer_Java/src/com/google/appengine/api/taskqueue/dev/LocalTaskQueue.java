package com.google.appengine.api.taskqueue.dev;


import com.google.appengine.api.taskqueue.InternalFailureException;
import com.google.appengine.api.taskqueue.QueueConstants;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddResponse.TaskResult;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueDeleteRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueDeleteResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueFetchQueueStatsRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueFetchQueueStatsResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueFetchQueueStatsResponse.QueueStats;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueMode.Mode;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueModifyTaskLeaseRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueModifyTaskLeaseResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueuePurgeQueueRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueuePurgeQueueResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueQueryAndOwnTasksRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueQueryAndOwnTasksResponse;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueQueryAndOwnTasksResponse.Task;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueScannerQueueInfo;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueServiceError.ErrorCode;
// AppScale - added import URLFetchServicePb
import com.google.appengine.api.urlfetch.URLFetchServicePb;
import com.google.appengine.api.urlfetch.URLFetchServicePb.URLFetchRequest;
import com.google.appengine.api.urlfetch.URLFetchServicePb.URLFetchResponse;
import com.google.appengine.api.urlfetch.dev.LocalURLFetchService;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.utils.config.QueueXml;
import com.google.apphosting.utils.config.QueueXml.Entry;
import com.google.apphosting.utils.config.QueueXmlReader;
import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Collections;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
// AppScale - removed Map.Entry import
import java.util.Random;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.quartz.Scheduler;
import org.quartz.SchedulerException;
import org.quartz.impl.StdSchedulerFactory;


@ServiceProvider(LocalRpcService.class)
public final class LocalTaskQueue extends AbstractLocalRpcService
{
    private static final Logger         logger                      = Logger.getLogger(LocalTaskQueue.class.getName());
    public static final String          PACKAGE                     = "taskqueue";
    public static final String          DISABLE_AUTO_TASK_EXEC_PROP = "task_queue.disable_auto_task_execution";
    public static final String          QUEUE_XML_PATH_PROP         = "task_queue.queue_xml_path";
    public static final String          CALLBACK_CLASS_PROP         = "task_queue.callback_class";
    private final Map<String, DevQueue> queues;
    private QueueXml                    queueXml;
    private boolean                     disableAutoTaskExecution;
    private LocalServerEnvironment      localServerEnvironment;
    private Clock                       clock;
    private LocalURLFetchService        fetchService;
    private LocalTaskQueueCallback      callback;
    private Thread                      shutdownHook;
    private Random                      rng;
    private final int                   tenMinutesInMillis          = 600000;
    private final static String         localHostIp                 = "127.0.0.1";
    private final static long           ONE_SECOND_IN_MILLIS        = 1000;
    /*
     * AppScale - added taskNameGenerator field
     */
    private final AtomicInteger         taskNameGenerator;

    public LocalTaskQueue()
    {
        this.queues = Collections.synchronizedMap(new TreeMap());
        /*
         * AppScale - added taskNameGenerator instantiation
         */
        this.taskNameGenerator = new AtomicInteger(0);
        this.disableAutoTaskExecution = false;
    }

    public void init( LocalServiceContext context, Map<String, String> properties )
    {
        this.localServerEnvironment = context.getLocalServerEnvironment();
        this.clock = context.getClock();

        final String queueXmlPath = (String)properties.get("task_queue.queue_xml_path");
        // AppScale - removed duplicate reader declaration
        QueueXmlReader reader;
        if (queueXmlPath != null)
        {
            reader = new QueueXmlReader(this.localServerEnvironment.getAppDir().getPath())
            {
                public String getFilename()
                {
                    return queueXmlPath;
                }
            };
        }
        else
            reader = new QueueXmlReader(this.localServerEnvironment.getAppDir().getPath());

        this.queueXml = reader.readQueueXml();

        logger.log(Level.INFO, "LocalTaskQueue is initialized");
        if (Boolean.valueOf((String)properties.get("task_queue.disable_auto_task_execution")).booleanValue())
        {
            this.disableAutoTaskExecution = true;
            logger.log(Level.INFO, "Automatic task execution is disabled.");
        }

        this.fetchService = new LocalURLFetchService();
        this.fetchService.init(null, new HashMap());

        this.fetchService.setTimeoutInMs(tenMinutesInMillis);

        this.rng = new Random();

        initializeCallback(properties);
    }

    private void initializeCallback( Map<String, String> properties )
    {
        String callbackOverrideClass = (String)properties.get("task_queue.callback_class");
        if (callbackOverrideClass != null)
        {
            try
            {
                this.callback = ((LocalTaskQueueCallback)newInstance(Class.forName(callbackOverrideClass)));
            }
            catch (InstantiationException e)
            {
                throw new RuntimeException(e);
            }
            catch (IllegalAccessException e)
            {
                throw new RuntimeException(e);
            }
            catch (ClassNotFoundException e)
            {
                throw new RuntimeException(e);
            }
        }
        else
        {
            this.callback = new UrlFetchServiceLocalTaskQueueCallback(this.fetchService);
        }
        this.callback.initialize(properties);
    }

    private static <E> E newInstance( Class<E> clazz ) throws InstantiationException, IllegalAccessException
    {
        try
        {
            return clazz.newInstance();
        }
        catch (IllegalAccessException e)
        {
            Constructor defaultConstructor;
            try
            {
                defaultConstructor = clazz.getDeclaredConstructor(new Class[0]);
            }
            catch (NoSuchMethodException f)
            {
                throw new InstantiationException("No zero-arg constructor.");
            }
            defaultConstructor.setAccessible(true);
            try
            {
                /*
                 * AppScale - added cast E below
                 */
                return (E)defaultConstructor.newInstance(new Object[0]);
            }
            catch (InvocationTargetException g)
            {
                throw new RuntimeException(g);
            }
        }
    }

    void setQueueXml( QueueXml queueXml )
    {
        this.queueXml = queueXml;
    }

    public void start()
    {
        AccessController.doPrivileged(new PrivilegedAction()
        {
            public Object run()
            {
                LocalTaskQueue.this.start_();
                return null;
            }
        });
    }

    private void start_()
    {
        this.shutdownHook = new Thread()
        {
            public void run()
            {
                LocalTaskQueue.this.stop_();
            }
        };
        Runtime.getRuntime().addShutdownHook(this.shutdownHook);

        this.fetchService.start();

        UrlFetchJob.initialize(this.localServerEnvironment, this.clock);

        String baseUrl = getBaseUrl(this.localServerEnvironment);
        AppScaleTaskQueueClient client = new AppScaleTaskQueueClient();

        if (this.queueXml != null)
        {
            for (QueueXml.Entry entry : this.queueXml.getEntries())
            {
                if ("pull".equals(entry.getMode()))
                {
                    this.queues.put(entry.getName(), new DevPullQueue(entry, this.clock));
                }
                else
                {
                    this.queues.put(entry.getName(), new DevPushQueue(entry, null, baseUrl, this.clock, this.callback, client));
                }

            }

        }

        if (this.queues.get("default") == null)
        {
            QueueXml.Entry entry = QueueXml.defaultEntry();
            this.queues.put(entry.getName(), new DevPushQueue(entry, null, baseUrl, this.clock, this.callback, client));
        }

        logger.info("Local task queue initialized with base url " + baseUrl);
    }

    static String getBaseUrl( LocalServerEnvironment localServerEnvironment )
    {
        String destAddress = localServerEnvironment.getAddress();
        if ("0.0.0.0".equals(destAddress))
        {
            destAddress = localHostIp;
        }
        return String.format("http://%s:%d", new Object[] { destAddress, Integer.valueOf(localServerEnvironment.getPort()) });
    }

    public void stop()
    {
        if (this.shutdownHook != null)
        {
            AccessController.doPrivileged(new PrivilegedAction()
            {
                public Void run()
                {
                    Runtime.getRuntime().removeShutdownHook(LocalTaskQueue.this.shutdownHook);
                    return null;
                }
            });
            this.shutdownHook = null;
        }
        stop_();
    }

    private void stop_()
    {
        this.queues.clear();
        this.fetchService.stop();
    }

    public String getPackage()
    {
        return PACKAGE;
    }

    private long currentTimeMillis()
    {
        return this.clock.getCurrentTime();
    }

    private long currentTimeUsec()
    {
        return currentTimeMillis() * ONE_SECOND_IN_MILLIS;
    }

    TaskQueuePb.TaskQueueServiceError.ErrorCode validateAddRequest( TaskQueuePb.TaskQueueAddRequest addRequest )
    {
        String taskName = addRequest.getTaskName();
        if ((taskName != null) && (taskName.length() != 0) && (!QueueConstants.TASK_NAME_PATTERN.matcher(taskName).matches()))
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_TASK_NAME;
        }

        String queueName = addRequest.getQueueName();
        if ((queueName == null) || (queueName.length() == 0) || (!QueueConstants.QUEUE_NAME_PATTERN.matcher(queueName).matches()))
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_NAME;
        }

        if (addRequest.getEtaUsec() < 0L)
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_ETA;
        }

        if (addRequest.getEtaUsec() - currentTimeUsec() > getMaxEtaDeltaUsec())
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_ETA;
        }

        if (addRequest.getMode() == TaskQueuePb.TaskQueueMode.Mode.PULL.getValue())
        {
            return validateAddPullRequest(addRequest);
        }
        return validateAddPushRequest(addRequest);
    }

    TaskQueuePb.TaskQueueServiceError.ErrorCode validateAddPullRequest( TaskQueuePb.TaskQueueAddRequest addRequest )
    {
        if (!addRequest.hasBody())
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_REQUEST;
        }
        return TaskQueuePb.TaskQueueServiceError.ErrorCode.OK;
    }

    TaskQueuePb.TaskQueueServiceError.ErrorCode validateAddPushRequest( TaskQueuePb.TaskQueueAddRequest addRequest )
    {
        String url = addRequest.getUrl();
        if ((!addRequest.hasUrl()) || (url.length() == 0) || (url.charAt(0) != '/') || (url.length() > QueueConstants.maxUrlLength()))
        {
            return TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_URL;
        }
        return TaskQueuePb.TaskQueueServiceError.ErrorCode.OK;
    }

    static long getMaxEtaDeltaUsec()
    {
        return QueueConstants.getMaxEtaDeltaMillis() * ONE_SECOND_IN_MILLIS;
    }

    public TaskQueuePb.TaskQueueAddResponse add( LocalRpcService.Status status, TaskQueuePb.TaskQueueAddRequest addRequest )
    {
        TaskQueuePb.TaskQueueBulkAddRequest bulkRequest = new TaskQueuePb.TaskQueueBulkAddRequest();
        TaskQueuePb.TaskQueueAddResponse addResponse = new TaskQueuePb.TaskQueueAddResponse();

        bulkRequest.addAddRequest().copyFrom(addRequest);
        TaskQueuePb.TaskQueueBulkAddResponse bulkResponse = bulkAdd(status, bulkRequest);

        if (bulkResponse.taskResultSize() != 1)
        {
            throw new InternalFailureException(String.format("expected 1 result from BulkAdd(), got %d", new Object[] { Integer.valueOf(bulkResponse.taskResultSize()) }));
        }

        int result = bulkResponse.getTaskResult(0).getResult();

        if (result != TaskQueuePb.TaskQueueServiceError.ErrorCode.OK.getValue()) throw new ApiProxy.ApplicationException(result);
        if (bulkResponse.getTaskResult(0).hasChosenTaskName())
        {
            addResponse.setChosenTaskName(bulkResponse.getTaskResult(0).getChosenTaskName());
        }

        return addResponse;
    }

    public TaskQueuePb.TaskQueueFetchQueueStatsResponse fetchQueueStats( LocalRpcService.Status status, TaskQueuePb.TaskQueueFetchQueueStatsRequest fetchQueueStatsRequest )
    {
        TaskQueuePb.TaskQueueFetchQueueStatsResponse fetchQueueStatsResponse = new TaskQueuePb.TaskQueueFetchQueueStatsResponse();

        for (String queueName : fetchQueueStatsRequest.queueNames())
        {
            TaskQueuePb.TaskQueueFetchQueueStatsResponse.QueueStats stats = new TaskQueuePb.TaskQueueFetchQueueStatsResponse.QueueStats();

            TaskQueuePb.TaskQueueScannerQueueInfo scannerInfo = new TaskQueuePb.TaskQueueScannerQueueInfo();

            scannerInfo.setEnforcedRate(this.rng.nextInt(500) + 1);
            scannerInfo.setExecutedLastMinute(this.rng.nextInt(3000));
            scannerInfo.setRequestsInFlight(this.rng.nextInt(5));
            if (this.rng.nextBoolean())
            {
                stats.setNumTasks(0);
                stats.setOldestEtaUsec(-1L);
            }
            else
            {
                stats.setNumTasks(this.rng.nextInt(2000) + 1);
                stats.setOldestEtaUsec(currentTimeMillis() * ONE_SECOND_IN_MILLIS);
            }
            stats.setScannerInfo(scannerInfo);

            fetchQueueStatsResponse.addQueueStats(stats);
        }
        return fetchQueueStatsResponse;
    }

    public TaskQueuePb.TaskQueuePurgeQueueResponse purgeQueue( LocalRpcService.Status status, TaskQueuePb.TaskQueuePurgeQueueRequest purgeQueueRequest )
    {
        TaskQueuePb.TaskQueuePurgeQueueResponse purgeQueueResponse = new TaskQueuePb.TaskQueuePurgeQueueResponse();
        flushQueue(purgeQueueRequest.getQueueName());
        return purgeQueueResponse;
    }

    public TaskQueuePb.TaskQueueBulkAddResponse bulkAdd( LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest bulkAddRequest )
    {
        TaskQueuePb.TaskQueueBulkAddResponse bulkAddResponse = new TaskQueuePb.TaskQueueBulkAddResponse();

        if (bulkAddRequest.addRequestSize() == 0)
        {
            return bulkAddResponse;
        }

        bulkAddRequest = (TaskQueuePb.TaskQueueBulkAddRequest)bulkAddRequest.clone();
        DevQueue queue = getQueueByName(bulkAddRequest.getAddRequest(0).getQueueName());

        Map chosenNames = new IdentityHashMap();

        boolean errorFound = false;

        for (TaskQueuePb.TaskQueueAddRequest addRequest : bulkAddRequest.addRequests())
        {
            TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult = bulkAddResponse.addTaskResult();
            TaskQueuePb.TaskQueueServiceError.ErrorCode error = validateAddRequest(addRequest);
            if (error == TaskQueuePb.TaskQueueServiceError.ErrorCode.OK)
            {
                if ((!addRequest.hasTaskName()) || (addRequest.getTaskName().equals("")))
                {
                    /*
                     * AppScale - accessed genTaskName non-statically
                     */
                    addRequest = addRequest.setTaskName(queue.genTaskName());
                    chosenNames.put(taskResult, addRequest.getTaskName());
                }

                taskResult.setResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.SKIPPED.getValue());
            }
            else
            {
                taskResult.setResult(error.getValue());
                errorFound = true;
            }
        }

        if (errorFound)
        {
            return bulkAddResponse;
        }

        if (bulkAddRequest.getAddRequest(0).hasTransaction())
        {
            try
            {
                ApiProxy.makeSyncCall("datastore_v3", "addActions", bulkAddRequest.toByteArray());
            }
            catch (ApiProxy.ApplicationException exception)
            {
                throw new ApiProxy.ApplicationException(exception.getApplicationError() + TaskQueuePb.TaskQueueServiceError.ErrorCode.DATASTORE_ERROR.getValue(), exception.getErrorDetail());
            }
        }
        else
        {
            for (int i = 0; i < bulkAddRequest.addRequestSize(); i++)
            {
                TaskQueuePb.TaskQueueAddRequest addRequest = bulkAddRequest.getAddRequest(i);
                TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult = bulkAddResponse.getTaskResult(i);
                try
                {
                    queue.add(addRequest);
                }
                catch (ApiProxy.ApplicationException exception)
                {
                    taskResult.setResult(exception.getApplicationError());
                }
            }
        }

        for (TaskQueuePb.TaskQueueBulkAddResponse.TaskResult taskResult : bulkAddResponse.taskResults())
        {
            if (taskResult.getResult() == TaskQueuePb.TaskQueueServiceError.ErrorCode.SKIPPED.getValue())
            {
                taskResult.setResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.OK.getValue());
                if (chosenNames.containsKey(taskResult))
                {
                    taskResult.setChosenTaskName((String)chosenNames.get(taskResult));
                }
            }
        }

        return bulkAddResponse;
    }

    public TaskQueuePb.TaskQueueDeleteResponse delete( LocalRpcService.Status status, TaskQueuePb.TaskQueueDeleteRequest request )
    {
        String queueName = request.getQueueName();

        DevQueue queue = getQueueByName(queueName);
        TaskQueuePb.TaskQueueDeleteResponse response = new TaskQueuePb.TaskQueueDeleteResponse();
        for (String taskName : request.taskNames())
        {
            try
            {
                if (!queue.deleteTask(taskName))
                    response.addResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.UNKNOWN_TASK.getValue());
                else
                    response.addResult(TaskQueuePb.TaskQueueServiceError.ErrorCode.OK.getValue());
            }
            catch (ApiProxy.ApplicationException e)
            {
                response.addResult(e.getApplicationError());
            }
        }
        return response;
    }

    public TaskQueuePb.TaskQueueQueryAndOwnTasksResponse queryAndOwnTasks( LocalRpcService.Status status, TaskQueuePb.TaskQueueQueryAndOwnTasksRequest request )
    {
        String queueName = request.getQueueName();
        validateQueueName(queueName);

        DevQueue queue = getQueueByName(queueName);

        if (queue.getMode() != TaskQueuePb.TaskQueueMode.Mode.PULL)
        {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_MODE.getValue());
        }

        DevPullQueue pullQueue = (DevPullQueue)queue;
        List results = pullQueue.queryAndOwnTasks(request.getLeaseSeconds(), request.getMaxTasks(), request.isGroupByTag(), request.getTagAsBytes());

        TaskQueuePb.TaskQueueQueryAndOwnTasksResponse response = new TaskQueuePb.TaskQueueQueryAndOwnTasksResponse();
        /*
         * AppScale - added cast to results
         */
        for (TaskQueuePb.TaskQueueAddRequest task : (List<TaskQueuePb.TaskQueueAddRequest>)results)
        {
            TaskQueuePb.TaskQueueQueryAndOwnTasksResponse.Task responseTask = response.addTask();
            responseTask.setTaskName(task.getTaskName());
            responseTask.setBodyAsBytes(task.getBodyAsBytes());
            responseTask.setEtaUsec(task.getEtaUsec());
            if (task.hasTag())
            {
                responseTask.setTagAsBytes(task.getTagAsBytes());
            }

        }

        return response;
    }

    public TaskQueuePb.TaskQueueModifyTaskLeaseResponse modifyTaskLease( LocalRpcService.Status status, TaskQueuePb.TaskQueueModifyTaskLeaseRequest request )
    {
        String queueName = request.getQueueName();
        validateQueueName(queueName);

        String taskName = request.getTaskName();
        validateTaskName(taskName);

        DevQueue queue = getQueueByName(queueName);

        if (queue.getMode() != TaskQueuePb.TaskQueueMode.Mode.PULL)
        {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_MODE.getValue());
        }

        DevPullQueue pullQueue = (DevPullQueue)queue;

        return pullQueue.modifyTaskLease(request);
    }

    public Map<String, QueueStateInfo> getQueueStateInfo()
    {
        TreeMap queueStateInfo = new TreeMap();

        for (Map.Entry entry : this.queues.entrySet())
        {
            String queueName = (String)entry.getKey();
            queueStateInfo.put(queueName, ((DevQueue)entry.getValue()).getStateInfo());
        }

        return queueStateInfo;
    }

    private DevQueue getQueueByName( String queueName )
    {
        DevQueue queue = (DevQueue)this.queues.get(queueName);
        if (queue == null)
        {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.UNKNOWN_QUEUE.getValue(), queueName);
        }
        return queue;
    }

    public void flushQueue( String queueName )
    {
        DevQueue queue = getQueueByName(queueName);
        queue.flush();
    }

    public boolean deleteTask( String queueName, String taskName )
    {
        DevQueue queue = getQueueByName(queueName);
        return queue.deleteTask(taskName);
    }

    public boolean runTask( String queueName, String taskName )
    {
        DevQueue queue = getQueueByName(queueName);
        return queue.runTask(taskName);
    }

    public Double getMaximumDeadline( boolean isOfflineRequest )
    {
        return Double.valueOf(30.0D);
    }

    static final void validateQueueName( String queueName ) throws ApiProxy.ApplicationException
    {
        if ((queueName == null) || (queueName.length() == 0) || (!QueueConstants.QUEUE_NAME_PATTERN.matcher(queueName).matches()))
        {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_QUEUE_NAME.getValue());
        }
    }

    static final void validateTaskName( String taskName ) throws ApiProxy.ApplicationException
    {
        if ((taskName == null) || (taskName.length() == 0) || (!QueueConstants.TASK_NAME_PATTERN.matcher(taskName).matches()))
        {
            throw new ApiProxy.ApplicationException(TaskQueuePb.TaskQueueServiceError.ErrorCode.INVALID_TASK_NAME.getValue());
        }
    }

    static final class UrlFetchServiceLocalTaskQueueCallback implements LocalTaskQueueCallback
    {
        private final LocalURLFetchService fetchService;

        UrlFetchServiceLocalTaskQueueCallback( LocalURLFetchService fetchService )
        {
            this.fetchService = fetchService;
        }

        public int execute( URLFetchServicePb.URLFetchRequest fetchReq )
        {
            LocalRpcService.Status status = new LocalRpcService.Status();
            return this.fetchService.fetch(status, fetchReq).getStatusCode();
        }

        public void initialize( Map<String, String> properties )
        {}
    }

    /*
     * AppScale - added private runAppScaleTask method
     */
    private void runAppScaleTask( final TaskQueueAddRequest addRequest )
    {
        AccessController.doPrivileged(new PrivilegedAction<Object>()
        {
            public Object run()
            {
                logger.fine("Running appscale task");
                new AppScaleRunTask(addRequest).run();
                return null;
            }
        });
    }
}
