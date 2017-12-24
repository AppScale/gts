package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.tools.info.SdkInfo;
import com.google.appengine.tools.info.UpdateCheck;
import com.google.appengine.tools.plugins.SDKPluginManager;
import com.google.appengine.tools.plugins.SDKRuntimePlugin;
import com.google.appengine.tools.plugins.SDKRuntimePlugin.ApplicationDirectories;
import com.google.appengine.tools.util.Action;
import com.google.appengine.tools.util.Logging;
import com.google.appengine.tools.util.Option;
import com.google.appengine.tools.util.Parser;
import com.google.appengine.tools.util.Parser.ParseResult;
import java.awt.Toolkit;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.PrintStream;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TimeZone;

public class DevAppServerMain {
    public static final String EXTERNAL_RESOURCE_DIR_ARG = "external_resource_dir";
    public static final String GENERATE_WAR_ARG = "generate_war";
    public static final String GENERATED_WAR_DIR_ARG = "generated_war_dir";
    private static final String DEFAULT_RDBMS_PROPERTIES_FILE = ".local.rdbms.properties";
    private static final String RDBMS_PROPERTIES_FILE_SYSTEM_PROPERTY = "rdbms.properties.file";
    private static final String SYSTEM_PROPERTY_STATIC_MODULE_PORT_NUM_PREFIX = "com.google.appengine.devappserver_module.";
    private static String originalTimeZone;
    private final Action ACTION = new DevAppServerMain.StartAction();
    private String versionCheckServer = SdkInfo.getDefaultServer();
    private String address = "127.0.0.1";
    private int port = 8080;
    private boolean disableUpdateCheck;
    private String generatedDirectory = null;
    private String defaultGcsBucketName = null;
    private boolean disableRestrictedCheck = true;
    private boolean noJavaAgent = false;
    private String externalResourceDir = null;
    private List<String> propertyOptions = null;
    private final List<Option> PARSERS = buildOptions(this);

    // add for AppScale
    private String db_location;
    private String login_server;
    private String cookie;
    private String appscale_version;
    private String admin_console_version;
    private static final String SECRET_LOCATION = "/etc/appscale/secret.key";

    private static List<Option> getBuiltInOptions(DevAppServerMain main) {
        return Arrays.asList(new Option("h", "help", true) {
            public void apply() {
                DevAppServerMain.printHelp(System.err);
                System.exit(0);
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --help, -h                 Show this help message and exit.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, "s", "server", false) {
            public void apply() {
                this.main.versionCheckServer = this.getValue();
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --server=SERVER            The server to use to determine the latest", "  -s SERVER                   SDK version.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, "a", "address", false) {
            public void apply() {
                this.main.address = this.getValue();
                System.setProperty("MY_IP_ADDRESS", this.main.address);
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --address=ADDRESS          The address of the interface on the local machine", "  -a ADDRESS                  to bind to (or 0.0.0.0 for all interfaces).");
            }
        }, new DevAppServerMain.DevAppServerOption(main, "p", "port", false) {
            public void apply() {
                this.main.port = Integer.valueOf(this.getValue());
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --port=PORT                The port number to bind to on the local machine.", "  -p PORT");
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "sdk_root", false) {
            public void apply() {
                System.setProperty("appengine.sdk.root", this.getValue());
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --sdk_root=DIR             Overrides where the SDK is located.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "disable_update_check", true) {
            public void apply() {
                this.main.disableUpdateCheck = true;
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --disable_update_check     Disable the check for newer SDK versions.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "generated_dir", false) {
            public void apply() {
                this.main.generatedDirectory = this.getValue();
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --generated_dir=DIR        Set the directory where generated files are created.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "default_gcs_bucket", false) {
            @Override
            public void apply() {
                this.main.defaultGcsBucketName = this.getValue();
            }

            @Override
            public List<String> getHelpLines() {
                return ImmutableList.of(" --default_gcs_bucket=NAME  Set the default Google Cloud Storage bucket name.");
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "disable_restricted_check", true) {
            public void apply() {
                this.main.disableRestrictedCheck = true;
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "external_resource_dir", false) {
            public void apply() {
                this.main.externalResourceDir = this.getValue();
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "property", false) {
            public void apply() {
                this.main.propertyOptions = this.getValues();
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "allow_remote_shutdown", true) {
            public void apply() {
                System.setProperty("appengine.allowRemoteShutdown", Boolean.TRUE.toString());
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "instance_port", false) {
            @Override
            public void apply() {
                DevAppServerMain.processInstancePorts(this.getValues());
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "no_java_agent", true) {
            @Override
            public void apply() {
                this.main.noJavaAgent = true;
            }
        },
        /*
         * AppScale added all of the below to end of list
         */
        new DevAppServerMain.DevAppServerOption(main, (String)null, "datastore_path", false) {
            public void apply() {
                this.main.db_location = this.getValue();
                System.setProperty("DB_LOCATION", this.main.db_location);
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "login_server", false) {
            public void apply() {
                this.main.login_server = this.getValue();
                System.setProperty("LOGIN_SERVER", this.main.login_server);
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "appscale_version", false) {
            public void apply() {
                this.main.appscale_version = this.getValue();
                System.setProperty("APP_SCALE_VERSION", this.main.appscale_version);
            }
        },
        // changed from admin_console_server
        new DevAppServerMain.DevAppServerOption(main,(String)null, "admin_console_version", false) {
            public void apply() {
                this.main.admin_console_version = this.getValue();
                System.setProperty("ADMIN_CONSOLE_VERSION", this.main.admin_console_version);
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "APP_NAME", false) {
            public void apply() {
                System.setProperty("APP_NAME", this.getValue());
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "NGINX_ADDRESS", false) {
            public void apply() {
                System.setProperty("NGINX_ADDR", this.getValue());
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "TQ_PROXY", false) {
            public void apply() {
                System.setProperty("TQ_PROXY", this.getValue());
            }
        }, new DevAppServerMain.DevAppServerOption(main, (String)null, "pidfile", false) {
            public void apply() {
                System.setProperty("PIDFILE", this.getValue());
            }
        });
    }

    private static void processInstancePorts(List<String> optionValues) {
        for (String optionValue : optionValues) {
            String[] keyAndValue = optionValue.split("=", 2);
            if (keyAndValue.length != 2) {
                reportBadInstancePortValue(optionValue);
            }

            try {
                Integer.parseInt(keyAndValue[1]);
            } catch (NumberFormatException nfe) {
                reportBadInstancePortValue(optionValue);
            }

            System.setProperty(
                SYSTEM_PROPERTY_STATIC_MODULE_PORT_NUM_PREFIX + keyAndValue[0].trim() + ".port",
                keyAndValue[1].trim());
        }

    }

    private static void reportBadInstancePortValue(String optionValue) {
        throw new IllegalArgumentException("Invalid instance_port value " + optionValue);
    }

    private static List<Option> buildOptions(DevAppServerMain main) {
        List<Option> options = getBuiltInOptions(main);
        for (SDKRuntimePlugin runtimePlugin : SDKPluginManager.findAllRuntimePlugins()) {
            options = runtimePlugin.customizeDevAppServerOptions(options);
        }

        return options;
    }

    public static void main(String[] args) throws Exception {
        recordTimeZone();
        Logging.initializeLogging();
        if (System.getProperty("os.name").equalsIgnoreCase("Mac OS X")) {
            Toolkit.getDefaultToolkit();
        }

        new DevAppServerMain(args);
    }

    private static void recordTimeZone() {
        originalTimeZone = System.getProperty("user.timezone");
    }

    public DevAppServerMain(String[] args) throws Exception {
        Parser parser = new Parser();
        ParseResult result = parser.parseArgs(this.ACTION, this.PARSERS, args);
        result.applyArgs();
    }

    public static void printHelp(PrintStream out) {
        out.println("Usage: <dev-appserver> [options] <app directory>");
        out.println("");
        out.println("Options:");
        for (Option option : buildOptions(null)) {
            for (String helpString : option.getHelpLines()) {
                out.println(helpString);
            }
        }

        out.println(" --jvm_flag=FLAG            Pass FLAG as a JVM argument. May be repeated to");
        out.println("                              supply multiple flags.");
    }

    public static void validateWarPath(File war) {
        if (!war.exists()) {
            System.out.println("Unable to find the webapp directory " + war);
            printHelp(System.err);
            System.exit(1);
        } else if (!war.isDirectory()) {
            System.out.println("dev_appserver only accepts webapp directories, not war files.");
            printHelp(System.err);
            System.exit(1);
        }

    }

    @VisibleForTesting
    static Map<String, String> parsePropertiesList(List<String> properties) {
        Map<String, String> parsedProperties = new HashMap();
        if (properties != null) {
            for (String property : properties) {
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

    class StartAction extends Action {
        StartAction() {
            super();
        }

        public void apply() {
            List args = this.getArgs();

            try {
                File externalResourceDir = this.getExternalResourceDir();
                if (args.size() != 1) {
                    DevAppServerMain.printHelp(System.err);
                    System.exit(1);
                }

                File appDir = (new File((String)args.get(0))).getCanonicalFile();
                DevAppServerMain.validateWarPath(appDir);
                SDKRuntimePlugin runtimePlugin = SDKPluginManager.findRuntimePlugin(appDir);
                if (runtimePlugin != null) {
                    ApplicationDirectories appDirs = runtimePlugin.generateApplicationDirectories(appDir);
                    appDir = appDirs.getWarDir();
                    externalResourceDir = appDirs.getExternalResourceDir();
                }

                UpdateCheck updateCheck = new UpdateCheck(DevAppServerMain.this.versionCheckServer, appDir, true);
                if (updateCheck.allowedToCheckForUpdates() && !DevAppServerMain.this.disableUpdateCheck) {
                    updateCheck.maybePrintNagScreen(System.err);
                }

                updateCheck.checkJavaVersion(System.err);

                // AppScale: Write a pidfile for Monit.
                String pidfile = System.getProperty("PIDFILE");
                if (pidfile != null) {
                    String pidString = ManagementFactory.getRuntimeMXBean().getName().split("@")[0];
                    Path file = Paths.get(pidfile);
                    Files.write(file, pidString.getBytes());
                }

                DevAppServer server = (new DevAppServerFactory()).createDevAppServer(appDir, externalResourceDir, DevAppServerMain.this.address, DevAppServerMain.this.port, DevAppServerMain.this.noJavaAgent);
                Map properties = System.getProperties();
                this.setTimeZone(properties);
                this.setGeneratedDirectory(properties);
                this.setDefaultGcsBucketName(properties);

                // AppScale: Fetch and cache deployment secret.
                setSecret();

                if (DevAppServerMain.this.disableRestrictedCheck) {
                    properties.put("appengine.disableRestrictedCheck", "");
                }

                this.setRdbmsPropertiesFile(properties, appDir, externalResourceDir);
                properties.putAll(DevAppServerMain.parsePropertiesList(DevAppServerMain.this.propertyOptions));
                server.setServiceProperties(properties);

                try {
                    server.start().await();
                } catch (InterruptedException var10) {
                    ;
                }

                System.out.println("Shutting down.");
                System.exit(0);
            } catch (Exception ex) {
                ex.printStackTrace();
                System.exit(1);
            }

        }

        // Set the AppScale secret.
        private void setSecret() {
            BufferedReader bufferReader = null;
            try {
                bufferReader = new BufferedReader(new FileReader(SECRET_LOCATION));
                String value = bufferReader.readLine();
                System.setProperty("COOKIE_SECRET", value);
            }
            catch(IOException e) {
               System.out.println("IOException getting port from secret key file.");
               e.printStackTrace(); 
            }        
            finally {
               try {
                   if (bufferReader != null) bufferReader.close();
               } 
               catch (IOException ex) {
                   ex.printStackTrace();
               }
            }
        }

        private void setTimeZone(Map<String, String> serviceProperties) {
            String timeZone = (String)serviceProperties.get("appengine.user.timezone");
            if (timeZone != null) {
                TimeZone.setDefault(TimeZone.getTimeZone(timeZone));
            } else {
                timeZone = DevAppServerMain.originalTimeZone;
            }

            serviceProperties.put("appengine.user.timezone.impl", timeZone);
        }

        private void setGeneratedDirectory(Map<String, String> stringProperties) {
            if (DevAppServerMain.this.generatedDirectory != null) {
                File dir = new File(DevAppServerMain.this.generatedDirectory);
                String error = null;
                if (dir.exists()) {
                    if (!dir.isDirectory()) {
                        error = DevAppServerMain.this.generatedDirectory + " is not a directory.";
                    } else if (!dir.canWrite()) {
                        error = DevAppServerMain.this.generatedDirectory + " is not writable.";
                    }
                } else if (!dir.mkdirs()) {
                    error = "Could not make " + DevAppServerMain.this.generatedDirectory;
                }

                if (error != null) {
                    System.err.println(error);
                    System.exit(1);
                }

                stringProperties.put("appengine.generated.dir", DevAppServerMain.this.generatedDirectory);
            }

        }

        private void setDefaultGcsBucketName(Map<String, String> stringProperties) {
            if (DevAppServerMain.this.defaultGcsBucketName != null) {
                stringProperties.put("appengine.default.gcs.bucket.name", DevAppServerMain.this.defaultGcsBucketName);
            }

        }

        private void setRdbmsPropertiesFile(Map<String, String> stringProperties, File appDir, File externalResourceDir) {
            if (stringProperties.get("rdbms.properties.file") == null) {
                File file = this.findRdbmsPropertiesFile(externalResourceDir);
                if (file == null) {
                    file = this.findRdbmsPropertiesFile(appDir);
                }

                if (file != null) {
                    String path = file.getPath();
                    System.out.println("Reading local rdbms properties from " + path);
                    stringProperties.put("rdbms.properties.file", path);
                }

            }
        }

        private File findRdbmsPropertiesFile(File dir) {
            File candidate = new File(dir, ".local.rdbms.properties");
            return candidate.isFile() && candidate.canRead() ? candidate : null;
        }

        private File getExternalResourceDir() {
            if (DevAppServerMain.this.externalResourceDir == null) {
                return null;
            } else {
                DevAppServerMain.this.externalResourceDir = DevAppServerMain.this.externalResourceDir.trim();
                String error = null;
                File dir = null;
                if (DevAppServerMain.this.externalResourceDir.isEmpty()) {
                    error = "The empty string was specified for external_resource_dir";
                } else {
                    dir = new File(DevAppServerMain.this.externalResourceDir);
                    if (dir.exists()) {
                        if (!dir.isDirectory()) {
                            error = DevAppServerMain.this.externalResourceDir + " is not a directory.";
                        }
                    } else {
                        error = "No such directory: " + DevAppServerMain.this.externalResourceDir;
                    }
                }

                if (error != null) {
                    System.err.println(error);
                    System.exit(1);
                }

                return dir;
            }
        }
    }

    private abstract static class DevAppServerOption extends Option {
        protected DevAppServerMain main;

        DevAppServerOption(DevAppServerMain main, String shortName, String longName, boolean isFlag) {
            super(shortName, longName, isFlag);
            this.main = main;
        }
    }
}
