package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.common.base.Objects;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableSortedMap;
import com.google.appengine.tools.development.EnvironmentVariableChecker;
import com.google.appengine.tools.development.LocalURLFetchServiceStreamHandler;
import com.google.appengine.tools.development.LoggingConfigurationManager;
import com.google.appengine.tools.development.SystemPropertiesManager;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import com.google.apphosting.utils.config.BackendsXml;
import com.google.apphosting.utils.config.BackendsXmlReader;
import com.google.apphosting.utils.config.BackendsYamlReader;
import com.google.apphosting.utils.config.EarHelper;
import com.google.apphosting.utils.config.EarInfo;
import com.google.apphosting.utils.config.WebModule;
import java.io.File;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;
import javax.annotation.concurrent.GuardedBy;

public class ApplicationConfigurationManager {
   private static final Logger LOGGER = Logger.getLogger(ApplicationConfigurationManager.class.getName());
   private final File configurationRoot;
   private final SystemPropertiesManager systemPropertiesManager;
   private final String sdkRelease;
   private final File applicationSchemaFile;
   @GuardedBy("this")
   private EnvironmentVariableChecker.MismatchReportingPolicy environmentVariableMismatchReportingPolicy;
   @GuardedBy("this")
   private final List moduleConfigurationHandles;

   static ApplicationConfigurationManager newEarConfigurationManager(File earRoot, String sdkVersion, File applicationSchemaFile) throws AppEngineConfigException {
      if(!EarHelper.isEar(earRoot.getAbsolutePath())) {
         String message = String.format("ApplicationConfigurationManager.newEarConfigurationManager passed an invalid EAR: %s", new Object[]{earRoot.getAbsolutePath()});
         LOGGER.severe(message);
         throw new AppEngineConfigException(message);
      } else {
         return new ApplicationConfigurationManager(earRoot, (File)null, (File)null, (File)null, sdkVersion, applicationSchemaFile);
      }
   }

   static ApplicationConfigurationManager newWarConfigurationManager(File warRoot, File appEngineWebXmlLocation, File webXmlLocation, File externalResourceDirectory, String sdkRelease) throws AppEngineConfigException {
      if(EarHelper.isEar(warRoot.getAbsolutePath())) {
         String message = String.format("ApplicationConfigurationManager.newWarConfigurationManager passed an EAR: %s", new Object[]{warRoot.getAbsolutePath()});
         LOGGER.severe(message);
         throw new AppEngineConfigException(message);
      } else {
         return new ApplicationConfigurationManager(warRoot, appEngineWebXmlLocation, webXmlLocation, externalResourceDirectory, sdkRelease, (File)null);
      }
   }

   ApplicationConfigurationManager.ModuleConfigurationHandle getPrimaryModuleConfigurationHandle() {
      return (ApplicationConfigurationManager.ModuleConfigurationHandle)this.moduleConfigurationHandles.get(0);
   }

   List getModuleConfigurationHandles() {
      return this.moduleConfigurationHandles;
   }

   private ApplicationConfigurationManager(File configurationRoot, File appEngineWebXmlLocation, File webXmlLocation, File externalResourceDirectory, String sdkRelease, File applicationSchemaFile) {
      this.environmentVariableMismatchReportingPolicy = EnvironmentVariableChecker.MismatchReportingPolicy.EXCEPTION;
      this.configurationRoot = configurationRoot;
      this.systemPropertiesManager = new SystemPropertiesManager();
      this.sdkRelease = sdkRelease;
      this.applicationSchemaFile = applicationSchemaFile;
      if(EarHelper.isEar(configurationRoot.getAbsolutePath())) {
         EarInfo warConfigurationHandle = this.readEarConfiguration();
         ImmutableList.Builder builder = ImmutableList.builder();
         Iterator i$ = warConfigurationHandle.getWebModules().iterator();

         while(i$.hasNext()) {
            WebModule module = (WebModule)i$.next();
            builder.add((Object)(new ApplicationConfigurationManager.EarModuleConfigurationHandle(module)));
         }

         this.moduleConfigurationHandles = builder.build();
      } else {
         ApplicationConfigurationManager.WarModuleConfigurationHandle warConfigurationHandle1 = new ApplicationConfigurationManager.WarModuleConfigurationHandle(appEngineWebXmlLocation, webXmlLocation, externalResourceDirectory);
         warConfigurationHandle1.readConfiguration();
         this.moduleConfigurationHandles = ImmutableList.of(warConfigurationHandle1);
      }

   }

   private synchronized void validateAndRegisterGlobalValues(WebModule module, LoggingConfigurationManager loggingConfigurationManager, File externalResourceDirectory) {
      module.getWebXml().validate();
      AppEngineWebXml appEngineWebXml = module.getAppEngineWebXml();
      loggingConfigurationManager.read(this.systemPropertiesManager.getOriginalSystemProperties(), appEngineWebXml.getSystemProperties(), module.getApplicationDirectory(), externalResourceDirectory);
      this.systemPropertiesManager.setSystemProperties(appEngineWebXml, module.getAppEngineWebXmlFile());
   }

   private synchronized EarInfo readEarConfiguration() {
      if(!EarHelper.isEar(this.configurationRoot.getAbsolutePath())) {
         String earInfo1 = String.format("Unsupported update from EAR to WAR for: %s", new Object[]{this.configurationRoot.getAbsolutePath()});
         LOGGER.severe(earInfo1);
         throw new AppEngineConfigException(earInfo1);
      } else {
         EarInfo earInfo = EarHelper.readEarInfo(this.configurationRoot.getAbsolutePath(), this.applicationSchemaFile);
         String majorVersionId = null;
         String urlStreamHandlerType = null;
         LoggingConfigurationManager loggingConfigurationManager = new LoggingConfigurationManager();

         WebModule module;
         for(Iterator i$ = earInfo.getWebModules().iterator(); i$.hasNext(); this.validateAndRegisterGlobalValues(module, loggingConfigurationManager, (File)null)) {
            module = (WebModule)i$.next();
            module.getWebXml().validate();
            AppEngineWebXml appEngineWebXml = module.getAppEngineWebXml();
            if(majorVersionId == null) {
               majorVersionId = appEngineWebXml.getMajorVersionId();
               urlStreamHandlerType = appEngineWebXml.getUrlStreamHandlerType();
            }
         }

         this.systemPropertiesManager.setAppengineSystemProperties(this.sdkRelease, earInfo.getAppengineApplicationXml().getApplicationId(), majorVersionId);
         loggingConfigurationManager.updateLoggingConfiguration();
         this.updateUrlStreamHandlerMode(urlStreamHandlerType);
         return earInfo;
      }
   }

   private synchronized void checkEnvironmentVariables() {
      EnvironmentVariableChecker environmentVariableChecker = new EnvironmentVariableChecker(this.environmentVariableMismatchReportingPolicy);
      Iterator i$ = this.moduleConfigurationHandles.iterator();

      while(i$.hasNext()) {
         ApplicationConfigurationManager.ModuleConfigurationHandle moduleConfigurationHandle = (ApplicationConfigurationManager.ModuleConfigurationHandle)i$.next();
         WebModule module = moduleConfigurationHandle.getModule();
         environmentVariableChecker.add(module.getAppEngineWebXml(), module.getAppEngineWebXmlFile());
      }

      environmentVariableChecker.check();
   }

   synchronized void setEnvironmentVariableMismatchReportingPolicy(EnvironmentVariableChecker.MismatchReportingPolicy environmentVariableMismatchReportingPolicy) {
      this.environmentVariableMismatchReportingPolicy = environmentVariableMismatchReportingPolicy;
   }

   synchronized EnvironmentVariableChecker.MismatchReportingPolicy getEnvironmentVariableMismatchReportingPolicy() {
      return this.environmentVariableMismatchReportingPolicy;
   }

   private void updateUrlStreamHandlerMode(String urlStreamHandlerType) {
      LocalURLFetchServiceStreamHandler.setUseNativeHandlers(urlStreamHandlerType != null && "native".equals(urlStreamHandlerType));
   }

   public synchronized String toString() {
      return "ApplicationConfigurationManager: configurationRoot=" + this.configurationRoot + " systemPropertiesManager=" + this.systemPropertiesManager + " sdkVersion=" + this.sdkRelease + " environmentVariableMismatchReportingPolicy=" + this.environmentVariableMismatchReportingPolicy + " moduleConfigurationHandles=" + this.moduleConfigurationHandles;
   }

   private static void checkDynamicModuleUpdateAllowed(WebModule currentModule, WebModule updatedModule) throws AppEngineConfigException {
      checkServerNamesMatch(currentModule, updatedModule);
      checkScalingTypesMatch(currentModule, updatedModule);
      checkInstanceCountsMatch(currentModule, updatedModule);
   }

   private static void checkServerNamesMatch(WebModule currentModule, WebModule updatedModule) throws AppEngineConfigException {
      String currentModuleName = currentModule.getModuleName();
      String updatedModuleName = updatedModule.getModuleName();
      if(!currentModuleName.equals(updatedModuleName)) {
         String message = String.format("Unsupported configuration change of module name from \'%s\' to \'%s\' in \'%s\'", new Object[]{currentModuleName, updatedModuleName, currentModule.getAppEngineWebXmlFile()});
         LOGGER.severe(message);
         throw new AppEngineConfigException(message);
      }
   }

   private static void checkScalingTypesMatch(WebModule currentModule, WebModule updatedModule) throws AppEngineConfigException {
      AppEngineWebXml.ScalingType currentScalingType = currentModule.getAppEngineWebXml().getScalingType();
      AppEngineWebXml.ScalingType updatedScalingType = updatedModule.getAppEngineWebXml().getScalingType();
      if(!currentScalingType.equals(updatedScalingType)) {
         String message = String.format("Unsupported configuration change of scaling from \'%s\' to \'%s\' in \'%s\'", new Object[]{currentScalingType, updatedScalingType, currentModule.getAppEngineWebXmlFile()});
         LOGGER.severe(message);
         throw new AppEngineConfigException(message);
      }
   }

   private static void checkInstanceCountsMatch(WebModule currentModule, WebModule updatedModule) throws AppEngineConfigException {
      AppEngineWebXml.ScalingType currentScalingType = currentModule.getAppEngineWebXml().getScalingType();
      String currentBasicMaxInstances;
      String updatedBasicMaxInstances;
      switch(ApplicationConfigurationManager.SyntheticClass_1.$SwitchMap$com$google$apphosting$utils$config$AppEngineWebXml$ScalingType[currentScalingType.ordinal()]) {
      case 1:
         String currentManualInstances = currentModule.getAppEngineWebXml().getManualScaling().getInstances();
         String updatedManualInstances = updatedModule.getAppEngineWebXml().getManualScaling().getInstances();
         if(!Objects.equal(currentManualInstances, updatedManualInstances)) {
            currentBasicMaxInstances = "Unsupported configuration change of manual scaling instances from \'%s\' to \'%s\' in \'%s\'";
            updatedBasicMaxInstances = String.format(currentBasicMaxInstances, new Object[]{currentManualInstances, updatedManualInstances, currentModule.getAppEngineWebXmlFile()});
            LOGGER.severe(updatedBasicMaxInstances);
            throw new AppEngineConfigException(updatedBasicMaxInstances);
         }
         break;
      case 2:
         currentBasicMaxInstances = currentModule.getAppEngineWebXml().getBasicScaling().getMaxInstances();
         updatedBasicMaxInstances = updatedModule.getAppEngineWebXml().getBasicScaling().getMaxInstances();
         if(!Objects.equal(currentBasicMaxInstances, updatedBasicMaxInstances)) {
            String template = "Unsupported configuration change of basic scaling max instances from \'%s\' to \'%s\' in \'%s\'";
            String message = String.format(template, new Object[]{currentBasicMaxInstances, updatedBasicMaxInstances, currentModule.getAppEngineWebXmlFile()});
            LOGGER.severe(message);
         }
      }

   }

   // $FF: synthetic class
   static class SyntheticClass_1 {
      // $FF: synthetic field
      static final int[] $SwitchMap$com$google$apphosting$utils$config$AppEngineWebXml$ScalingType = new int[AppEngineWebXml.ScalingType.values().length];

      static {
         try {
            $SwitchMap$com$google$apphosting$utils$config$AppEngineWebXml$ScalingType[AppEngineWebXml.ScalingType.MANUAL.ordinal()] = 1;
         } catch (NoSuchFieldError var2) {
            ;
         }

         try {
            $SwitchMap$com$google$apphosting$utils$config$AppEngineWebXml$ScalingType[AppEngineWebXml.ScalingType.BASIC.ordinal()] = 2;
         } catch (NoSuchFieldError var1) {
            ;
         }

      }
   }

   private class EarModuleConfigurationHandle implements ApplicationConfigurationManager.ModuleConfigurationHandle {
      @GuardedBy("ApplicationConfigurationManager.this")
      private WebModule webModule;

      EarModuleConfigurationHandle(WebModule webModule) {
         this.webModule = webModule;
      }

      public WebModule getModule() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            return this.webModule;
         }
      }

      public void checkEnvironmentVariables() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            ApplicationConfigurationManager.this.checkEnvironmentVariables();
         }
      }

      public BackendsXml getBackendsXml() {
         return null;
      }

      public void readConfiguration() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            EarInfo earInfo = ApplicationConfigurationManager.this.readEarConfiguration();
            this.checkDynamicUpdateAllowed(earInfo);
            Iterator i$ = earInfo.getWebModules().iterator();

            WebModule module;
            do {
               if(!i$.hasNext()) {
                  throw new IllegalStateException("Expected web module not found.");
               }

               module = (WebModule)i$.next();
            } while(!module.getApplicationDirectory().equals(this.webModule.getApplicationDirectory()));

            this.webModule = module;
         }
      }

      private void checkDynamicUpdateAllowed(EarInfo updatedEarInfo) throws AppEngineConfigException {
         Map currentModuleMap = this.getCurrentModuleMap();
         Map updatedModuleMap = this.getUpdatedModuleMap(updatedEarInfo);
         this.checkWarDirectoriesMatch(currentModuleMap.keySet(), updatedModuleMap.keySet());
         Iterator i$ = currentModuleMap.keySet().iterator();

         while(i$.hasNext()) {
            File currentWarFile = (File)i$.next();
            WebModule currentModule = (WebModule)currentModuleMap.get(currentWarFile);
            WebModule updatedModule = (WebModule)updatedModuleMap.get(currentWarFile);
            ApplicationConfigurationManager.checkDynamicModuleUpdateAllowed(currentModule, updatedModule);
         }

      }

      private Map getCurrentModuleMap() {
         ImmutableSortedMap.Builder currentModuleMapBuilder = ImmutableSortedMap.naturalOrder();
         Iterator i$ = ApplicationConfigurationManager.this.moduleConfigurationHandles.iterator();

         while(i$.hasNext()) {
            ApplicationConfigurationManager.ModuleConfigurationHandle handle = (ApplicationConfigurationManager.ModuleConfigurationHandle)i$.next();
            currentModuleMapBuilder.put(handle.getModule().getApplicationDirectory(), handle.getModule());
         }

         return currentModuleMapBuilder.build();
      }

      private Map getUpdatedModuleMap(EarInfo earInfo) {
         ImmutableSortedMap.Builder updatedModuleMapBuilder = ImmutableSortedMap.naturalOrder();
         Iterator i$ = earInfo.getWebModules().iterator();

         while(i$.hasNext()) {
            WebModule module = (WebModule)i$.next();
            updatedModuleMapBuilder.put(module.getApplicationDirectory(), module);
         }

         return updatedModuleMapBuilder.build();
      }

      private void checkWarDirectoriesMatch(Set currentWarDirectories, Set updatedWarDirectories) {
         if(!currentWarDirectories.equals(updatedWarDirectories)) {
            String message = String.format("Unsupported configuration change of war directories from \'%s\' to \'%s\'", new Object[]{currentWarDirectories, updatedWarDirectories});
            ApplicationConfigurationManager.LOGGER.severe(message);
            throw new AppEngineConfigException(message);
         }
      }

      public void restoreSystemProperties() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            ApplicationConfigurationManager.this.systemPropertiesManager.restoreSystemProperties();
         }
      }

      public String toString() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            return "WarConfigurationHandle: webModule=" + this.webModule;
         }
      }
   }

   private class WarModuleConfigurationHandle implements ApplicationConfigurationManager.ModuleConfigurationHandle {
      private final File rawAppEngineWebXmlLocation;
      private final File rawWebXmlLocation;
      private final File externalResourceDirectory;
      @GuardedBy("ApplicationConfigurationManager.this")
      private BackendsXml backendsXml;
      @GuardedBy("ApplicationConfigurationManager.this")
      private WebModule webModule;

      WarModuleConfigurationHandle(File appEngineWebXmlLocation, File webXmlLocation, File externalResourceDirectory) {
         this.rawAppEngineWebXmlLocation = appEngineWebXmlLocation;
         this.rawWebXmlLocation = webXmlLocation;
         this.externalResourceDirectory = externalResourceDirectory;
      }

      public WebModule getModule() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            return this.webModule;
         }
      }

      public void checkEnvironmentVariables() {
         ApplicationConfigurationManager.this.checkEnvironmentVariables();
      }

      public BackendsXml getBackendsXml() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            return this.backendsXml;
         }
      }

      public void readConfiguration() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            if(EarHelper.isEar(ApplicationConfigurationManager.this.configurationRoot.getAbsolutePath())) {
               String updatedWebModule1 = String.format("Unsupported update from WAR to EAR for: %s", new Object[]{ApplicationConfigurationManager.this.configurationRoot.getAbsolutePath()});
               ApplicationConfigurationManager.LOGGER.severe(updatedWebModule1);
               throw new AppEngineConfigException(updatedWebModule1);
            } else {
               WebModule updatedWebModule = EarHelper.readWebModule((String)null, ApplicationConfigurationManager.this.configurationRoot, this.rawAppEngineWebXmlLocation, this.rawWebXmlLocation);
               if(this.webModule != null) {
                  ApplicationConfigurationManager.checkDynamicModuleUpdateAllowed(this.webModule, updatedWebModule);
               }

               this.webModule = updatedWebModule;
               String baseDir = ApplicationConfigurationManager.this.configurationRoot.getAbsolutePath();
               File webinf = new File(baseDir, "WEB-INF");
               this.backendsXml = (new BackendsXmlReader(baseDir)).readBackendsXml();
               if(this.backendsXml == null) {
                  BackendsYamlReader appEngineWebXml = new BackendsYamlReader(webinf.getPath());
                  this.backendsXml = appEngineWebXml.parse();
               }

               AppEngineWebXml appEngineWebXml1 = this.webModule.getAppEngineWebXml();
               if(appEngineWebXml1.getAppId() == null || appEngineWebXml1.getAppId().length() == 0) {
                  appEngineWebXml1.setAppId("no_app_id");
               }
               // AppScale: Ensure that each module has only one version.
               appEngineWebXml1.setMajorVersionId("1");

               LoggingConfigurationManager loggingConfigurationManager = new LoggingConfigurationManager();
               ApplicationConfigurationManager.this.validateAndRegisterGlobalValues(this.webModule, loggingConfigurationManager, this.externalResourceDirectory);
               ApplicationConfigurationManager.this.systemPropertiesManager.setAppengineSystemProperties(ApplicationConfigurationManager.this.sdkRelease, appEngineWebXml1.getAppId(), appEngineWebXml1.getMajorVersionId());
               loggingConfigurationManager.updateLoggingConfiguration();
               ApplicationConfigurationManager.this.updateUrlStreamHandlerMode(appEngineWebXml1.getUrlStreamHandlerType());
            }
         }
      }

      public void restoreSystemProperties() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            ApplicationConfigurationManager.this.systemPropertiesManager.restoreSystemProperties();
         }
      }

      public String toString() {
         ApplicationConfigurationManager var1 = ApplicationConfigurationManager.this;
         synchronized(ApplicationConfigurationManager.this) {
            return "WarConfigurationHandle: webModule=" + this.webModule + " backendsXml=" + this.backendsXml + " appEngineWebXmlLocation=" + this.rawAppEngineWebXmlLocation + " webXmlLocation=" + this.rawWebXmlLocation + " externalResourceDirectory=" + this.externalResourceDirectory;
         }
      }
   }

   interface ModuleConfigurationHandle {
      WebModule getModule();

      void checkEnvironmentVariables();

      BackendsXml getBackendsXml();

      void readConfiguration() throws AppEngineConfigException;

      void restoreSystemProperties();
   }
}
