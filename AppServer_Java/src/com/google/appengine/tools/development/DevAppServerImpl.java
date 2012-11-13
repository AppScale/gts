package com.google.appengine.tools.development;


import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.Environment;
import java.io.File;
import java.io.PrintStream;
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


class DevAppServerImpl implements DevAppServer
{
    private final LocalServerEnvironment environment;
    private Map<String, String>          serviceProperties = new HashMap();

    private Logger                       logger            = Logger.getLogger(DevAppServerImpl.class.getName());

    private ServerState                  serverState       = ServerState.INITIALIZING;

    private ContainerService             mainContainer     = null;
    private final BackendContainer       backendContainer;
    private ApiProxyLocal                apiProxyLocal;

    public DevAppServerImpl( File appDir, File externalResourceDir, File webXmlLocation, File appEngineWebXmlLocation, String address, int port, boolean useCustomStreamHandler, Map<String, Object> containerConfigProperties )
    {
        String serverInfo = ContainerUtils.getServerInfo();
        if (useCustomStreamHandler)
        {
            StreamHandlerFactory.install();
        }
        DevSocketImplFactory.install();
        this.mainContainer = ContainerUtils.loadContainer();
        this.environment = this.mainContainer.configure(serverInfo, appDir, externalResourceDir, webXmlLocation, appEngineWebXmlLocation, address, port, containerConfigProperties, this);

        this.backendContainer = BackendServers.getInstance();
        this.backendContainer.init(appDir, externalResourceDir, webXmlLocation, appEngineWebXmlLocation, address, containerConfigProperties, this);
    }

    public void setServiceProperties( Map<String, String> properties )
    {
        if (this.serverState != ServerState.INITIALIZING)
        {
            String msg = "Cannot set service properties after the server has been started.";
            throw new IllegalStateException(msg);
        }

        this.serviceProperties = new HashMap(properties);
        this.backendContainer.setServiceProperties(properties);
    }

    public void start() throws Exception
    {
        if (this.serverState != ServerState.INITIALIZING)
        {
            throw new IllegalStateException("Cannot start a server that has already been started.");
        }

        initializeLogging();

        ApiProxyLocalFactory factory = new ApiProxyLocalFactory();
        this.apiProxyLocal = factory.create(this.environment);
        this.apiProxyLocal.setProperties(this.serviceProperties);
        ApiProxy.setDelegate(this.apiProxyLocal);

        TimeZone currentTimeZone = null;
        try
        {
            currentTimeZone = setServerTimeZone();
            this.mainContainer.startup();

            ApiProxy.Environment env = ApiProxy.getCurrentEnvironment();
            env.getAttributes().put("com.google.appengine.runtime.default_version_hostname", "localhost:" + getPort());

            this.serviceProperties.putAll(this.mainContainer.getServiceProperties());
            this.apiProxyLocal.appendProperties(this.mainContainer.getServiceProperties());

            /*
             * AppScale - added config and setting system property if config is
             * null
             */
            AppEngineWebXml config = this.mainContainer.getAppEngineWebXmlConfig();
            if (config == null)
            {
                throw new RuntimeException("applciation context config is null");
            }
            else
            {
                System.setProperty("APPLICATION_ID", config.getAppId());
            }

            this.backendContainer.startupAll(this.mainContainer.getBackendsXml(), this.apiProxyLocal);
        }
        catch (BindException ex)
        {
            System.err.println();
            System.err.println("************************************************");
            System.err.println("Could not open the requested socket: " + ex.getMessage());
            System.err.println("Try overriding --address and/or --port.");
            System.exit(2);
        }
        finally
        {
            ApiProxy.clearEnvironmentForCurrentThread();
            restoreLocalTimeZone(currentTimeZone);
        }
        this.serverState = ServerState.RUNNING;

        String prettyAddress = this.mainContainer.getAddress();
        if ((prettyAddress.equals("0.0.0.0")) || (prettyAddress.equals("127.0.0.1")))
        {
            prettyAddress = "localhost";
        }

        String listeningHostAndPort = prettyAddress + ":" + this.mainContainer.getPort();
        this.logger.info("The server is running at http://" + listeningHostAndPort + "/");
        this.logger.info("The admin console is running at http://" + listeningHostAndPort + "/_ah/admin");
    }

    private TimeZone setServerTimeZone()
    {
        String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
        if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0))
        {
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
            }
            catch (Exception ex)
            {
                throw new RuntimeException("Unable to set the TimeZone to UTC", ex);
            }
        }
    }

    private void restoreLocalTimeZone( TimeZone timeZone )
    {
        String sysTimeZone = (String)this.serviceProperties.get("appengine.user.timezone.impl");
        if ((sysTimeZone != null) && (sysTimeZone.trim().length() > 0))
        {
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
            }
            catch (Exception ex)
            {
                throw new RuntimeException("Unable to restore the previous TimeZone", ex);
            }
        }
    }

    public void restart() throws Exception
    {
        if (this.serverState != ServerState.RUNNING)
        {
            throw new IllegalStateException("Cannot restart a server that is not currently running.");
        }
        this.mainContainer.shutdown();
        this.backendContainer.shutdownAll();
        this.mainContainer.startup();
        this.backendContainer.startupAll(this.mainContainer.getBackendsXml(), this.apiProxyLocal);
    }

    public void shutdown() throws Exception
    {
        if (this.serverState != ServerState.RUNNING)
        {
            throw new IllegalStateException("Cannot shutdown a server that is not currently running.");
        }
        this.mainContainer.shutdown();
        this.backendContainer.shutdownAll();
        ApiProxy.setDelegate(null);
        this.apiProxyLocal = null;
        this.serverState = ServerState.SHUTDOWN;
    }

    public int getPort()
    {
        return this.mainContainer.getPort();
    }

    public AppContext getAppContext()
    {
        return this.mainContainer.getAppContext();
    }

    public void setThrowOnEnvironmentVariableMismatch( boolean throwOnMismatch )
    {
        this.mainContainer.setEnvironmentVariableMismatchSeverity(throwOnMismatch ? ContainerService.EnvironmentVariableMismatchSeverity.ERROR : ContainerService.EnvironmentVariableMismatchSeverity.WARNING);
    }

    private void initializeLogging()
    {
        for (Handler handler : Logger.getLogger("").getHandlers())
            if ((handler instanceof ConsoleHandler)) handler.setLevel(Level.FINEST);
    }

    ServerState getServerState()
    {
        return this.serverState;
    }

    static enum ServerState
    {
        INITIALIZING,
        RUNNING,
        STOPPING,
        SHUTDOWN;
    }
}