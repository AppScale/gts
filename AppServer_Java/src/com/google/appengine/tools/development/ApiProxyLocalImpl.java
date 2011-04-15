package com.google.appengine.tools.development;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutput;
import java.io.ObjectOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadFactory;
import java.util.logging.Logger;

import sun.misc.Service;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.protobuf.Message;
import com.google.appengine.tools.development.ApiProxyLocal;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.apphosting.api.ApiProxy;

class ApiProxyLocalImpl implements ApiProxyLocal {
	private static final Class BYTE_ARRAY_CLASS = byte[].class;
	private static final int MAX_API_REQUEST_SIZE = 1048576*60;
	private static final Logger logger = Logger
			.getLogger(ApiProxyLocalImpl.class.getName());

	private final Map<String, LocalRpcService> serviceCache = new ConcurrentHashMap<String, LocalRpcService>();

	private final Map<String, String> properties = new HashMap<String, String>();

	private final ExecutorService apiExecutor = Executors
			.newCachedThreadPool(new DaemonThreadFactory(Executors
					.defaultThreadFactory()));
	private final LocalServiceContext context;
	private Clock clock = Clock.DEFAULT;

	protected ApiProxyLocalImpl(LocalServerEnvironment environment) {
		this.context = new LocalServiceContextImpl(environment);
	}

	public void log(ApiProxy.Environment environment, ApiProxy.LogRecord record) {
		logger.log(toJavaLevel(record.getLevel()), "[" + record.getTimestamp()
				+ "] " + record.getMessage());
	}

	public byte[] makeSyncCall(ApiProxy.Environment environment,
			String packageName, String methodName, byte[] requestBytes) {
		Future<byte[]> future = doAsyncCall(environment, packageName,
				methodName, requestBytes, null);
		try {
			return ((byte[]) future.get());
		} catch (InterruptedException ex) {
			throw new ApiProxy.CancelledException(packageName, methodName);
		} catch (CancellationException ex) {
			throw new ApiProxy.CancelledException(packageName, methodName);
		} catch (ExecutionException ex) {
			if (ex.getCause() instanceof RuntimeException)
				throw ((RuntimeException) ex.getCause());
			if (ex.getCause() instanceof Error) {
				throw ((Error) ex.getCause());
			}
			throw new ApiProxy.UnknownException(packageName, methodName, ex
					.getCause());
		}
	}

	public Future<byte[]> makeAsyncCall(ApiProxy.Environment environment,
			String packageName, String methodName, byte[] requestBytes,
			ApiProxy.ApiConfig apiConfig) {
		return doAsyncCall(environment, packageName, methodName, requestBytes,
				apiConfig);
	}

	private Future<byte[]> doAsyncCall(ApiProxy.Environment environment,
			String packageName, String methodName, byte[] requestBytes,
			ApiProxy.ApiConfig apiConfig) {
		Semaphore semaphore = (Semaphore) environment.getAttributes().get(
				"com.google.appengine.tools.development.api_call_semaphore");

		final Callable<byte[]> callable = Executors
				.privilegedCallable(new AsyncApiCall(environment, packageName,
						methodName, requestBytes, semaphore));

		if (semaphore != null) {
			try {
				semaphore.acquire();
			} catch (InterruptedException ex) {
				throw new RuntimeException(
						"Interrupted while waiting on semaphore:", ex);
			}

		}

		return ((Future<byte[]>) AccessController
				.doPrivileged(new PrivilegedAction<Future<byte[]>>() {
					public Future<byte[]> run() {
						return (Future<byte[]>) ApiProxyLocalImpl.this.apiExecutor
								.submit(callable);
					}
				}));
	}

	private <T> T convertBytesToPb(byte[] bytes, Class<T> requestClass)
			throws IllegalAccessException, InstantiationException,
			InvocationTargetException, NoSuchMethodException {
		if (ProtocolMessage.class.isAssignableFrom(requestClass)) {
			ProtocolMessage proto = (ProtocolMessage) requestClass
					.newInstance();
			proto.mergeFrom(bytes);
			return (T)proto;
		}
		if (Message.class.isAssignableFrom(requestClass)) {
			Method method = requestClass.getMethod("parseFrom",
					new Class[] { BYTE_ARRAY_CLASS });
			return (T)method.invoke(null, new Object[] { bytes });
		}
		throw new UnsupportedOperationException("Cannot convert byte[] to "
				+ requestClass);
	}

	private byte[] convertPbToBytes(Object object) {
		if (object instanceof ProtocolMessage) {
			return ((ProtocolMessage) object).toByteArray();
		}
		if (object instanceof Message) {
			return ((Message) object).toByteArray();
		}
		throw new UnsupportedOperationException("Cannot convert " + object
				+ " to byte[].");
	}

	public void setProperty(String property, String value) {
		this.properties.put(property, value);
	}

	public void setProperties(Map<String, String> properties) {
		this.properties.clear();
		if (properties != null)
			this.properties.putAll(properties);
	}

	public void stop() {
		for (LocalRpcService service : this.serviceCache.values()) {
			service.stop();
		}

		this.serviceCache.clear();
	}

	private int getMaxApiRequestSize(String packageName) {
		return MAX_API_REQUEST_SIZE;
	}

	private Method getDispatchMethod(LocalRpcService service,
			String packageName, String methodName) {
		String dispatchName = Character.toLowerCase(methodName.charAt(0))
				+ methodName.substring(1);

		for (Method method : service.getClass().getMethods()) {
			if (dispatchName.equals(method.getName())) {
				return method;
			}
		}
		throw new ApiProxy.CallNotFoundException(packageName, methodName);
	}

	public final synchronized LocalRpcService getService(final String pkg) {
		LocalRpcService cachedService = (LocalRpcService) this.serviceCache
				.get(pkg);
		if (cachedService != null) {
			return cachedService;
		}

		return ((LocalRpcService) AccessController
				.doPrivileged(new PrivilegedAction<LocalRpcService>() {
					public LocalRpcService run() {
						return ApiProxyLocalImpl.this.startServices(pkg);
					}
				}));
	}

	private LocalRpcService startServices(String pkg) {
		Iterator services = Service.providers(LocalRpcService.class,
				ApiProxyLocalImpl.class.getClassLoader());

		while (services.hasNext()) {
			LocalRpcService service = (LocalRpcService) services.next();
			if (service.getPackage().equals(pkg)) {
				service.init(this.context, this.properties);
				service.start();
				this.serviceCache.put(pkg, service);
				return service;
			}
		}
		return null;
	}

	private static java.util.logging.Level toJavaLevel(
			ApiProxy.LogRecord.Level apiProxyLevel) {
		switch (apiProxyLevel.ordinal() + 1) {
		case 1:
			return java.util.logging.Level.FINE;
		case 2:
			return java.util.logging.Level.INFO;
		case 3:
			return java.util.logging.Level.WARNING;
		case 4:
			return java.util.logging.Level.SEVERE;
		case 5:
			return java.util.logging.Level.SEVERE;
		}
		return java.util.logging.Level.WARNING;
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
			Thread thread = this.parent.newThread(r);
			thread.setDaemon(true);
			return thread;
		}
	}

	private class AsyncApiCall implements Callable<byte[]> {
		private final ApiProxy.Environment environment;
		private final String packageName;
		private final String methodName;
		private final byte[] requestBytes;
		private final Semaphore semaphore;

		public AsyncApiCall(ApiProxy.Environment paramEnvironment,
				String paramString1, String paramString2,
				byte[] paramArrayOfByte, Semaphore paramSemaphore) {
			this.environment = paramEnvironment;
			this.packageName = paramString1;
			this.methodName = paramString2;
			this.requestBytes = paramArrayOfByte;
			this.semaphore = paramSemaphore;
		}

		public byte[] call() {
			LocalRpcService service = ApiProxyLocalImpl.this
					.getService(this.packageName);

			if (service == null) {
				throw new ApiProxy.CallNotFoundException(this.packageName,
						this.methodName);
			}

			if (this.requestBytes.length > ApiProxyLocalImpl.this
					.getMaxApiRequestSize(this.packageName)) {
				throw new ApiProxy.RequestTooLargeException(this.packageName,
						this.methodName);
			}

			Method method = ApiProxyLocalImpl.this.getDispatchMethod(service,
					this.packageName, this.methodName);
			LocalRpcService.Status status = new LocalRpcService.Status();

			ApiProxy.setEnvironmentForCurrentThread(this.environment);
			try {
				Class requestClass = method.getParameterTypes()[1];
				// Object request = ApiProxyLocalImpl.this.convertBytesToPb(
				// this.requestBytes, requestClass);
				Object request = null;
				if (!packageName.equals("mapreduce")
						&& !packageName.equals("localTesting")) {
					request = convertBytesToPb(requestBytes, requestClass);
				} else {
					// System.out.println("size of array: "+
					// requestBytes.length);
					// De-serialize from a byte array
					ObjectInputStream in;
					try {
						in = new ObjectInputStream(new ByteArrayInputStream(
								requestBytes));
						request = in.readObject();
						in.close();
					} catch (IOException e) {
						e.printStackTrace();
					} catch (ClassNotFoundException e) {
						e.printStackTrace();
					}
					// System.out.println("deserialization ok!");
				}

				// byte[] arrayOfByte = ApiProxyLocalImpl.this
				// .convertPbToBytes(method.invoke(service, new Object[] {
				// status, request }));
				//
				// return arrayOfByte;
				if (!packageName.equals("mapreduce")
						&& !packageName.equals("localTesting")) {
					System.out.println("method: " + method.getName()
							+ "service: " + service.getPackage());

					return convertPbToBytes(method.invoke(service,
							new Object[] { status, request }));
				} else {
					System.out.println("method: " + method.getName()
							+ "service: " + service.getPackage());
					Object obj = method.invoke(service, new Object[] { status,
							request });
					// serialize the object
					ByteArrayOutputStream bos = new ByteArrayOutputStream();
					ObjectOutput out;
					try {
						out = new ObjectOutputStream(bos);
						out.writeObject(obj);
						out.close();
					} catch (IOException e) {
						e.printStackTrace();
					}
					// Get the bytes of the serialized object
					return bos.toByteArray();
				}
			} catch (IllegalAccessException e) {
				return null;
			} catch (InstantiationException e) {
				return null;
			} catch (NoSuchMethodException e) {
				return null;
			} catch (InvocationTargetException e) {
				return null;
			} finally {
				ApiProxy.clearEnvironmentForCurrentThread();

				if (this.semaphore != null)
					this.semaphore.release();
			}
		}
	}

	private class LocalServiceContextImpl implements LocalServiceContext {
		private final LocalServerEnvironment localServerEnvironment;

		public LocalServiceContextImpl(
				LocalServerEnvironment paramLocalServerEnvironment) {
			this.localServerEnvironment = paramLocalServerEnvironment;
		}

		public LocalServerEnvironment getLocalServerEnvironment() {
			return this.localServerEnvironment;
		}

		public Clock getClock() {
			return ApiProxyLocalImpl.this.clock;
		}
	}
}
