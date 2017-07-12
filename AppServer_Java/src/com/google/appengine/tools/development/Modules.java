package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableMap;
import com.google.appengine.tools.development.ApplicationConfigurationManager;
import com.google.appengine.tools.development.AutomaticModule;
import com.google.appengine.tools.development.DevAppServerImpl;
import com.google.appengine.tools.development.InstanceHolder;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.ManualModule;
import com.google.appengine.tools.development.Module;
import com.google.appengine.tools.development.ModulesController;
import com.google.appengine.tools.development.ModulesFilterHelper;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import java.io.File;
import java.io.IOException;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public class Modules implements ModulesController, ModulesFilterHelper {
   private static final Logger LOGGER = Logger.getLogger(Modules.class.getName());
   private final List modules;
   private final Map moduleNameToModuleMap;
   private final Lock dynamicConfigurationLock = new ReentrantLock();
   private static final int DYNAMIC_CONFIGURATION_TIMEOUT_SECONDS = 2;

   // The number of seconds an instance is allowed to finish serving requests after it receives a shutdown signal.
   private static final int MAX_INSTANCE_RESPONSE_TIME = 600;

   static Modules createModules(ApplicationConfigurationManager applicationConfigurationManager, String serverInfo, File externalResourceDir, String address, DevAppServerImpl devAppServer) {
      ImmutableList.Builder builder = ImmutableList.builder();

      for(Iterator i$ = applicationConfigurationManager.getModuleConfigurationHandles().iterator(); i$.hasNext(); externalResourceDir = null) {
         ApplicationConfigurationManager.ModuleConfigurationHandle moduleConfigurationHandle = (ApplicationConfigurationManager.ModuleConfigurationHandle)i$.next();
         AppEngineWebXml appEngineWebXml = moduleConfigurationHandle.getModule().getAppEngineWebXml();
         Object module = null;
         if(!appEngineWebXml.getBasicScaling().isEmpty()) {
            throw new AppEngineConfigException("Basic scaling modules are currently not supported");
         }

         if(!appEngineWebXml.getManualScaling().isEmpty()) {
            module = new ManualModule(moduleConfigurationHandle, serverInfo, address, devAppServer, appEngineWebXml);
         } else {
            module = new AutomaticModule(moduleConfigurationHandle, serverInfo, externalResourceDir, address, devAppServer);
         }

         builder.add(module);
      }

      return new Modules(builder.build());
   }

   void shutdown() throws Exception {
      // Prevent instances from serving new requests.
      for (Object uncastModule : this.modules) {
         Module module = (Module) uncastModule;
         JettyContainerService container = (JettyContainerService) module.getMainContainer();
         container.requestShutdown();
      }

      LOGGER.info("Waiting for instances to finish serving requests");
      long deadline = System.currentTimeMillis() + (MAX_INSTANCE_RESPONSE_TIME * 1000);
      while (true) {
         if (System.currentTimeMillis() > deadline) {
            LOGGER.log(Level.SEVERE, "Request timeout while shutting down");
            break;
         }

         boolean requestsInProgress = false;
         for (Object uncastModule : this.modules) {
            Module module = (Module) uncastModule;
            JettyContainerService container = (JettyContainerService) module.getMainContainer();
            if (container.getRequestCount() > 0)
               requestsInProgress = true;
         }

         if (!requestsInProgress)
            break;

         Thread.sleep(500);
      }

      for (Object uncastModule : this.modules) {
         Module module = (Module) uncastModule;
         module.shutdown();
      }
   }

   void configure(Map containerConfigProperties) throws Exception {
      Iterator i$ = this.modules.iterator();

      while(i$.hasNext()) {
         Module module = (Module)i$.next();
         module.configure(containerConfigProperties);
      }

   }

   void createConnections() throws Exception {
      Iterator i$ = this.modules.iterator();

      while(i$.hasNext()) {
         Module module = (Module)i$.next();
         module.createConnection();
      }

   }

   void startup() throws Exception {
      Iterator i$ = this.modules.iterator();

      while(i$.hasNext()) {
         Module module = (Module)i$.next();
         module.startup();
      }

   }

   Module getMainModule() {
      return (Module)this.modules.get(0);
   }

   private Modules(List modules) {
      if(modules.size() < 1) {
         throw new IllegalArgumentException("modules must not be empty.");
      } else {
         this.modules = modules;
         ImmutableMap.Builder mapBuilder = ImmutableMap.builder();
         Iterator i$ = this.modules.iterator();

         while(i$.hasNext()) {
            Module module = (Module)i$.next();
            mapBuilder.put(module.getModuleName(), module);
         }

         this.moduleNameToModuleMap = mapBuilder.build();
      }
   }

   LocalServerEnvironment getLocalServerEnvironment() {
      return ((Module)this.modules.get(0)).getLocalServerEnvironment();
   }

   Module getModule(String moduleName) {
      return (Module)this.moduleNameToModuleMap.get(moduleName);
   }

   public Iterable getModuleNames() {
      return this.moduleNameToModuleMap.keySet();
   }

   public Iterable getVersions(String moduleName) throws ApplicationException {
      return ImmutableList.of(this.getDefaultVersion(moduleName));
   }

   public String getDefaultVersion(String moduleName) throws ApplicationException {
      Module module = this.getRequiredModule(moduleName);
      return module.getMainContainer().getAppEngineWebXmlConfig().getMajorVersionId();
   }

   public int getNumInstances(String moduleName, String version) throws ApplicationException {
      Module module = this.getRequiredModule(moduleName);
      this.checkVersion(version, module);
      AppEngineWebXml.ManualScaling manualScaling = this.getRequiredManualScaling(module);
      return Integer.parseInt(manualScaling.getInstances());
   }

   public String getHostname(String moduleName, String version, int instance) throws ApplicationException {
      Module module = this.getRequiredModule(moduleName);
      this.checkVersion(version, module);
      if(instance != -1) {
         this.getRequiredManualScaling(module);
      }

      String hostAndPort = module.getHostAndPort(instance);
      if(hostAndPort == null) {
         throw new ApplicationException(3, "Instance " + instance + " not found");
      } else {
         return hostAndPort;
      }
   }

   public void startModule(final String moduleName, final String version) throws ApplicationException {
      this.doDynamicConfiguration("startServing", new Runnable() {
         public void run() {
            Modules.this.doStartModule(moduleName, version);
         }
      });
   }

   private void doStartModule(String moduleName, String version) {
      Module module = this.getRequiredModule(moduleName);
      this.checkVersion(version, module);
      this.getRequiredManualScaling(module);

      try {
         module.startServing();
      } catch (Exception var5) {
         LOGGER.log(Level.SEVERE, "startServing failed", var5);
         throw new ApplicationException(5, "startServing failed with error " + var5.getMessage());
      }
   }

   public void stopModule(final String moduleName, final String version) throws ApplicationException {
      this.doDynamicConfiguration("stopServing", new Runnable() {
         public void run() {
            Modules.this.doStopModule(moduleName, version);
         }
      });
   }

   private void doDynamicConfiguration(String operation, Runnable runnable) {
      try {
         if(this.dynamicConfigurationLock.tryLock(2L, TimeUnit.SECONDS)) {
            try {
               runnable.run();
            } finally {
               this.dynamicConfigurationLock.unlock();
            }

         } else {
            LOGGER.log(Level.SEVERE, "stopServing timed out");
            throw new ApplicationException(5, operation + " timed out");
         }
      } catch (InterruptedException var7) {
         LOGGER.log(Level.SEVERE, "stopServing interrupted", var7);
         throw new ApplicationException(5, operation + " interrupted " + var7.getMessage());
      }
   }

   private void doStopModule(String moduleName, String version) {
      Module module = this.getRequiredModule(moduleName);
      this.checkVersion(version, module);
      this.getRequiredManualScaling(module);

      try {
         module.stopServing();
      } catch (Exception var5) {
         LOGGER.log(Level.SEVERE, "stopServing failed", var5);
         throw new ApplicationException(5, "stopServing failed with error " + var5.getMessage());
      }
   }

   private Module getRequiredModule(String moduleName) {
      Module module = (Module)this.moduleNameToModuleMap.get(moduleName);
      if(module == null) {
         throw new ApplicationException(1, "Module not found");
      } else {
         return module;
      }
   }

   private AppEngineWebXml.ManualScaling getRequiredManualScaling(Module module) {
      AppEngineWebXml.ManualScaling manualScaling = module.getMainContainer().getAppEngineWebXmlConfig().getManualScaling();
      if(manualScaling.isEmpty()) {
         LOGGER.warning("Module " + module.getModuleName() + " must be a manual scaling module");
         throw new ApplicationException(2, "Manual scaling is required.");
      } else {
         return manualScaling;
      }
   }

   private void checkVersion(String version, Module module) {
      String moduleVersion = module.getMainContainer().getAppEngineWebXmlConfig().getMajorVersionId();
      if(version == null || !version.equals(moduleVersion)) {
         throw new ApplicationException(2, "Version not found");
      }
   }

   public boolean acquireServingPermit(String moduleName, int instanceNumber, boolean allowQueueOnBackends) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getInstanceHolder(instanceNumber);
      return instanceHolder.acquireServingPermit();
   }

   public int getAndReserveFreeInstance(String moduleName) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getAndReserveAvailableInstanceHolder();
      return instanceHolder == null?-1:instanceHolder.getInstance();
   }

   public void returnServingPermit(String moduleName, int instance) {
   }

   public boolean checkInstanceExists(String moduleName, int instance) {
      Module module = this.getModule(moduleName);
      return module != null && module.getInstanceHolder(instance) != null;
   }

   public boolean checkModuleExists(String moduleName) {
      return this.getModule(moduleName) != null;
   }

   public boolean checkModuleStopped(String serverName) {
      return this.checkInstanceStopped(serverName, -1);
   }

   public boolean checkInstanceStopped(String moduleName, int instance) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getInstanceHolder(instance);
      return instanceHolder.isStopped();
   }

   public void forwardToInstance(String requestedModule, int instance, HttpServletRequest hrequest, HttpServletResponse hresponse) throws IOException, ServletException {
      Module module = this.getModule(requestedModule);
      InstanceHolder instanceHolder = module.getInstanceHolder(instance);
      instanceHolder.getContainerService().forwardToServer(hrequest, hresponse);
   }

   public boolean isLoadBalancingInstance(String moduleName, int instance) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getInstanceHolder(instance);
      return instanceHolder.isLoadBalancingInstance();
   }

   public boolean expectsGeneratedStartRequests(String moduleName, int instance) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getInstanceHolder(instance);
      return instanceHolder.expectsGeneratedStartRequest();
   }

   public int getPort(String moduleName, int instance) {
      Module module = this.getModule(moduleName);
      InstanceHolder instanceHolder = module.getInstanceHolder(instance);
      return instanceHolder.getContainerService().getPort();
   }
}
