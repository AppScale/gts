package com.google.appengine.tools.development;

import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.log.dev.DevLogHandler;
import com.google.appengine.api.log.dev.LocalLogService;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.tools.development.AbstractContainerService;
import com.google.appengine.tools.development.AppContext;
import com.google.appengine.tools.development.ContainerService;
import com.google.appengine.tools.development.DevAppEngineWebAppContext;
import com.google.appengine.tools.development.DevAppServer;
import com.google.appengine.tools.development.IsolatedAppClassLoader;
import com.google.appengine.tools.development.LocalHttpRequestEnvironment;
import com.google.appengine.tools.development.SerializableObjectsOnlyHashSessionManager;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.config.WebModule;
import com.google.apphosting.utils.jetty.JettyLogger;
import com.google.apphosting.utils.jetty.StubSessionManager;
import java.io.File;
import java.io.FilenameFilter;
import java.io.IOException;
import java.net.URL;
import java.security.Permissions;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.concurrent.Semaphore;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.servlet.RequestDispatcher;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpServletResponseWrapper;
import org.mortbay.jetty.Server;
import org.mortbay.jetty.handler.HandlerWrapper;
import org.mortbay.jetty.nio.SelectChannelConnector;
import org.mortbay.jetty.servlet.DatastoreSessionManager;
import org.mortbay.jetty.servlet.ServletHolder;
import org.mortbay.jetty.servlet.SessionHandler;
import org.mortbay.jetty.webapp.WebAppContext;
import org.mortbay.resource.Resource;
import org.mortbay.util.Scanner;

@ServiceProvider(ContainerService.class)
public class JettyContainerService extends AbstractContainerService {
   private static final Logger log = Logger.getLogger(JettyContainerService.class.getName());
   public static final String WEB_DEFAULTS_XML = "com/google/appengine/tools/development/webdefault.xml";
   private static final int MAX_SIMULTANEOUS_API_CALLS = 100;
   private static final Long SOFT_DEADLINE_DELAY_MS = Long.valueOf(60000L);
   private static final String[] CONFIG_CLASSES = new String[]{"org.mortbay.jetty.webapp.WebXmlConfiguration", "org.mortbay.jetty.webapp.TagLibConfiguration"};
   private static final String WEB_XML_ATTR = "com.google.appengine.tools.development.webXml";
   private static final String APPENGINE_WEB_XML_ATTR = "com.google.appengine.tools.development.appEngineWebXml";
   private static final int SCAN_INTERVAL_SECONDS = 5;
   private WebAppContext context;
   private AppContext appContext;
   private Server server;
   private Scanner scanner;

   protected File initContext() throws IOException {
      this.context = new DevAppEngineWebAppContext(this.appDir, this.externalResourceDir, this.devAppServerVersion, this.apiProxyLocal, this.devAppServer);
      this.appContext = new JettyContainerService.JettyAppContext(null);
      this.context.setDescriptor(this.webXmlLocation == null?null:this.webXmlLocation.getAbsolutePath());
      this.context.setDefaultsDescriptor("com/google/appengine/tools/development/webdefault.xml");
      this.context.setConfigurationClasses(CONFIG_CLASSES);
      File appRoot = this.determineAppRoot();
      this.installLocalInitializationEnvironment();
      URL[] classPath = this.getClassPathForApp(appRoot);
      this.context.setClassLoader(new IsolatedAppClassLoader(appRoot, this.externalResourceDir, classPath, JettyContainerService.class.getClassLoader()));
      if(Boolean.parseBoolean(System.getProperty("appengine.allowRemoteShutdown"))) {
         this.context.addServlet(new ServletHolder(new JettyContainerService.ServerShutdownServlet()), "/_ah/admin/quit");
      }

      return appRoot;
   }

   protected void connectContainer() throws Exception {
      this.moduleConfigurationHandle.checkEnvironmentVariables();
      Thread currentThread = Thread.currentThread();
      ClassLoader previousCcl = currentThread.getContextClassLoader();
      currentThread.setContextClassLoader((ClassLoader)null);

      try {
         SelectChannelConnector connector = new SelectChannelConnector();
         connector.setHost(this.address);
         connector.setPort(this.port);
         connector.setSoLingerTime(0);
         connector.open();
         this.server = new Server();
         this.server.addConnector(connector);
         this.port = connector.getLocalPort();
      } finally {
         currentThread.setContextClassLoader(previousCcl);
      }

   }

   protected void startContainer() throws Exception {
      this.context.setAttribute("com.google.appengine.tools.development.webXml", this.webXml);
      this.context.setAttribute("com.google.appengine.tools.development.appEngineWebXml", this.appEngineWebXml);
      Thread currentThread = Thread.currentThread();
      ClassLoader previousCcl = currentThread.getContextClassLoader();
      currentThread.setContextClassLoader((ClassLoader)null);

      try {
         JettyContainerService.ApiProxyHandler apiHandler = new JettyContainerService.ApiProxyHandler(this.appEngineWebXml);
         apiHandler.setHandler(this.context);
         this.server.setHandler(apiHandler);
         SessionHandler handler = this.context.getSessionHandler();
         if(this.isSessionsEnabled()) {
            handler.setSessionManager(new DatastoreSessionManager(DatastoreServiceFactory.getDatastoreService()));
         } else {
            handler.setSessionManager(new StubSessionManager());
         }

         this.server.start();
      } finally {
         currentThread.setContextClassLoader(previousCcl);
      }

   }

   protected void stopContainer() throws Exception {
      this.server.stop();
   }

   protected void startHotDeployScanner() throws Exception {
      String fullScanInterval = System.getProperty("appengine.fullscan.seconds");
      if(fullScanInterval != null) {
         try {
            int ex = Integer.parseInt(fullScanInterval);
            if(ex < 1) {
               log.info("Full scan of the web app for changes is disabled.");
               return;
            }

            log.info("Full scan of the web app in place every " + ex + "s.");
            this.fullWebAppScanner(ex);
            return;
         } catch (NumberFormatException var3) {
            log.log(Level.WARNING, "appengine.fullscan.seconds property is not an integer:", var3);
            log.log(Level.WARNING, "Using the default scanning method.");
         }
      }

      this.scanner = new Scanner();
      this.scanner.setScanInterval(5);
      this.scanner.setScanDirs(ImmutableList.of(this.getScanTarget()));
      this.scanner.setFilenameFilter(new FilenameFilter() {
         public boolean accept(File dir, String name) {
            try {
               return name.equals(JettyContainerService.this.getScanTarget().getName());
            } catch (Exception var4) {
               return false;
            }
         }
      });
      this.scanner.scan();
      this.scanner.addListener(new JettyContainerService.ScannerListener(null));
      this.scanner.start();
   }

   protected void stopHotDeployScanner() throws Exception {
      if(this.scanner != null) {
         this.scanner.stop();
      }

      this.scanner = null;
   }

   private File getScanTarget() throws Exception {
      return !this.appDir.isFile() && this.context.getWebInf() != null?new File(this.context.getWebInf().getFile().getPath() + File.separator + "appengine-web.xml"):this.appDir;
   }

   private void fullWebAppScanner(int interval) throws IOException {
      String webInf = this.context.getWebInf().getFile().getPath();
      ArrayList scanList = new ArrayList();
      scanList.add(new File(webInf, "classes"));
      scanList.add(new File(webInf, "lib"));
      scanList.add(new File(webInf, "web.xml"));
      scanList.add(new File(webInf, "appengine-web.xml"));
      this.scanner = new Scanner();
      this.scanner.setScanInterval(interval);
      this.scanner.setScanDirs(scanList);
      this.scanner.setReportExistingFilesOnStartup(false);
      this.scanner.setRecursive(true);
      this.scanner.scan();
      this.scanner.addListener(new Scanner.BulkListener() {
         public void filesChanged(List changedFiles) throws Exception {
            JettyContainerService.log.info("A file has changed, reloading the web application.");
            JettyContainerService.this.reloadWebApp();
         }
      });
      this.scanner.start();
   }

   protected void reloadWebApp() throws Exception {
      this.server.getHandler().stop();
      this.moduleConfigurationHandle.restoreSystemProperties();
      this.moduleConfigurationHandle.readConfiguration();
      this.moduleConfigurationHandle.checkEnvironmentVariables();
      this.extractFieldsFromWebModule(this.moduleConfigurationHandle.getModule());
      Thread currentThread = Thread.currentThread();
      ClassLoader previousCcl = currentThread.getContextClassLoader();
      currentThread.setContextClassLoader((ClassLoader)null);

      try {
         File webAppDir = this.initContext();
         this.installLoggingServiceHandler();
         this.installLocalInitializationEnvironment();
         if(!this.isSessionsEnabled()) {
            this.context.getSessionHandler().setSessionManager(new StubSessionManager());
         }

         this.context.setAttribute("com.google.appengine.tools.development.webXml", this.webXml);
         this.context.setAttribute("com.google.appengine.tools.development.appEngineWebXml", this.appEngineWebXml);
         JettyContainerService.ApiProxyHandler apiHandler = new JettyContainerService.ApiProxyHandler(this.appEngineWebXml);
         apiHandler.setHandler(this.context);
         this.server.setHandler(apiHandler);
         apiHandler.start();
      } finally {
         currentThread.setContextClassLoader(previousCcl);
      }

   }

   public AppContext getAppContext() {
      return this.appContext;
   }

   // AppScale: Allows dispatcher to access request handler.
   public void requestShutdown() {
      ApiProxyHandler handler = (ApiProxyHandler) this.server.getHandler();
      handler.requestShutdown();
   }

   public int getRequestCount() {
      ApiProxyHandler handler = (ApiProxyHandler) this.server.getHandler();
      return handler.getRequestCount();
   }
   // End AppScale.

   public void forwardToServer(HttpServletRequest hrequest, HttpServletResponse hresponse) throws IOException, ServletException {
      log.finest("forwarding request to module: " + this.appEngineWebXml.getModule() + "." + this.instance);
      RequestDispatcher requestDispatcher = this.context.getServletContext().getRequestDispatcher(hrequest.getRequestURI());
      requestDispatcher.forward(hrequest, hresponse);
   }

   private File determineAppRoot() throws IOException {
      Resource webInf = this.context.getWebInf();
      if(webInf == null) {
         if(this.userCodeClasspathManager.requiresWebInf()) {
            throw new AppEngineConfigException("Supplied application has to contain WEB-INF directory.");
         } else {
            return this.appDir;
         }
      } else {
         return webInf.getFile().getParentFile();
      }
   }

   static {
      System.setProperty("org.mortbay.log.class", JettyLogger.class.getName());
   }

   private class RecordingResponseWrapper extends HttpServletResponseWrapper {
      private int status = 200;

      RecordingResponseWrapper(HttpServletResponse response) {
         super(response);
      }

      public void setStatus(int sc) {
         this.status = sc;
         super.setStatus(sc);
      }

      public int getStatus() {
         return this.status;
      }

      public void sendError(int sc) throws IOException {
         this.status = sc;
         super.sendError(sc);
      }

      public void sendError(int sc, String msg) throws IOException {
         this.status = sc;
         super.sendError(sc, msg);
      }

      public void sendRedirect(String location) throws IOException {
         this.status = 302;
         super.sendRedirect(location);
      }

      public void setStatus(int status, String string) {
         super.setStatus(status, string);
         this.status = status;
      }

      public void reset() {
         super.reset();
         this.status = 200;
      }
   }

   private class ApiProxyHandler extends HandlerWrapper {
      private final AppEngineWebXml appEngineWebXml;

      // AppScale: Keeps track of active requests in case of shutdown.
      private int requestCount;
      private boolean sigtermSent;
      private ReentrantLock gracefulShutdownLock;
      // End AppScale.

      public ApiProxyHandler(AppEngineWebXml appEngineWebXml) {
         this.appEngineWebXml = appEngineWebXml;
         this.requestCount = 0;
         this.gracefulShutdownLock = new ReentrantLock();
      }

      // AppScale: A wrapper for handling requests that keeps track of active requests.
      public void handle(String target, HttpServletRequest request, HttpServletResponse response, int dispatch) throws IOException, ServletException {
         this.gracefulShutdownLock.lock();
         try {
            if (this.sigtermSent) {
               response.sendError(503, "This instance is shutting down");
               return;
            }
            this.requestCount++;
         } finally {
            this.gracefulShutdownLock.unlock();
         }

         handleImpl(target, request, response, dispatch);

         this.gracefulShutdownLock.lock();
         try {
            this.requestCount--;
         } finally {
            this.gracefulShutdownLock.unlock();
         }
      }
      // End AppScale.

      // AppScale: Allows container to manipulate handler state.
      public void requestShutdown() {
         this.gracefulShutdownLock.lock();
         try {
            this.sigtermSent = true;
         } finally {
            this.gracefulShutdownLock.unlock();
         }
      }

      public int getRequestCount() {
         return this.requestCount;
      }
      // End AppScale.

      private void handleImpl(String target, HttpServletRequest request, HttpServletResponse response, int dispatch) throws IOException, ServletException {
         if(dispatch == 1) {
            long startTimeUsec = System.currentTimeMillis() * 1000L;
            Semaphore semaphore = new Semaphore(100);
            LocalHttpRequestEnvironment env = new LocalHttpRequestEnvironment(this.appEngineWebXml.getAppId(), WebModule.getModuleName(this.appEngineWebXml), this.appEngineWebXml.getMajorVersionId(), JettyContainerService.this.instance, Integer.valueOf(JettyContainerService.this.getPort()), request, JettyContainerService.SOFT_DEADLINE_DELAY_MS, JettyContainerService.this.modulesFilterHelper);
            env.getAttributes().put("com.google.appengine.tools.development.api_call_semaphore", semaphore);

            // AppScale: Override default version hostname.
            String nginxPort = ResourceLoader.getNginxPort();
            String defaultVersionHostname = System.getProperty("NGINX_ADDR") + ":" + nginxPort;
            env.getAttributes().put("com.google.appengine.runtime.default_version_hostname", defaultVersionHostname);
            // End AppScale

            ApiProxy.setEnvironmentForCurrentThread(env);
            JettyContainerService.RecordingResponseWrapper wrappedResponse = JettyContainerService.this.new RecordingResponseWrapper(response);
            boolean var43 = false;

            try {
               var43 = true;
               super.handle(target, request, wrappedResponse, dispatch);
               if(request.getRequestURI().startsWith("/_ah/reloadwebapp")) {
                  try {
                     JettyContainerService.this.reloadWebApp();
                     JettyContainerService.log.info("Reloaded the webapp context: " + request.getParameter("info"));
                     var43 = false;
                  } catch (Exception var48) {
                     JettyContainerService.log.log(Level.WARNING, "Failed to reload the current webapp context.", var48);
                     var43 = false;
                  }
               } else {
                  var43 = false;
               }
            } finally {
               if(var43) {
                  try {
                     semaphore.acquire(100);
                  } catch (InterruptedException var45) {
                     JettyContainerService.log.log(Level.WARNING, "Interrupted while waiting for API calls to complete:", var45);
                  }

                  env.callRequestEndListeners();

                  try {
                     String appId1 = env.getAppId();
                     String versionId1 = env.getVersionId();
                     String requestId1 = DevLogHandler.getRequestId();
                     long endTimeUsec1 = (new Date()).getTime() * 1000L;
                     LocalLogService logService1 = (LocalLogService)JettyContainerService.this.apiProxyLocal.getService("logservice");
                     logService1.addRequestInfo(appId1, versionId1, requestId1, request.getRemoteAddr(), request.getRemoteUser(), startTimeUsec, endTimeUsec1, request.getMethod(), request.getRequestURI(), request.getProtocol(), request.getHeader("User-Agent"), true, Integer.valueOf(wrappedResponse.getStatus()), request.getHeader("Referrer"));
                     logService1.clearResponseSize();
                  } finally {
                     ApiProxy.clearEnvironmentForCurrentThread();
                  }
               }
            }

            try {
               semaphore.acquire(100);
            } catch (InterruptedException var47) {
               JettyContainerService.log.log(Level.WARNING, "Interrupted while waiting for API calls to complete:", var47);
            }

            env.callRequestEndListeners();

            try {
               String appId = env.getAppId();
               String versionId = env.getVersionId();
               String requestId = DevLogHandler.getRequestId();
               long endTimeUsec = (new Date()).getTime() * 1000L;
               LocalLogService logService = (LocalLogService)JettyContainerService.this.apiProxyLocal.getService("logservice");
               logService.addRequestInfo(appId, versionId, requestId, request.getRemoteAddr(), request.getRemoteUser(), startTimeUsec, endTimeUsec, request.getMethod(), request.getRequestURI(), request.getProtocol(), request.getHeader("User-Agent"), true, Integer.valueOf(wrappedResponse.getStatus()), request.getHeader("Referrer"));
               logService.clearResponseSize();
            } finally {
               ApiProxy.clearEnvironmentForCurrentThread();
            }
         } else {
            super.handle(target, request, response, dispatch);
         }

      }
   }

   private class ScannerListener implements Scanner.DiscreteListener {
      private ScannerListener() {
      }

      public void fileAdded(String filename) throws Exception {
         this.fileChanged(filename);
      }

      public void fileChanged(String filename) throws Exception {
         JettyContainerService.log.info(filename + " updated, reloading the webapp!");
         JettyContainerService.this.reloadWebApp();
      }

      public void fileRemoved(String filename) throws Exception {
      }

      // $FF: synthetic method
      ScannerListener(Object x1) {
         this();
      }
   }

   static class ServerShutdownServlet extends HttpServlet {
      protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
         resp.getWriter().println("Shutting down local server.");
         resp.flushBuffer();
         DevAppServer server = (DevAppServer)this.getServletContext().getAttribute("com.google.appengine.devappserver.Server");
         server.gracefulShutdown();
      }
   }

   private class JettyAppContext implements AppContext {
      private JettyAppContext() {
      }

      public IsolatedAppClassLoader getClassLoader() {
         return (IsolatedAppClassLoader)JettyContainerService.this.context.getClassLoader();
      }

      public Permissions getUserPermissions() {
         return JettyContainerService.this.getUserPermissions();
      }

      public Permissions getApplicationPermissions() {
         return this.getClassLoader().getAppPermissions();
      }

      public Object getContainerContext() {
         return JettyContainerService.this.context;
      }

      // $FF: synthetic method
      JettyAppContext(Object x1) {
         this();
      }
   }
}
