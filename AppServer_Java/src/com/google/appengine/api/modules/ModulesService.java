package com.google.appengine.api.modules;

import java.util.Set;
import java.util.concurrent.Future;

/**
 * User: uglitskih
 * Date: 27.10.16
 * Time: 15:29
 */
public interface ModulesService {
    String getCurrentModule();

    String getCurrentVersion();

    String getCurrentInstanceId();

    Set<String> getModules();

    Set<String> getVersions(String var1);

    String getDefaultVersion(String var1);

    int getNumInstances(String var1, String var2);

    void setNumInstances(String var1, String var2, long var3);

    Future<Void> setNumInstancesAsync(String var1, String var2, long var3);

    void startVersion(String var1, String var2);

    Future<Void> startVersionAsync(String var1, String var2);

    void stopVersion(String var1, String var2);

    Future<Void> stopVersionAsync(String var1, String var2);

    String getVersionHostname(String var1, String var2);

    String getInstanceHostname(String var1, String var2, String var3);
}
