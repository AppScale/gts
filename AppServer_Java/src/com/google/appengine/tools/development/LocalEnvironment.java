package com.google.appengine.tools.development;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.utils.config.AppEngineWebXml;

public abstract class LocalEnvironment
  implements ApiProxy.Environment
{
//  private static final Logger logger = Logger.getLogger(LocalEnvironment.class.getName());
//  private static final String REQUEST_NAMESPACE = "";
  static final String API_CALL_SEMAPHORE = "com.google.appengine.tools.development.api_call_semaphore";
  private final AppEngineWebXml appEngineWebXml;
  protected final ConcurrentMap<String, Object> attributes = new ConcurrentHashMap<String, Object>();

  protected LocalEnvironment(AppEngineWebXml appEngineWebXml)
  {
    this.appEngineWebXml = appEngineWebXml;
  }

  public String getAppId() {
    return this.appEngineWebXml.getAppId();
  }

  public String getVersionId()
  {
    return this.appEngineWebXml.getMajorVersionId() + ".1";
  }

  public String getAuthDomain()
  {
    return "gmail.com";
  }

  public String getRequestNamespace() {
    return "";
  }

  public ConcurrentMap<String, Object> getAttributes() {
    return this.attributes;
  }
}