package com.google.appengine.tools.development;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.ServiceLoader;
import java.util.concurrent.Callable;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.protobuf.Message;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApiConfig;
import com.google.apphosting.api.ApiProxy.CallNotFoundException;
import com.google.apphosting.api.ApiProxy.Environment;
import com.google.apphosting.api.ApiProxy.LogRecord;
import com.google.apphosting.api.ApiProxy.UnknownException;

/**
 * Implements ApiProxy.Delegate such that the requests are dispatched to local
 * service implementations. Used for both the
 * {@link com.google.appengine.tools.development.DevAppServer} and for unit
 * testing services.
 * 
 */
class ApiProxyLocalImpl implements ApiProxyLocal {
    private static final Class<?> BYTE_ARRAY_CLASS = byte[].class;
    /**
     * The maximum size of any given API request.
     */
    private static final int MAX_API_REQUEST_SIZE = 1048576;

    private static final Logger logger = Logger.getLogger(ApiProxyLocalImpl.class.getName());

    private final Map<String, LocalRpcService> serviceCache = new ConcurrentHashMap<String, LocalRpcService>();

    private final Map<String, String> properties = new HashMap<String, String>();

    private final ExecutorService apiExecutor = Executors.newCachedThreadPool(new DaemonThreadFactory(Executors
            .defaultThreadFactory()));
    private final LocalServiceContext context;
    private Clock clock = Clock.DEFAULT;

    /**
     * Creates the local proxy in a given context
     * 
     * @param environment
     *            the local server environment.
     */
    protected ApiProxyLocalImpl(LocalServerEnvironment environment) {
        this.context = new LocalServiceContextImpl(environment);
    }

    public void log(Environment environment, LogRecord record) {
        logger.log(toJavaLevel(record.getLevel()), record.getMessage());
    }

    public void flushLogs(Environment environment) {
        System.err.flush();
    }

    public byte[] makeSyncCall(Environment environment, String packageName, String methodName, byte[] requestBytes) {
        Future<byte[]> future = makeAsyncCall(environment, packageName, methodName, requestBytes, null);
        try {
            return future.get();
        } catch (InterruptedException ex) {
            throw new ApiProxy.CancelledException(packageName, methodName);
        } catch (CancellationException ex) {
            throw new ApiProxy.CancelledException(packageName, methodName);
        } catch (ExecutionException ex) {
            if ((ex.getCause() instanceof RuntimeException)) {
                throw ((RuntimeException) ex.getCause());
            } else if ((ex.getCause() instanceof Error)) {
                throw ((Error) ex.getCause());
            } else
                throw new UnknownException(packageName, methodName, ex.getCause());
        }
    }

    public Future<byte[]> makeAsyncCall(Environment environment, String packageName, String methodName,
            byte[] requestBytes, ApiConfig apiConfig) {
        Semaphore semaphore = (Semaphore) environment.getAttributes().get(LocalEnvironment.API_CALL_SEMAPHORE);

        if (semaphore != null) {
            try {
                semaphore.acquire();
            } catch (InterruptedException ex) {
                throw new RuntimeException("Interrupted while waiting on semaphore:", ex);
            }
        }
        AsyncApiCall asyncApiCall = new AsyncApiCall(environment, packageName, methodName, requestBytes, semaphore);

        boolean success = false;
        try {
            Callable<byte[]> callable = Executors.privilegedCallable(asyncApiCall);

            Future<byte[]> result = AccessController.doPrivileged(new PrivilegedApiAction(callable, asyncApiCall));

            success = true;
            return result;
        } finally {
            if (!success) {
                asyncApiCall.tryReleaseSemaphore();
            }
        }
    }

    public List<Thread> getRequestThreads(Environment environment) {
         return Arrays.asList(new Thread[] { Thread.currentThread() });
     }

    /**
     * Convert the specified byte array to a protocol buffer representation of
     * the specified type. This type can either be a subclass of
     * {@link ProtocolMessage} (a legacy protocol buffer implementation), or
     * {@link Message} (the open-sourced protocol buffer implementation).
     */
    private <T> T convertBytesToPb(byte[] bytes, Class<T> requestClass) throws IllegalAccessException,
            InstantiationException, InvocationTargetException, NoSuchMethodException {
        if (ProtocolMessage.class.isAssignableFrom(requestClass)) {
            ProtocolMessage<?> proto = (ProtocolMessage<?>) requestClass.newInstance();
            proto.mergeFrom(bytes);
            return requestClass.cast(proto);
        }
        if (Message.class.isAssignableFrom(requestClass)) {
            Method method = requestClass.getMethod("parseFrom", BYTE_ARRAY_CLASS);
            return requestClass.cast(method.invoke(null, bytes));
        }
        throw new UnsupportedOperationException("Cannot convert byte[] to " + requestClass);
    }

    /**
     * Convert the protocol buffer representation to a byte array. The object
     * can either be an instance of {@link ProtocolMessage} (a legacy protocol
     * buffer implementation), or {@link Message} (the open-sourced protocol
     * buffer implementation).
     */
    private byte[] convertPbToBytes(Object object) {
        if ((object instanceof ProtocolMessage<?>)) {
            return ((ProtocolMessage<?>) object).toByteArray();
        }
        if ((object instanceof Message)) {
            return ((Message) object).toByteArray();
        }
        throw new UnsupportedOperationException("Cannot convert " + object + " to byte[].");
    }

    public void setProperty(String property, String value) {
        this.properties.put(property, value);
    }

    public void setProperties(Map<String, String> properties) {
        this.properties.clear();
        if (properties != null)
            this.properties.putAll(properties);
    }

    public void appendProperties(Map<String, String> properties) {
        this.properties.putAll(properties);
    }

    public void stop() {
        for (LocalRpcService service : this.serviceCache.values()) {
            service.stop();
        }

        this.serviceCache.clear();
    }

    int getMaxApiRequestSize(String packageName) {
        if ("images".equals(packageName)) {
            return 33554432;
        }
        if ("memcache".equals(packageName)) {
            return 33554432;
        }
        if ("mail".equals(packageName)) {
            return 33554432;
        }
        return MAX_API_REQUEST_SIZE;
    }

    private Method getDispatchMethod(LocalRpcService service, String packageName, String methodName) {
        String dispatchName = Character.toLowerCase(methodName.charAt(0)) + methodName.substring(1);

        for (Method method : service.getClass().getMethods()) {
            if (dispatchName.equals(method.getName())) {
                return method;
            }
        }
        throw new CallNotFoundException(packageName, methodName);
    }

    /**
     * Method needs to be synchronized to ensure that we don't end up starting
     * multiple instances of the same service. As an example, we've seen a race
     * condition where the local datastore service has not yet been initialized
     * and two datastore requests come in at the exact same time. The first
     * request looks in the service cache, doesn't find it, starts a new local
     * datastore service, registers it in the service cache, and uses that local
     * datastore service to handle the first request. Meanwhile the second
     * request looks in the service cache, doesn't find it, starts a new local
     * datastore service, registers it in the service cache (stomping on the
     * original one), and uses that local datastore service to handle the second
     * request. If both of these requests start txns we can end up with 2
     * requests receiving the same txn id, and that yields all sorts of exciting
     * behavior. So, we synchronize this method to ensure that we only register
     * a single instance of each service type.
     */
    public final synchronized LocalRpcService getService(final String pkg) {
        LocalRpcService cachedService = serviceCache.get(pkg);
        if (cachedService != null) {
            return cachedService;
        }

        return (LocalRpcService) AccessController.doPrivileged(new PrivilegedAction<LocalRpcService>() {
            public LocalRpcService run() {
                return startServices(pkg);
            }
        });
    }

    @SuppressWarnings( { "restriction", "unchecked" })
    private LocalRpcService startServices(String pkg) {
        // @SuppressWarnings( { "unchecked", "sunapi" })
        for (LocalRpcService service : ServiceLoader.load(LocalRpcService.class, ApiProxyLocalImpl.class.getClassLoader()))
        {
            if (service.getPackage().equals(pkg)) {
                service.init(context, properties);
                service.start();
                serviceCache.put(pkg, service);
                return service;
            }
        }
        return null;
    }

    private static Level toJavaLevel(LogRecord.Level apiProxyLevel) {
        switch (apiProxyLevel) {
        case debug:
            return Level.FINE;
        case info:
            return Level.INFO;
        case warn:
            return Level.WARNING;
        case error:
            return Level.SEVERE;
        case fatal:
            return Level.SEVERE;
        }
        return Level.WARNING;
    }

    public Clock getClock() {
        return this.clock;
    }

    public void setClock(Clock clock) {
        this.clock = clock;
    }

    private static class DaemonThreadFactory implements ThreadFactory {
        private final ThreadFactory parent;

        public DaemonThreadFactory(ThreadFactory parent) {
            this.parent = parent;
        }

        public Thread newThread(Runnable r) {
            Thread thread = parent.newThread(r);
            thread.setDaemon(true);
            return thread;
        }
    }

    private class AsyncApiCall implements Callable<byte[]> {
        private final Environment environment;
        private final String packageName;
        private final String methodName;
        private final byte[] requestBytes;
        private final Semaphore semaphore;
        private boolean released;

        public AsyncApiCall(Environment environment, String packageName, String methodName, byte[] requestBytes,
                Semaphore semaphore) {
            this.environment = environment;
            this.packageName = packageName;
            this.methodName = methodName;
            this.requestBytes = requestBytes;
            this.semaphore = semaphore;
        }

        public byte[] call() {
            try {
                return callInternal();
            } finally {
                tryReleaseSemaphore();
            }
        }

        private byte[] callInternal() {
            LocalRpcService service = getService(this.packageName);

            if (service == null) {
                throw new ApiProxy.CallNotFoundException(this.packageName, this.methodName);
            }

            if (requestBytes.length > getMaxApiRequestSize(this.packageName)) {
                throw new ApiProxy.RequestTooLargeException(this.packageName, this.methodName);
            }

            Method method = getDispatchMethod(service, this.packageName, this.methodName);
            LocalRpcService.Status status = new LocalRpcService.Status();

            ApiProxy.setEnvironmentForCurrentThread(this.environment);
            try {
                Class<?> requestClass = method.getParameterTypes()[1];
                Object request = convertBytesToPb(this.requestBytes, requestClass);

                return convertPbToBytes(method.invoke(service, new Object[] { status, request }));
            } catch (IllegalAccessException e) {
                throw new UnknownException(this.packageName, this.methodName, e);
            } catch (InstantiationException e) {
                throw new UnknownException(this.packageName, this.methodName, e);
            } catch (NoSuchMethodException e) {
                throw new UnknownException(this.packageName, this.methodName, e);
            } catch (InvocationTargetException e) {
                if ((e.getCause() instanceof RuntimeException)) {
                    throw ((RuntimeException) e.getCause());
                }
                throw new ApiProxy.UnknownException(this.packageName, this.methodName, e.getCause());
            } finally {
                ApiProxy.clearEnvironmentForCurrentThread();
            }
        }

        /**
         * Synchronized method that ensures the semaphore that was claimed for
         * this API call only gets released once.
         */
        synchronized void tryReleaseSemaphore() {
            if (!released && semaphore != null) {
                this.semaphore.release();
                this.released = true;
            }
        }
    }

    private class PrivilegedApiAction implements PrivilegedAction<Future<byte[]>> {
        private final Callable<byte[]> callable;
        private final AsyncApiCall asyncApiCall;

        PrivilegedApiAction(Callable<byte[]> callable, AsyncApiCall asyncApiCall) {
            this.callable = callable;
            this.asyncApiCall = asyncApiCall;
        }

        public Future<byte[]> run() {
            final Future<byte[]> result = apiExecutor.submit(callable);
            return new Future<byte[]>() {
                public boolean cancel(final boolean mayInterruptIfRunning) {
                    return (AccessController.doPrivileged(new PrivilegedAction<Boolean>() {
                        public Boolean run() {
                            asyncApiCall.tryReleaseSemaphore();
                            return (result.cancel(mayInterruptIfRunning));
                        }
                    }));
                }

                public boolean isCancelled() {
                    return result.isCancelled();
                }

                public boolean isDone() {
                    return result.isDone();
                }

                public byte[] get() throws InterruptedException, ExecutionException {
                    return result.get();
                }

                public byte[] get(long timeout, TimeUnit unit) throws InterruptedException, ExecutionException,
                        TimeoutException {
                    return result.get(timeout, unit);
                }
            };
        }
    }

    /** Implementation of the {@link LocalServiceContext} interface */
    private class LocalServiceContextImpl implements LocalServiceContext {
        /** The local server environment */
        private final LocalServerEnvironment localServerEnvironment;
        private final LocalCapabilitiesEnvironment localCapabilitiesEnvironment = new LocalCapabilitiesEnvironment(System.getProperties());

        /**
         * Creates a new context, for the given application.
         * 
         * @param localServerEnvironment
         *            The environment for the local server.
         */
        public LocalServiceContextImpl(LocalServerEnvironment localServerEnvironment) {
            this.localServerEnvironment = localServerEnvironment;
        }

        public LocalServerEnvironment getLocalServerEnvironment() {
            return this.localServerEnvironment;
        }

        public LocalCapabilitiesEnvironment getLocalCapabilitiesEnvironment() {
            return this.localCapabilitiesEnvironment;
        }

        public Clock getClock() {
            return clock;
        }

        public LocalRpcService getLocalService(String packageName) {
            return ApiProxyLocalImpl.this.getService(packageName);
        }
    }
}
