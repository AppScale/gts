package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;
import com.google.appengine.repackaged.com.google.common.base.Joiner;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.tools.util.Logging;
import com.google.appengine.tools.util.Option;
import java.awt.Toolkit;
import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.TimeZone;

public abstract class SharedMain {
    private static String originalTimeZone;
    private boolean disableRestrictedCheck = false;
    private boolean noJavaAgent = false;
    private String pathToPythonApiServer = null;
    private List<String> apisUsingPythonStubs = null;
    private String externalResourceDir = null;
    private List<String> propertyOptions = null;
    private List pythonApiServerFlags = null;

    protected List<Option> getSharedOptions() {
        return Arrays.asList(new Option("h", "help", true) {
            public void apply() {
                SharedMain.this.printHelp(System.err);
                System.exit(0);
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --help, -h                 Show this help message and exit.");
            }
        }, new Option((String)null, "sdk_root", false) {
            public void apply() {
                System.setProperty("appengine.sdk.root", this.getValue());
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --sdk_root=DIR             Overrides where the SDK is located.");
            }
        }, new Option((String)null, "disable_restricted_check", true) {
            public void apply() {
                SharedMain.this.disableRestrictedCheck = true;
            }
        }, new Option((String)null, "external_resource_dir", false) {
            public void apply() {
                SharedMain.this.externalResourceDir = this.getValue();
            }
        }, new Option((String)null, "property", false) {
            public void apply() {
                SharedMain.this.propertyOptions = this.getValues();
            }
        }, new Option((String)null, "allow_remote_shutdown", true) {
            public void apply() {
                System.setProperty("appengine.allowRemoteShutdown", "true");
            }
        }, new Option((String)null, "api_using_python_stub", false) {
            public void apply() {
                SharedMain.this.apisUsingPythonStubs = this.getValues();
                if (!SharedMain.this.apisUsingPythonStubs.isEmpty()) {
                    System.setProperty("appengine.apisUsingPythonStubs", Joiner.on(',').join((Iterable)SharedMain.this.apisUsingPythonStubs));
                }

            }
        }, new Option((String)null, "path_to_python_api_server", false) {
            public void apply() {
                SharedMain.this.pathToPythonApiServer = this.getValue();
                System.setProperty("appengine.pathToPythonApiServer", SharedMain.this.pathToPythonApiServer);
            }
        }, new Option((String)null, "no_java_agent", true) {
            public void apply() {
                SharedMain.this.noJavaAgent = true;
            }
        }, new Option((String)null, "python_api_server_flag", false) {
            public void apply() {
                SharedMain.this.pythonApiServerFlags = this.getValues();
                if (!SharedMain.this.pythonApiServerFlags.isEmpty()) {
                    System.setProperty("appengine.pythonApiServerFlags", Joiner.on('|').join((Iterable)SharedMain.this.pythonApiServerFlags));
                }

            }
        });
    }

    protected static void sharedInit() {
        recordTimeZone();
        Logging.initializeLogging();
        if (System.getProperty("os.name").equalsIgnoreCase("Mac OS X")) {
            Toolkit.getDefaultToolkit();
        }

    }

    private static void recordTimeZone() {
        originalTimeZone = System.getProperty("user.timezone");
    }

    protected abstract void printHelp(PrintStream var1);

    protected void postServerActions(Map<String, String> stringProperties) {
        this.setTimeZone(stringProperties);
        if (this.disableRestrictedCheck) {
            stringProperties.put("appengine.disableRestrictedCheck", "");
        }

    }

    protected void addPropertyOptionToProperties(Map<String, String> properties) {
        properties.putAll(parsePropertiesList(this.propertyOptions));
    }

    protected Map<String, String> getSystemProperties() {
        Properties properties = System.getProperties();
        Map<String, String> stringProperties = new HashMap();
        Iterator i$ = properties.stringPropertyNames().iterator();

        while(i$.hasNext()) {
            String property = (String)i$.next();
            stringProperties.put(property, properties.getProperty(property));
        }

        return stringProperties;
    }

    private void setTimeZone(Map<String, String> serviceProperties) {
        String timeZone = (String)serviceProperties.get("appengine.user.timezone");
        if (timeZone != null) {
            TimeZone.setDefault(TimeZone.getTimeZone(timeZone));
        } else {
            timeZone = originalTimeZone;
        }

        serviceProperties.put("appengine.user.timezone.impl", timeZone);
    }

    protected File getExternalResourceDir() {
        if (this.externalResourceDir == null) {
            return null;
        } else {
            this.externalResourceDir = this.externalResourceDir.trim();
            String error = null;
            File dir = null;
            if (this.externalResourceDir.isEmpty()) {
                error = "The empty string was specified for external_resource_dir";
            } else {
                dir = new File(this.externalResourceDir);
                if (dir.exists()) {
                    if (!dir.isDirectory()) {
                        error = this.externalResourceDir + " is not a directory.";
                    }
                } else {
                    error = "No such directory: " + this.externalResourceDir;
                }
            }

            if (error != null) {
                System.err.println(error);
                System.exit(1);
            }

            return dir;
        }
    }

    public void validateWarPath(File war) {
        if (!war.exists()) {
            System.out.println("Unable to find the webapp directory " + war);
            this.printHelp(System.err);
            System.exit(1);
        } else if (!war.isDirectory()) {
            System.out.println("dev_appserver only accepts webapp directories, not war files.");
            this.printHelp(System.err);
            System.exit(1);
        }

    }

    @VisibleForTesting
    static Map<String, String> parsePropertiesList(List<String> properties) {
        Map<String, String> parsedProperties = new HashMap();
        if (properties != null) {
            Iterator i$ = properties.iterator();

            while(i$.hasNext()) {
                String property = (String)i$.next();
                String[] propertyKeyValue = property.split("=", 2);
                if (propertyKeyValue.length == 2) {
                    parsedProperties.put(propertyKeyValue[0], propertyKeyValue[1]);
                } else if (propertyKeyValue[0].startsWith("no")) {
                    parsedProperties.put(propertyKeyValue[0].substring(2), "false");
                } else {
                    parsedProperties.put(propertyKeyValue[0], "true");
                }
            }
        }

        return parsedProperties;
    }

    protected boolean getNoJavaAgent() {
        return this.noJavaAgent;
    }
}
