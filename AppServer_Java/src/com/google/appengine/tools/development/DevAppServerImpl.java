package com.google.appengine.tools.development;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.BindException;
import java.util.HashMap;
import java.util.Map;
import java.util.TimeZone;
import java.util.logging.ConsoleHandler;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.config.AppEngineWebXmlReader;

class DevAppServerImpl implements DevAppServer {
    private final LocalServerEnvironment environment;
    private Map<String, String> serviceProperties = new HashMap<String, String>();

    private Logger logger = Logger.getLogger(DevAppServerImpl.class.getName());

    private ServerState serverState = ServerState.INITIALIZING;

    private ContainerService mainContainer = null;
    private final BackgroundContainer backgroundContainer;

    public DevAppServerImpl(File appDir) {
        this(appDir, "127.0.0.1", 8080);
    }

    public DevAppServerImpl(File appDir, String address, int port) {
        this(appDir, null, null, address, port, true);
    }

    public DevAppServerImpl(File appDir, String webXmlLocation, String appEngineWebXml, String address, int port,
            boolean useCustomStreamHandler) {
        String serverInfo = ContainerUtils.getServerInfo();
        if (useCustomStreamHandler) {
            StreamHandlerFactory.install();
        }
        this.mainContainer = ContainerUtils.loadContainer();
        AppEngineWebXmlReader appEngineWebXmlReader = null;
        if (appEngineWebXml != null) {
            appEngineWebXmlReader = new AppEngineWebXmlReader(appDir.getAbsolutePath(), appEngineWebXml);
        }
        this.environment = this.mainContainer.configure(serverInfo, appDir, webXmlLocation, appEngineWebXmlReader,
                address, port);

        this.backgroundContainer = new NullBackgroundContainer();
    }

    public void setServiceProperties(Map<String, String> properties) {
        if (this.serverState != ServerState.INITIALIZING) {
            String msg = "Cannot set service properties after the server has been started.";
            throw new IllegalStateException(msg);
        }
        this.serviceProperties = properties;
        this.backgroundContainer.setServiceProperties(properties);
    }

    public void start() throws Exception {
        if (this.serverState != ServerState.INITIALIZING) {
            throw new IllegalStateException("Cannot start a server that has already been started.");
        }

        initializeLogging();

        ApiProxyLocalFactory factory = new ApiProxyLocalFactory();
        ApiProxyLocal localImpl = factory.create(this.environment);
        localImpl.setProperties(this.serviceProperties);
        ApiProxy.setDelegate(localImpl);

        TimeZone currentTimeZone = null;
        try {
            currentTimeZone = setServerTimeZone();
            this.mainContainer.startup();
            AppEngineWebXml config = this.mainContainer.getAppEngineWebXmlConfig();
            if (config == null) {
                logger.log(Level.INFO, "config is null");
            } else {
                System.setProperty("APPLICATION_ID", config.getAppId());
            }
            this.backgroundContainer.startupAll(this.mainContainer.getAppEngineWebXmlConfig());
        } catch (BindException ex) {
            System.err.println();
            System.err.println("************************************************");
            System.err.println("Could not open the requested socket: " + ex.getMessage());
            System.err.println("Try overriding --address and/or --port.");
            System.exit(2);
        } finally {
            ApiProxy.clearEnvironmentForCurrentThread();
            restoreLocalTimeZone(currentTimeZone);
        }
        this.serverState = ServerState.RUNNING;

        String prettyAddress = this.mainContainer.getAddress();
        if ((prettyAddress.equals("0.0.0.0")) || (prettyAddress.equals("127.0.0.1"))) {
            prettyAddress = "localhost";
        }
        this.logger.info("The server is running at http://" + prettyAddress + ":" + this.mainContainer.getPort() + "/");
    }

    private TimeZone setServerTimeZone() {
        String sysTimeZone = (String) this.serviceProperties.get("appengine.user.timezone.impl");
        if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0)) {
            return null;
        }

        TimeZone utc = TimeZone.getTimeZone("UTC");
        assert (utc.getID().equals("UTC")) : "Unable to retrieve the UTC TimeZone";
        try {
            Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
            f.setAccessible(true);
            ThreadLocal<?> tl = (ThreadLocal<?>) f.get(null);
            Method getZone = ThreadLocal.class.getMethod("get", new Class[0]);
            TimeZone previousZone = (TimeZone) getZone.invoke(tl, new Object[0]);
            Method setZone = ThreadLocal.class.getMethod("set", new Class[] { Object.class });
            setZone.invoke(tl, new Object[] { utc });
            return previousZone;
        } catch (Exception e) {
            throw new RuntimeException("Unable to set the TimeZone to UTC", e);
        }
    }

    private void restoreLocalTimeZone(TimeZone timeZone) {
        String sysTimeZone = (String) this.serviceProperties.get("appengine.user.timezone.impl");
        if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0)) {
            return;
        }
        try {
            Field f = TimeZone.class.getDeclaredField("defaultZoneTL");
            f.setAccessible(true);
            ThreadLocal<?> tl = (ThreadLocal<?>) f.get(null);
            Method setZone = ThreadLocal.class.getMethod("set", new Class[] { Object.class });
            setZone.invoke(tl, new Object[] { timeZone });
        } catch (Exception e) {
            throw new RuntimeException("Unable to restore the previous TimeZone", e);
        }
    }

    public void restart() throws Exception {
        if (this.serverState != ServerState.RUNNING) {
            throw new IllegalStateException("Cannot restart a server that is not currently running.");
        }
        this.mainContainer.shutdown();
        this.backgroundContainer.shutdownAll();
        this.mainContainer.startup();
        this.backgroundContainer.startupAll(this.mainContainer.getAppEngineWebXmlConfig());
    }

    public void shutdown() throws Exception {
        if (this.serverState != ServerState.RUNNING) {
            throw new IllegalStateException("Cannot shutdown a server that is not currently running.");
        }
        this.mainContainer.shutdown();
        this.backgroundContainer.shutdownAll();
        ApiProxy.setDelegate(null);
        this.serverState = ServerState.SHUTDOWN;
    }

    public int getPort() {
        return this.mainContainer.getPort();
    }

    public AppContext getAppContext() {
        return this.mainContainer.getAppContext();
    }

    public void setThrowOnEnvironmentVariableMismatch(boolean throwOnMismatch) {
        this.mainContainer
                .setEnvironmentVariableMismatchSeverity(throwOnMismatch ? ContainerService.EnvironmentVariableMismatchSeverity.ERROR
                        : ContainerService.EnvironmentVariableMismatchSeverity.WARNING);
    }

    private void initializeLogging() {
        for (Handler handler : Logger.getLogger("").getHandlers())
            if ((handler instanceof ConsoleHandler))
                handler.setLevel(Level.FINEST);
    }

    ServerState getServerState() {
        return this.serverState;
    }

    static enum ServerState {
        INITIALIZING, RUNNING, STOPPING, SHUTDOWN;
    }
}