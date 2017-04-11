package com.google.appengine.api.modules;

import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.concurrent.Future;
import java.util.logging.Logger;

/**
 * User: uglitskih
 * Date: 27.10.16
 * Time: 15:31
 */
public final class ModulesServiceImpl implements ModulesService {

    private static Map<String, String> modulePorts = new HashMap<String, String>();
    private static Set<String> moduleNames = new HashSet<String>();
    private static Properties properties = new Properties();

    {
        final Logger logger = Logger.getLogger(ModulesService.class.getName());
        final InputStream inputStream = Thread.currentThread().getContextClassLoader().getResourceAsStream("modules.properties");
        if (inputStream != null) {
            try {
                properties.load(inputStream);
            } catch (IOException e) {
                logger.severe(e.getMessage());
            }
            final String masterHostName = properties.getProperty("appscale.master.hostname");
            for (Object key : properties.keySet()) {
                if (key instanceof String
                        && ((String) key).startsWith("module.")) {
                    final String moduleName = ((String) key).substring("module.".length());
                    moduleNames.add(moduleName);
                    modulePorts.put(moduleName, masterHostName + ":" + properties.getProperty((String) key));
                }
            }
        } else {
            logger.warning("Cannot find file modules.properties");
        }
    }

    public String getCurrentModule() {
        return properties.getProperty("current.module.name");
    }

    public String getCurrentVersion() {
        return "v1";
    }

    public String getCurrentInstanceId() {
        return null;
    }

    public Set<String> getModules() {
        return moduleNames;
    }

    public Set<String> getVersions(final String var1) {
        final Set<String> out = new HashSet<String>();
        out.add("v1");
        return out;
    }

    public String getDefaultVersion(final String var1) {
        return "v1";
    }

    public int getNumInstances(final String var1, final String var2) {
        throw new UnsupportedOperationException();
    }

    public void setNumInstances(final String var1, final String var2, final long var3) {
        throw new UnsupportedOperationException();
    }

    public Future<Void> setNumInstancesAsync(final String var1, final String var2, final long var3) {
        throw new UnsupportedOperationException();
    }

    public void startVersion(final String var1, final String var2) {
        throw new UnsupportedOperationException();
    }

    public Future<Void> startVersionAsync(final String var1, final String var2) {
        throw new UnsupportedOperationException();
    }

    public void stopVersion(final String var1, final String var2) {
        throw new UnsupportedOperationException();
    }

    public Future<Void> stopVersionAsync(final String var1, final String var2) {
        throw new UnsupportedOperationException();
    }

    public String getVersionHostname(final String var1, final String var2) {
        return modulePorts.get(var1);
    }

    public String getInstanceHostname(final String var1, final String var2, final String var3) {
        return null;
    }
}
