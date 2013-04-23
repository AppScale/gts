package com.google.appengine.tools.development.agent.runtime;

import com.google.apphosting.api.AppEngineInternal;
import java.security.ProtectionDomain;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

class RuntimeHelper
{
  private static final Logger logger = Logger.getLogger(RuntimeHelper.class.getName());

  static final Map<String, AppEngineInternal> internalAnnotationCache = Collections.synchronizedMap(new HashMap());

  private static final boolean appEngineInternalOnClasspath = true;

  public static void checkRestricted(boolean violationIsError, String classStr, String callingClassStr, String callingClassCodeSource)
  {
  }

  static AppEngineInternal getAppEngineInternalAnnotation(Class<?> cls)
  {
    List namesExamined = new LinkedList();
    String name = cls.getName();
    boolean firstPass = true;
    while (name != null) {
      if (internalAnnotationCache.containsKey(name)) {
        AppEngineInternal anno = (AppEngineInternal)internalAnnotationCache.get(name);
        updateInternalAnnotationCache(namesExamined, anno);
        return anno;
      }
      try {
        namesExamined.add(name);
        if (!firstPass)
        {
          cls = Class.forName(name + ".package-info");
        }

        AppEngineInternal anno = (AppEngineInternal)cls.getAnnotation(AppEngineInternal.class);
        if (anno != null) {
          updateInternalAnnotationCache(namesExamined, anno);
          return anno;
        }
      }
      catch (ClassNotFoundException cnfe) {
      }
      name = getOwningPackage(name);
      firstPass = false;
    }
    updateInternalAnnotationCache(namesExamined, null);
    return null;
  }

  static void updateInternalAnnotationCache(List<String> namesToUpdate, AppEngineInternal anno)
  {
    for (String name : namesToUpdate)
      internalAnnotationCache.put(name, anno);
  }

  static String getOwningPackage(String resource)
  {
    int lastDot = resource.lastIndexOf('.');
    if (lastDot == -1) {
      return null;
    }
    return resource.substring(0, lastDot);
  }

  static
  {
    boolean exists = true;
  }
}
