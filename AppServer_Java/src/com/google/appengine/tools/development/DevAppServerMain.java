package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.common.annotations.VisibleForTesting;
import com.google.appengine.repackaged.com.google.common.collect.ImmutableList;
import com.google.appengine.tools.info.SdkInfo;
import com.google.appengine.tools.info.UpdateCheck;
import com.google.appengine.tools.plugins.SDKPluginManager;
import com.google.appengine.tools.plugins.SDKRuntimePlugin;
import com.google.appengine.tools.plugins.SDKRuntimePlugin.ApplicationDirectories;
import com.google.appengine.tools.util.Action;
import com.google.appengine.tools.util.Option;
import com.google.appengine.tools.util.Parser;
import com.google.appengine.tools.util.Parser.ParseResult;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.PrintStream;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

public class DevAppServerMain extends SharedMain {
    public static final String EXTERNAL_RESOURCE_DIR_ARG = "external_resource_dir";
    public static final String GENERATE_WAR_ARG = "generate_war";
    public static final String GENERATED_WAR_DIR_ARG = "generated_war_dir";
    private static final String DEFAULT_RDBMS_PROPERTIES_FILE = ".local.rdbms.properties";
    private static final String RDBMS_PROPERTIES_FILE_SYSTEM_PROPERTY = "rdbms.properties.file";
    private static final String SYSTEM_PROPERTY_STATIC_MODULE_PORT_NUM_PREFIX = "com.google.appengine.devappserver_module.";
    private final Action ACTION = new DevAppServerMain.StartAction();
    private String versionCheckServer = SdkInfo.getDefaultServer();
    private String address = "127.0.0.1";
    private int port = 8080;
    private boolean disableUpdateCheck;
    private String generatedDirectory = null;
    private String defaultGcsBucketName = null;

    // add for AppScale
    private String db_location;
    private String login_server;
    private String cookie;
    private String appscale_version;
    private String admin_console_version;
    private static final String SECRET_LOCATION = "/etc/appscale/secret.key";

    @VisibleForTesting
    List<Option> getBuiltInOptions() {
        List<Option> options = new ArrayList();
        options.addAll(this.getSharedOptions());
        options.addAll(Arrays.asList(new Option("s", "server", false) {
            public void apply() {
                DevAppServerMain.this.versionCheckServer = this.getValue();
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --server=SERVER            The server to use to determine the latest", "  -s SERVER                   SDK version.");
            }
        }, new Option("a", "address", false) {
            public void apply() {
                DevAppServerMain.this.address = this.getValue();
                System.setProperty("MY_IP_ADDRESS", DevAppServerMain.this.address);
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --address=ADDRESS          The address of the interface on the local machine", "  -a ADDRESS                  to bind to (or 0.0.0.0 for all interfaces).");
            }
        }, new Option("p", "port", false) {
            public void apply() {
                DevAppServerMain.this.port = Integer.valueOf(this.getValue());
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --port=PORT                The port number to bind to on the local machine.", "  -p PORT");
            }
        }, new Option((String)null, "disable_update_check", true) {
            public void apply() {
                DevAppServerMain.this.disableUpdateCheck = true;
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --disable_update_check     Disable the check for newer SDK versions.");
            }
        }, new Option((String)null, "generated_dir", false) {
            public void apply() {
                DevAppServerMain.this.generatedDirectory = this.getValue();
            }

            public List<String> getHelpLines() {
                return ImmutableList.of(" --generated_dir=DIR        Set the directory where generated files are created.");
            }
        }, new Option((String)null, "default_gcs_bucket", false) {
            @Override
            public void apply() {
                DevAppServerMain.this.defaultGcsBucketName = this.getValue();
            }

            @Override
            public List<String> getHelpLines() {
                return ImmutableList.of(" --default_gcs_bucket=NAME  Set the default Google Cloud Storage bucket name.");
            }
        }, new Option((String)null, "instance_port", false) {
            @Override
            public void apply() {
                DevAppServerMain.processInstancePorts(this.getValues());
            }
        },
        /*
         * AppScale added all of the below to end of list
         */
        new Option((String)null, "datastore_path", false) {
            public void apply() {
                DevAppServerMain.this.db_location = this.getValue();
                System.setProperty("DB_LOCATION", DevAppServerMain.this.db_location);
            }
        }, new Option((String)null, "login_server", false) {
            public void apply() {
                DevAppServerMain.this.login_server = this.getValue();
                System.setProperty("LOGIN_SERVER", DevAppServerMain.this.login_server);
            }
        }, new Option((String)null, "appscale_version", false) {
            public void apply() {
                DevAppServerMain.this.appscale_version = this.getValue();
                System.setProperty("APP_SCALE_VERSION", DevAppServerMain.this.appscale_version);
            }
        },
        // changed from admin_console_server
        new Option((String)null, "admin_console_version", false) {
            public void apply() {
                DevAppServerMain.this.admin_console_version = this.getValue();
                System.setProperty("ADMIN_CONSOLE_VERSION", DevAppServerMain.this.admin_console_version);
            }
        }, new Option((String)null, "APP_NAME", false) {
            public void apply() {
                System.setProperty("APP_NAME", this.getValue());
            }
        }, new Option((String)null, "NGINX_ADDRESS", false) {
            public void apply() {
                System.setProperty("NGINX_ADDR", this.getValue());
            }
        }, new Option((String)null, "xmpp_path", false) {
            public void apply() {
                System.setProperty("XMPP_PATH", this.getValue());
            }
        }, new Option((String)null, "pidfile", false) {
            public void apply() {
                System.setProperty("PIDFILE", this.getValue());
            }
        }));
        return options;
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

    private List<Option> buildOptions() {
        List<Option> options = this.getBuiltInOptions();
        for (SDKRuntimePlugin runtimePlugin : SDKPluginManager.findAllRuntimePlugins()) {
            options = runtimePlugin.customizeDevAppServerOptions(options);
        }

        return options;
    }

    public static void main(String[] args) throws Exception {
        SharedMain.sharedInit();
        (new DevAppServerMain()).run(args);
    }

    public void run(String[] args) throws Exception {
        Parser parser = new Parser();
        ParseResult result = parser.parseArgs(this.ACTION, this.buildOptions(), args);
        result.applyArgs();
    }

    public void printHelp(PrintStream out) {
        out.println("Usage: <dev-appserver> [options] <app directory>");
        out.println("");
        out.println("Options:");
        for (Option option : this.buildOptions()) {
            for (String helpString : option.getHelpLines()) {
                out.println(helpString);
            }
        }

        out.println(" --jvm_flag=FLAG            Pass FLAG as a JVM argument. May be repeated to");
        out.println("                              supply multiple flags.");
    }

    class StartAction extends Action {
        StartAction() {
            super();
        }

        public void apply() {
            List args = this.getArgs();

            try {
                File externalResourceDir = DevAppServerMain.this.getExternalResourceDir();
                if (args.size() != 1) {
                    DevAppServerMain.this.printHelp(System.err);
                    System.exit(1);
                }

                File appDir = (new File((String)args.get(0))).getCanonicalFile();
                DevAppServerMain.this.validateWarPath(appDir);
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

                DevAppServer server = (new DevAppServerFactory()).createDevAppServer(appDir, externalResourceDir, DevAppServerMain.this.address, DevAppServerMain.this.port, DevAppServerMain.this.getNoJavaAgent());
                Map<String, String> stringProperties = DevAppServerMain.this.getSystemProperties();
                this.setGeneratedDirectory(stringProperties);
                this.setRdbmsPropertiesFile(stringProperties, appDir, externalResourceDir);
                DevAppServerMain.this.postServerActions(stringProperties);
                this.setDefaultGcsBucketName(stringProperties);
                DevAppServerMain.this.addPropertyOptionToProperties(stringProperties);
                server.setServiceProperties(stringProperties);

                // AppScale: Fetch and cache deployment secret.
                setSecret();

                try {
                    server.start().await();
                } catch (InterruptedException ie) {
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
    }
}
