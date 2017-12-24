package com.google.appengine.tools.development;

import com.google.appengine.api.labs.modules.dev.LocalModulesService;
import com.google.appengine.repackaged.com.google.common.base.Joiner;
import com.google.appengine.repackaged.com.google.common.base.Splitter;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableMap;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableSet;
import com.google.appengine.tools.info.SdkInfo;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.Delegate;
import com.google.apphosting.api.ApiProxy.Environment;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.config.EarHelper;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.BindException;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.TimeZone;
import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.ConsoleHandler;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.Logger;

class DevAppServerImpl implements DevAppServer {
  private final String APPLICATION_ID_PROPERTY = "APPLICATION_ID";
  public static final String MODULES_FILTER_HELPER_PROPERTY = "com.google.appengine.tools.development.modules_filter_helper";
  private static final Logger logger = Logger.getLogger(DevAppServerImpl.class.getName());
  private final ApplicationConfigurationManager applicationConfigurationManager;
  private final Modules modules;
  private Map<String, String> serviceProperties = new HashMap();
  private final Map<String, Object> containerConfigProperties;
  private final int requestedPort;
  private DevAppServerImpl.ServerState serverState;
  private final BackendServers backendContainer;
  private ApiProxyLocal apiProxyLocal;
  private final AppEngineConfigException configurationException;
  private final ScheduledExecutorService shutdownScheduler;
  private CountDownLatch shutdownLatch;

  public DevAppServerImpl(File appDir, File externalResourceDir, File webXmlLocation, File appEngineWebXmlLocation, String address, int port, boolean useCustomStreamHandler, Map<String, Object> containerConfigProperties) {
    this.serverState = DevAppServerImpl.ServerState.INITIALIZING;
    this.shutdownScheduler = Executors.newScheduledThreadPool(1);
    this.shutdownLatch = null;
    String serverInfo = ContainerUtils.getServerInfo();
    if (useCustomStreamHandler) {
      StreamHandlerFactory.install();
    }

    DevSocketImplFactory.install();
    this.backendContainer = BackendServers.getInstance();
    this.requestedPort = port;
    ApplicationConfigurationManager tempManager = null;
    File schemaFile = new File(SdkInfo.getSdkRoot(), "docs/appengine-application.xsd");

    try {
      if (EarHelper.isEar(appDir.getAbsolutePath())) {
        tempManager = ApplicationConfigurationManager.newEarConfigurationManager(appDir, SdkInfo.getLocalVersion().getRelease(), schemaFile);
        String contextRootWarning = "Ignoring application.xml context-root element, for details see https://developers.google.com/appengine/docs/java/modules/#config";
        logger.info(contextRootWarning);
      } else {
        tempManager = ApplicationConfigurationManager.newWarConfigurationManager(appDir, appEngineWebXmlLocation, webXmlLocation, externalResourceDir, SdkInfo.getLocalVersion().getRelease());
      }
    } catch (AppEngineConfigException configurationException) {
      this.modules = null;
      this.applicationConfigurationManager = null;
      this.containerConfigProperties = null;
      this.configurationException = configurationException;
      return;
    }

    this.applicationConfigurationManager = tempManager;
    this.modules = Modules.createModules(this.applicationConfigurationManager, serverInfo, externalResourceDir, address, this);
    DelegatingModulesFilterHelper modulesFilterHelper = new DelegatingModulesFilterHelper(this.backendContainer, this.modules);
    this.containerConfigProperties = (ImmutableMap<String, Object>)(Map<?,?>)(ImmutableMap.builder().putAll(containerConfigProperties).put(MODULES_FILTER_HELPER_PROPERTY, modulesFilterHelper).put("devappserver.portMappingProvider", this.backendContainer).build());
    this.backendContainer.init(address, this.applicationConfigurationManager.getPrimaryModuleConfigurationHandle(), externalResourceDir, this.containerConfigProperties, this);
    this.configurationException = null;
  }

  public void setServiceProperties(Map<String, String> properties) {
    if (this.serverState != DevAppServerImpl.ServerState.INITIALIZING) {
      String msg = "Cannot set service properties after the server has been started.";
      throw new IllegalStateException(msg);
    } else {
      if (this.configurationException == null) {
        this.serviceProperties = new ConcurrentHashMap(properties);
        if (this.requestedPort != 0) {
          DevAppServerPortPropertyHelper.setPort(this.modules.getMainModule().getModuleName(), this.requestedPort, this.serviceProperties);
        }

        this.backendContainer.setServiceProperties(properties);
        DevAppServerDatastorePropertyHelper.setDefaultProperties(this.serviceProperties);
      }

    }
  }

  Map<String, String> getServiceProperties() {
    return this.serviceProperties;
  }

  public CountDownLatch start() throws Exception {
    if (this.serverState != DevAppServerImpl.ServerState.INITIALIZING) {
      throw new IllegalStateException("Cannot start a server that has already been started.");
    } else {
      this.reportDeferredConfigurationException();
      this.initializeLogging();
      this.modules.configure(this.containerConfigProperties);

      try {
        this.modules.createConnections();
      } catch (BindException ex) {
        System.err.println();
        System.err.println("************************************************");
        System.err.println("Could not open the requested socket: " + ex.getMessage());
        System.err.println("Try overriding --address and/or --port.");
        System.exit(2);
      }

      ApiProxyLocalFactory factory = new ApiProxyLocalFactory();
      Set<String> apisUsingPythonStubs = new HashSet();
      if (System.getProperty("appengine.apisUsingPythonStubs") != null) {
        for (String api : Splitter.on(',').split(System.getProperty("appengine.apisUsingPythonStubs"))) {
          apisUsingPythonStubs.add(api);
        }
      }

      this.apiProxyLocal = factory.create(this.modules.getLocalServerEnvironment(), apisUsingPythonStubs);
      this.setInboundServicesProperty();
      this.apiProxyLocal.setProperties(this.serviceProperties);
      ApiProxy.setDelegate(this.apiProxyLocal);
      LocalModulesService localModulesService = (LocalModulesService)this.apiProxyLocal.getService(LocalModulesService.PACKAGE);
      localModulesService.setModulesController(this.modules);
      TimeZone currentTimeZone = null;

      try {
        currentTimeZone = this.setServerTimeZone();
        this.backendContainer.configureAll(this.apiProxyLocal);
        this.modules.startup();
        Module mainServer = this.modules.getMainModule();
        Map<String, String> portMapping = this.backendContainer.getPortMapping();
        AbstractContainerService.installLocalInitializationEnvironment(mainServer.getMainContainer().getAppEngineWebXmlConfig(), -1, this.getPort(), this.getPort(), (String)null, -1, portMapping);
        this.backendContainer.startupAll(this.apiProxyLocal);
      } finally {
        ApiProxy.clearEnvironmentForCurrentThread();
        this.restoreLocalTimeZone(currentTimeZone);
      }

      // AppScale: Capture sigterm in order to finish requests before exiting.
      ShutdownThread shutdownThread = new ShutdownThread(this) {
        public void run() {
          try {
            this.server.shutdown();
          } catch (Exception e) {
            e.printStackTrace();
          }
        }
      };
      Runtime.getRuntime().addShutdownHook(shutdownThread);
      // End AppScale.

      this.shutdownLatch = new CountDownLatch(1);
      this.serverState = DevAppServerImpl.ServerState.RUNNING;

      // add for AppScale
      Module mainModule = this.modules.getMainModule();
      AppEngineWebXml config = mainModule.getMainContainer().getAppEngineWebXmlConfig();
      if (config == null) {
        throw new RuntimeException("application context config is null");
      } else {
        System.setProperty(APPLICATION_ID_PROPERTY, config.getAppId());
        // AppScale: Set MODULE and VERSION env variables for taskqueue.
        System.setProperty("MODULE", mainModule.getModuleName());
        String versionId = config.getMajorVersionId();
        if (versionId == null)
          versionId = "v1";
        System.setProperty("VERSION", versionId);
        // End AppScale
      }

      logger.info("Dev App Server is now running");
      return this.shutdownLatch;
    }
  }

  public void setInboundServicesProperty() {
    ImmutableSet.Builder<String> setBuilder = ImmutableSet.builder();

    for (Object uncastHandle : applicationConfigurationManager.getModuleConfigurationHandles()) {
      ApplicationConfigurationManager.ModuleConfigurationHandle moduleConfigurationHandle = (ApplicationConfigurationManager.ModuleConfigurationHandle)uncastHandle;
      setBuilder.addAll((Iterable)moduleConfigurationHandle.getModule().getAppEngineWebXml().getInboundServices());
    }

    this.serviceProperties.put("appengine.dev.inbound-services", Joiner.on(",").useForNull("null").join((Iterable)setBuilder.build()));
  }

  private TimeZone setServerTimeZone() {
    String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
    if (sysTimeZone != null && sysTimeZone.trim().length() > 0) {
      return null;
    } else {
      TimeZone utc = TimeZone.getTimeZone("UTC");

      assert utc.getID().equals("UTC") : "Unable to retrieve the UTC TimeZone";

      try {
        Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
        f.setAccessible(true);
        ThreadLocal<?> tl = (ThreadLocal)f.get((Object)null);
        Method getZone = ThreadLocal.class.getMethod("get");
        TimeZone previousZone = (TimeZone)getZone.invoke(tl, new Object[0]);
        Method setZone = ThreadLocal.class.getMethod("set", Object.class);
        setZone.invoke(tl, utc);
        return previousZone;
      } catch (Exception e) {
        try {
          Method getZone = TimeZone.class.getDeclaredMethod("getDefaultInAppContext");
          getZone.setAccessible(true);
          TimeZone previousZone = (TimeZone)getZone.invoke((Object)null, new Object[0]);
          Method setZone = TimeZone.class.getDeclaredMethod("setDefaultInAppContext", TimeZone.class);
          setZone.setAccessible(true);
          setZone.invoke((Object)null, utc);
          return previousZone;
        } catch (Exception ex) {
          throw new RuntimeException("Unable to set the TimeZone to UTC", ex);
        }
      }
    }
  }

  private void restoreLocalTimeZone(TimeZone timeZone) {
    String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
    if (sysTimeZone == null || sysTimeZone.trim().length() <= 0) {
      try {
        Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
        f.setAccessible(true);
        ThreadLocal<?> tl = (ThreadLocal)f.get((Object)null);
        Method setZone = ThreadLocal.class.getMethod("set", Object.class);
        setZone.invoke(tl, timeZone);
      } catch (Exception e) {
        try {
          Method setZone = TimeZone.class.getDeclaredMethod("setDefaultInAppContext", TimeZone.class);
          setZone.setAccessible(true);
          setZone.invoke((Object)null, timeZone);
        } catch (Exception ex) {
          throw new RuntimeException("Unable to restore the previous TimeZone", ex);
        }
      }

    }
  }

  public CountDownLatch restart() throws Exception {
    if (this.serverState != DevAppServerImpl.ServerState.RUNNING) {
      throw new IllegalStateException("Cannot restart a server that is not currently running.");
    } else {
      this.modules.shutdown();
      this.backendContainer.shutdownAll();
      this.shutdownLatch.countDown();
      this.modules.createConnections();
      this.backendContainer.configureAll(this.apiProxyLocal);
      this.modules.startup();
      this.backendContainer.startupAll(this.apiProxyLocal);
      this.shutdownLatch = new CountDownLatch(1);
      return this.shutdownLatch;
    }
  }

  public void shutdown() throws Exception {
    logger.info("Shutting down.");
    if (this.serverState != DevAppServerImpl.ServerState.RUNNING) {
      throw new IllegalStateException("Cannot shutdown a server that is not currently running.");
    } else {
      this.modules.shutdown();
      this.backendContainer.shutdownAll();
      ApiProxy.setDelegate((Delegate)null);
      this.apiProxyLocal = null;
      this.serverState = DevAppServerImpl.ServerState.SHUTDOWN;
      this.shutdownLatch.countDown();
    }
  }

  public void gracefulShutdown() throws IllegalStateException {
    AccessController.doPrivileged(new PrivilegedAction<Future<Void>>() {
      public Future<Void> run() {
        return DevAppServerImpl.this.shutdownScheduler.schedule(new Callable<Void>() {
          public Void call() throws Exception {
            DevAppServerImpl.this.shutdown();
            return null;
          }
        }, 1000L, TimeUnit.MILLISECONDS);
      }
    });
  }

  public int getPort() {
    this.reportDeferredConfigurationException();
    return this.modules.getMainModule().getMainContainer().getPort();
  }

  protected void reportDeferredConfigurationException() {
    if (this.configurationException != null) {
      throw new AppEngineConfigException("Invalid configuration", this.configurationException);
    }
  }

  public AppContext getAppContext() {
    this.reportDeferredConfigurationException();
    return this.modules.getMainModule().getMainContainer().getAppContext();
  }

  public AppContext getCurrentAppContext() {
    AppContext result = null;
    Environment env = ApiProxy.getCurrentEnvironment();
    if (env != null && env.getVersionId() != null) {
      String moduleName = LocalEnvironment.getModuleName(env.getVersionId());
      result = this.modules.getModule(moduleName).getMainContainer().getAppContext();
    }

    return result;
  }

  public void setThrowOnEnvironmentVariableMismatch(boolean throwOnMismatch) {
    if (this.configurationException == null) {
      this.applicationConfigurationManager.setEnvironmentVariableMismatchReportingPolicy(throwOnMismatch ? EnvironmentVariableChecker.MismatchReportingPolicy.EXCEPTION : EnvironmentVariableChecker.MismatchReportingPolicy.LOG);
    }

  }

  private void initializeLogging() {
    for (Handler handler : Logger.getLogger("").getHandlers()) {
      if (handler instanceof ConsoleHandler) {
        handler.setLevel(Level.FINEST);
      }
    }

  }

  DevAppServerImpl.ServerState getServerState() {
    return this.serverState;
  }

  static enum ServerState {
    INITIALIZING,
    RUNNING,
    STOPPING,
    SHUTDOWN;
  }

  // AppScale: Needed for passing server instance to shutdown thread.
  private class ShutdownThread extends Thread {
    public DevAppServerImpl server;

    public ShutdownThread(DevAppServerImpl server) {
      super();
      this.server = server;
    }
  }
  // End AppScale.
}
