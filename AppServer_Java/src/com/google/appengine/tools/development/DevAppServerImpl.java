package com.google.appengine.tools.development;

import com.google.appengine.api.labs.servers.dev.LocalServersService;
import com.google.appengine.repackaged.com.google.common.base.Joiner;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableMap;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableSet;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableSet.Builder;
import com.google.appengine.tools.info.SdkInfo;
import com.google.appengine.tools.info.Version;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.Environment;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.config.EarHelper;
import com.google.apphosting.utils.config.WebModule;
import java.io.File;
import java.io.PrintStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.BindException;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.HashMap;
import java.util.Map;
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

class DevAppServerImpl
  implements DevAppServer
{
  private final String APPLICATION_ID_PROPERTY = "APPLICATION_ID";
  public static final String SERVERS_FILTER_HELPER_PROPERTY = "com.google.appengine.tools.development.servers_filter_helper";
  private static final Logger logger = Logger.getLogger(DevAppServerImpl.class.getName());
  private final ApplicationConfigurationManager applicationConfigurationManager;
  private final Servers servers;
  private Map<String, String> serviceProperties = new HashMap();
  private final Map<String, Object> containerConfigProperties;
  private ServerState serverState = ServerState.INITIALIZING;
  private final BackendServers backendContainer;
  private ApiProxyLocal apiProxyLocal;
  private final AppEngineConfigException configurationException;
  private final ScheduledExecutorService shutdownScheduler = Executors.newScheduledThreadPool(1);

  private CountDownLatch shutdownLatch = null;

  public DevAppServerImpl(File appDir, File externalResourceDir, File webXmlLocation, File appEngineWebXmlLocation, String address, int port, boolean useCustomStreamHandler, Map<String, Object> containerConfigProperties)
  {
    String serverInfo = ContainerUtils.getServerInfo();
    if (useCustomStreamHandler) {
      StreamHandlerFactory.install();
    }
    DevSocketImplFactory.install();

    this.backendContainer = BackendServers.getInstance();
    ApplicationConfigurationManager tempManager = null;
    File schemaFile = new File(SdkInfo.getSdkRoot(), "docs/appengine-application.xsd");
    try {
      if (EarHelper.isEar(appDir.getAbsolutePath())) {
        tempManager = ApplicationConfigurationManager.newEarConfigurationManager(appDir, SdkInfo.getLocalVersion().getRelease(), schemaFile);
      }
      else {
        tempManager = ApplicationConfigurationManager.newWarConfigurationManager(appDir, appEngineWebXmlLocation, webXmlLocation, externalResourceDir, SdkInfo.getLocalVersion().getRelease());
      }
    }
    catch (AppEngineConfigException configurationException)
    {
      this.servers = null;
      this.applicationConfigurationManager = null;
      this.containerConfigProperties = null;
      this.configurationException = configurationException;
      return;
    }
    this.applicationConfigurationManager = tempManager;
    this.servers = Servers.createServers(this.applicationConfigurationManager, serverInfo, externalResourceDir, address, port, this);

    DelegatingServersFilterHelper serversFilterHelper = new DelegatingServersFilterHelper(this.backendContainer, this.servers);

    this.containerConfigProperties = (ImmutableMap<String, Object>)(Map<?,?>)(ImmutableMap.builder().putAll(containerConfigProperties).put("com.google.appengine.tools.development.servers_filter_helper", serversFilterHelper).put("devappserver.portMappingProvider", this.backendContainer).build());

    this.backendContainer.init(address, this.applicationConfigurationManager.getPrimaryServerConfigurationHandle(), externalResourceDir, this.containerConfigProperties, this);

    this.configurationException = null;
  }

  public void setServiceProperties(Map<String, String> properties)
  {
    if (this.serverState != ServerState.INITIALIZING) {
      String msg = "Cannot set service properties after the server has been started.";
      throw new IllegalStateException(msg);
    }

    if (this.configurationException == null)
    {
      this.serviceProperties = new ConcurrentHashMap(properties);
      this.backendContainer.setServiceProperties(properties);
    }
  }

  Map<String, String> getServiceProperties() {
    return this.serviceProperties;
  }

  public CountDownLatch start()
    throws Exception
  {
    if (this.serverState != ServerState.INITIALIZING) {
      throw new IllegalStateException("Cannot start a server that has already been started.");
    }

    reportDeferredConfigurationException();

    initializeLogging();
    this.servers.configure(this.containerConfigProperties);
    try {
      this.servers.createConnections();
    } catch (BindException ex) {
      System.err.println();
      System.err.println("************************************************");
      System.err.println("Could not open the requested socket: " + ex.getMessage());
      System.err.println("Try overriding --address and/or --port.");
      System.exit(2);
    }

    ApiProxyLocalFactory factory = new ApiProxyLocalFactory();
    this.apiProxyLocal = factory.create(this.servers.getLocalServerEnvironment());
    setInboundServicesProperty();
    this.apiProxyLocal.setProperties(this.serviceProperties);
    ApiProxy.setDelegate(this.apiProxyLocal);
    LocalServersService localServersService = (LocalServersService)this.apiProxyLocal.getService("servers");

    localServersService.setServersControler(this.servers);
    TimeZone currentTimeZone = null;
    try {
      currentTimeZone = setServerTimeZone();
      this.backendContainer.configureAll(this.apiProxyLocal);
      this.servers.startup();
      Server mainServer = this.servers.getMainServer();

      Map portMapping = this.backendContainer.getPortMapping();
      AbstractContainerService.installLocalInitializationEnvironment(mainServer.getMainContainer().getAppEngineWebXmlConfig(), -1, getPort(), null, -1, portMapping);

      this.backendContainer.startupAll(this.apiProxyLocal);
    } finally {
      ApiProxy.clearEnvironmentForCurrentThread();
      restoreLocalTimeZone(currentTimeZone);
    }
    this.shutdownLatch = new CountDownLatch(1);
    this.serverState = ServerState.RUNNING;

    // add for AppScale
    Server mainServer = this.servers.getMainServer();
    AppEngineWebXml config = mainServer.getMainContainer().getAppEngineWebXmlConfig();
    if (config == null)
    {
        throw new RuntimeException("applciation context config is null");
    }
    else
    {
        System.setProperty(APPLICATION_ID_PROPERTY, config.getAppId());
    }
    logger.info("Dev App Server is now running");
    return this.shutdownLatch;
  }

  public void setInboundServicesProperty() {
    ImmutableSet.Builder setBuilder = ImmutableSet.builder();

    for (ApplicationConfigurationManager.ServerConfigurationHandle serverConfigurationHandle : this.applicationConfigurationManager.getServerConfigurationHandles()) {
      setBuilder.addAll(serverConfigurationHandle.getModule().getAppEngineWebXml().getInboundServices());
    }

    this.serviceProperties.put("appengine.dev.inbound-services", Joiner.on(",").useForNull("null").join(setBuilder.build()));
  }

  private TimeZone setServerTimeZone()
  {
    String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
    if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0)) {
      return null;
    }

    TimeZone utc = TimeZone.getTimeZone("UTC");
    assert (utc.getID().equals("UTC")) : "Unable to retrieve the UTC TimeZone";
    try
    {
      Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
      f.setAccessible(true);
      ThreadLocal tl = (ThreadLocal)f.get(null);
      Method getZone = ThreadLocal.class.getMethod("get", new Class[0]);
      TimeZone previousZone = (TimeZone)getZone.invoke(tl, new Object[0]);
      Method setZone = ThreadLocal.class.getMethod("set", new Class[] { Object.class });
      setZone.invoke(tl, new Object[] { utc });
      return previousZone;
    }
    catch (Exception e)
    {
      try
      {
        Method getZone = TimeZone.class.getDeclaredMethod("getDefaultInAppContext", new Class[0]);
        getZone.setAccessible(true);
        TimeZone previousZone = (TimeZone)getZone.invoke(null, new Object[0]);
        Method setZone = TimeZone.class.getDeclaredMethod("setDefaultInAppContext", new Class[] { TimeZone.class });
        setZone.setAccessible(true);
        setZone.invoke(null, new Object[] { utc });
        return previousZone;
      } catch (Exception ex) {
        throw new RuntimeException("Unable to set the TimeZone to UTC", ex);
      }
    }
  }

  private void restoreLocalTimeZone(TimeZone timeZone)
  {
    String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
    if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0)) {
      return;
    }
    try
    {
      Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
      f.setAccessible(true);
      ThreadLocal tl = (ThreadLocal)f.get(null);
      Method setZone = ThreadLocal.class.getMethod("set", new Class[] { Object.class });
      setZone.invoke(tl, new Object[] { timeZone });
    }
    catch (Exception e)
    {
      try
      {
        Method setZone = TimeZone.class.getDeclaredMethod("setDefaultInAppContext", new Class[] { TimeZone.class });
        setZone.setAccessible(true);
        setZone.invoke(null, new Object[] { timeZone });
      } catch (Exception ex) {
        throw new RuntimeException("Unable to restore the previous TimeZone", ex);
      }
    }
  }

  public CountDownLatch restart() throws Exception
  {
    if (this.serverState != ServerState.RUNNING) {
      throw new IllegalStateException("Cannot restart a server that is not currently running.");
    }
    this.servers.shutdown();
    this.backendContainer.shutdownAll();
    this.shutdownLatch.countDown();
    this.servers.createConnections();
    this.backendContainer.configureAll(this.apiProxyLocal);
    this.servers.startup();
    this.backendContainer.startupAll(this.apiProxyLocal);
    this.shutdownLatch = new CountDownLatch(1);
    return this.shutdownLatch;
  }

  public void shutdown() throws Exception
  {
    if (this.serverState != ServerState.RUNNING) {
      throw new IllegalStateException("Cannot shutdown a server that is not currently running.");
    }
    this.servers.shutdown();
    this.backendContainer.shutdownAll();
    ApiProxy.setDelegate(null);
    this.apiProxyLocal = null;
    this.serverState = ServerState.SHUTDOWN;
    this.shutdownLatch.countDown();
  }

  public void gracefulShutdown()
    throws IllegalStateException
  {
    AccessController.doPrivileged(new PrivilegedAction()
    {
      public Future<Void> run() {
        return DevAppServerImpl.this.shutdownScheduler.schedule(new Callable()
        {
          public Void call() throws Exception {
            DevAppServerImpl.this.shutdown();
            return null;
          }
        }
        , 1000L, TimeUnit.MILLISECONDS);
      }
    });
  }

  public int getPort()
  {
    reportDeferredConfigurationException();
    return this.servers.getMainServer().getMainContainer().getPort();
  }

  protected void reportDeferredConfigurationException() {
    if (this.configurationException != null)
      throw new AppEngineConfigException("Invalid configuration", this.configurationException);
  }

  public AppContext getAppContext()
  {
    reportDeferredConfigurationException();
    return this.servers.getMainServer().getMainContainer().getAppContext();
  }

  public AppContext getCurrentAppContext()
  {
    AppContext result = null;
    ApiProxy.Environment env = ApiProxy.getCurrentEnvironment();

    if ((env != null) && (env.getVersionId() != null)) {
      String serverName = LocalEnvironment.getServerName(env.getVersionId());
      result = this.servers.getServer(serverName).getMainContainer().getAppContext();
    }
    return result;
  }

  public void setThrowOnEnvironmentVariableMismatch(boolean throwOnMismatch)
  {
    if (this.configurationException == null)
      this.applicationConfigurationManager.setEnvironmentVariableMismatchReportingPolicy(throwOnMismatch ? EnvironmentVariableChecker.MismatchReportingPolicy.EXCEPTION : EnvironmentVariableChecker.MismatchReportingPolicy.LOG);
  }

  private void initializeLogging()
  {
    for (Handler handler : Logger.getLogger("").getHandlers())
      if ((handler instanceof ConsoleHandler))
        handler.setLevel(Level.FINEST);
  }

  ServerState getServerState()
  {
    return this.serverState;
  }

  static enum ServerState
  {
    INITIALIZING, RUNNING, STOPPING, SHUTDOWN;
  }
}
