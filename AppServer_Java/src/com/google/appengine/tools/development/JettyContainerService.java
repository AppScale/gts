package com.google.appengine.tools.development;

import java.io.File;
import java.io.FilenameFilter;
import java.io.IOException;
import java.net.URL;
import java.security.Permissions;
import java.util.concurrent.Semaphore;
import java.util.logging.Level;
import java.util.logging.Logger;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.mortbay.jetty.Server;
import org.mortbay.jetty.handler.HandlerWrapper;
import org.mortbay.jetty.nio.SelectChannelConnector;
import org.mortbay.jetty.webapp.WebAppContext;
import org.mortbay.resource.Resource;
import org.mortbay.util.Scanner;

import com.google.appengine.tools.development.AbstractContainerService;
import com.google.appengine.tools.development.AppContext;
import com.google.appengine.tools.development.ContainerService;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.jetty.DevAppEngineWebAppContext;
import com.google.apphosting.utils.jetty.JettyLogger;
import com.google.apphosting.utils.jetty.StubSessionManager;

@ServiceProvider(ContainerService.class)
public class JettyContainerService extends AbstractContainerService
{
  private static final Logger log = Logger.getLogger(JettyContainerService.class.getName());
   	
  public static final String WEB_DEFAULTS_XML = "com/google/appengine/tools/development/webdefault.xml";
  private static final int MAX_SIMULTANEOUS_API_CALLS = 10;
  private static final String[] CONFIG_CLASSES = { "org.mortbay.jetty.webapp.WebXmlConfiguration", "org.mortbay.jetty.webapp.TagLibConfiguration" };
  private static final String WEB_XML_ATTR = "com.google.appengine.tools.development.webXml";
  private static final String APPENGINE_WEB_XML_ATTR = "com.google.appengine.tools.development.appEngineWebXml";
  private static final int SCAN_INTERVAL_SECONDS = 5;
  private WebAppContext context;
  private AppContext appContext;
  private Server server;
  private Scanner scanner;

  protected File initContext()
    throws IOException
  {
	 
    this.context = new DevAppEngineWebAppContext(this.appDir, this.devAppServerVersion);
    this.appContext = new JettyAppContext();

    this.context.setDescriptor(this.webXmlLocation);

    this.context.setDefaultsDescriptor("com/google/appengine/tools/development/webdefault.xml");

    this.context.setConfigurationClasses(CONFIG_CLASSES);

    File appRoot = determineAppRoot();
    URL[] classPath = getClassPathForApp(appRoot);
    this.context.setClassLoader(new IsolatedAppClassLoader(appRoot, classPath, JettyContainerService.class.getClassLoader()));

    return appRoot;
  }

  protected void startContainer() throws Exception
  {
    this.context.setAttribute("com.google.appengine.tools.development.webXml", this.webXml);
    this.context.setAttribute("com.google.appengine.tools.development.appEngineWebXml", this.appEngineWebXml);

    Thread currentThread = Thread.currentThread();
    ClassLoader previousCcl = currentThread.getContextClassLoader();
    currentThread.setContextClassLoader(null);
    try
    {
      ApiProxyHandler apiHandler = new ApiProxyHandler(this.appEngineWebXml);
      apiHandler.setHandler(this.context);

      SelectChannelConnector connector = new SelectChannelConnector();
      connector.setHost(this.address);
      connector.setPort(this.port);
//      System.out.println("num of acceptors: "+connector.getAcceptors());
//      System.out.println("acceptor size: "+connector.getAcceptQueueSize());
      connector.setSoLingerTime(0);

      this.server = new Server();
      this.server.addConnector(connector);
      this.server.setHandler(apiHandler);

      if (!(isSessionsEnabled())) {
        this.context.getSessionHandler().setSessionManager(new StubSessionManager());
      }
      this.server.start();
      this.port = connector.getLocalPort();
    } finally {
      currentThread.setContextClassLoader(previousCcl);
    }
  }

  protected void stopContainer() throws Exception
  {
    this.server.stop();
  }

  protected void startHotDeployScanner()
    throws Exception
  {
    this.scanner = new Scanner();
    this.scanner.setScanInterval(5);
    this.scanner.setScanDir(getScanTarget());
    this.scanner.setFilenameFilter(new FilenameFilter()
    {
      public boolean accept(File dir, String name) {
        try {
          return (name.equals(JettyContainerService.this.getScanTarget().getName()));
        }
        catch (Exception e)
        {
        }

        return false;
      }
    });
    this.scanner.scan();
    this.scanner.addListener(new ScannerListener());
    this.scanner.start();
  }

  protected void stopHotDeployScanner() throws Exception
  {
    if (this.scanner != null) {
      this.scanner.stop();
    }
    this.scanner = null;
  }

  private File getScanTarget()
    throws Exception
  {
    if (this.appDir.isFile()) {
      return this.appDir;
    }

    return new File(this.context.getWebInf().getFile().getPath() + File.separator + "appengine-web.xml");
  }

  protected void reloadWebApp()
    throws Exception
  {
    this.server.getHandler().stop();
    restoreSystemProperties();

    Thread currentThread = Thread.currentThread();
    ClassLoader previousCcl = currentThread.getContextClassLoader();
    currentThread.setContextClassLoader(null);
    try
    {
      File webAppDir = initContext();
      loadAppEngineWebXml(webAppDir);

      if (!(isSessionsEnabled())) {
        this.context.getSessionHandler().setSessionManager(new StubSessionManager());
      }
      this.context.setAttribute("com.google.appengine.tools.development.webXml", this.webXml);
      this.context.setAttribute("com.google.appengine.tools.development.appEngineWebXml", this.appEngineWebXml);

      ApiProxyHandler apiHandler = new ApiProxyHandler(this.appEngineWebXml);
      apiHandler.setHandler(this.context);
      this.server.setHandler(apiHandler);
      

      apiHandler.start();
    } finally {
      currentThread.setContextClassLoader(previousCcl);
    }
  }

  public AppContext getAppContext()
  {
    return this.appContext;
  }

  private File determineAppRoot()
    throws IOException
  {
    Resource webInf = this.context.getWebInf();
    if (webInf == null) {
      throw new AppEngineConfigException("Supplied application has to contain WEB-INF directory.");
    }
    return webInf.getFile().getParentFile();
  }

  static
  {
    System.setProperty("org.mortbay.log.class", JettyLogger.class.getName());
  }

  private class ApiProxyHandler extends HandlerWrapper
  {
    private final AppEngineWebXml appEngineWebXml;

    public ApiProxyHandler(AppEngineWebXml paramAppEngineWebXml)
    {
      this.appEngineWebXml = paramAppEngineWebXml;
      
    }

    public void handle(String target, HttpServletRequest request, HttpServletResponse response, int dispatch)
      throws IOException, ServletException
    {
    	if (dispatch == 1) {
        Semaphore semaphore = new Semaphore(10);

        LocalEnvironment env = new LocalHttpRequestEnvironment(this.appEngineWebXml, request);
        env.getAttributes().put("com.google.appengine.tools.development.api_call_semaphore", semaphore);
        ApiProxy.setEnvironmentForCurrentThread(env);
        try {
			super.handle(target, request, response, dispatch);
	
          if (request.getRequestURI().startsWith("/_ah/reloadwebapp"))
            try {
              JettyContainerService.this.reloadWebApp();
              JettyContainerService.log.info("Reloaded the webapp context: " + request.getParameter("info"));
            } catch (Exception ex) {
              JettyContainerService.log.log(Level.WARNING, "Failed to reload the current webapp context.", ex);
            }
        }
        finally
        {
          try {
            semaphore.acquire(10);
//            System.out.println("semaphores at hand!");
          } catch (InterruptedException ex) {
            JettyContainerService.log.log(Level.WARNING, "Interrupted while waiting for API calls to complete:", ex);
          }
          ApiProxy.clearEnvironmentForCurrentThread();
        }
      }
      else
      {
			super.handle(target, request, response, dispatch);
		}
      }
    
  }

  private class ScannerListener
    implements Scanner.DiscreteListener
  {
    public void fileAdded(String filename)
      throws Exception
    {
      fileChanged(filename);
    }

    public void fileChanged(String filename) throws Exception
    {
      JettyContainerService.log.info(filename + " updated, reloading the webapp!");
      JettyContainerService.this.reloadWebApp();
    }

    public void fileRemoved(String filename)
      throws Exception
    {
    }
  }

  private class JettyAppContext
    implements AppContext
  {
    public IsolatedAppClassLoader getClassLoader()
    {
      return ((IsolatedAppClassLoader)JettyContainerService.this.context.getClassLoader());
    }

    public Permissions getUserPermissions()
    {
      return JettyContainerService.this.getUserPermissions();
    }

    public Permissions getApplicationPermissions()
    {
      return getClassLoader().getAppPermissions();
    }

    public Object getContainerContext()
    {
      return JettyContainerService.this.context;
    }
  }
}