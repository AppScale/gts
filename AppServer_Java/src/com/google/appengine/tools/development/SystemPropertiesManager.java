package com.google.appengine.tools.development;

import com.google.appengine.api.utils.SystemProperty;
import com.google.appengine.api.utils.SystemProperty.Environment;
import com.google.appengine.api.utils.SystemProperty.Environment.Value;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.AppEngineWebXml;
import java.io.File;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Properties;
import java.util.Set;
import java.util.logging.Logger;

public class SystemPropertiesManager
{
  private static final Logger LOGGER = Logger.getLogger(SystemPropertiesManager.class.getName());

  private final Map<String, File> propertyNameToFileMap;

  private final Properties originalSystemProperties;

  SystemPropertiesManager()
  {
    this.propertyNameToFileMap = new HashMap();
    this.originalSystemProperties = new Properties();
    this.originalSystemProperties.putAll(System.getProperties());
  }

  Properties getOriginalSystemProperties() {
    Properties result = new Properties();
    result.putAll(this.originalSystemProperties);
    return result;
  }

  public void setAppengineSystemProperties(String release, String applicationId, String majorVersionId)
  {
    SystemProperty.environment.set(SystemProperty.Environment.Value.Production);
    if (release == null)
    {
      release = "null";
    }
    SystemProperty.version.set(release);
    SystemProperty.applicationId.set(applicationId);
    SystemProperty.applicationVersion.set(majorVersionId + ".1");
  }

  public synchronized void setSystemProperties(AppEngineWebXml appEngineWebXml, File appengineWebXmlFile) throws AppEngineConfigException
  {
    Map originalSystemProperties = copySystemProperties();

    for (Map.Entry entry : appEngineWebXml.getSystemProperties().entrySet()) {
      if ((this.propertyNameToFileMap.containsKey(entry.getKey())) && (!((String)entry.getValue()).equals(System.getProperty((String)entry.getKey()))) && (!((File)this.propertyNameToFileMap.get(entry.getKey())).equals(appengineWebXmlFile)))
      {
        String template = "Property %s is defined in %s and in %s with different values. Currently Java Development Server requires matching values.";

        String message = String.format(template, new Object[] { entry.getKey(), appengineWebXmlFile.getAbsolutePath(), this.propertyNameToFileMap.get(entry.getKey()) });

        LOGGER.severe(message);
        throw new AppEngineConfigException(message);
      }
      if (originalSystemProperties.containsKey(entry.getKey())) {
        String message = String.format("Overwriting system property key '%s', value '%s' with value '%s' from '%s'", new Object[] { entry.getKey(), originalSystemProperties.get(entry.getKey()), entry.getValue(), appengineWebXmlFile.getAbsolutePath() });

        LOGGER.info(message);
      }

    }

    Iterator iterator = this.propertyNameToFileMap.entrySet().iterator();

    while (iterator.hasNext()) {
      Map.Entry entry = (Map.Entry)iterator.next();
      if (((File)entry.getValue()).equals(appengineWebXmlFile.getAbsolutePath())) {
        iterator.remove();
      }
    }

    for (Map.Entry entry : appEngineWebXml.getSystemProperties().entrySet()) {
      this.propertyNameToFileMap.put((String)entry.getKey(), appengineWebXmlFile);
    }
    System.getProperties().putAll(appEngineWebXml.getSystemProperties());
  }

  public synchronized void restoreSystemProperties()
  {
    for (String key : this.propertyNameToFileMap.keySet()) {
      System.clearProperty(key);
    }

    this.propertyNameToFileMap.clear();

    System.getProperties().putAll(this.originalSystemProperties);
  }

  static Map<String, String> copySystemProperties()
  {
    HashMap copy = new HashMap();
    for (String key : System.getProperties().stringPropertyNames()) {
      copy.put(key, System.getProperties().getProperty(key));
    }
    return copy;
  }
}

