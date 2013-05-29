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
import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TimeZone;


public class DevAppServerMain
{
    public static final String  EXTERNAL_RESOURCE_DIR_ARG             = "external_resource_dir";
    public static final String  GENERATE_WAR_ARG                      = "generate_war";
    public static final String  GENERATED_WAR_DIR_ARG                 = "generated_war_dir";
    private static final String DEFAULT_RDBMS_PROPERTIES_FILE         = ".local.rdbms.properties";
    private static final String RDBMS_PROPERTIES_FILE_SYSTEM_PROPERTY = "rdbms.properties.file";
    private static String       originalTimeZone;
    private final Action        ACTION                                = new StartAction();

    private String              server                                = SdkInfo.getDefaultServer();

    private String              address                               = "127.0.0.1";
    private int                 port                                  = 8080;
    private boolean             disableUpdateCheck;
    private boolean             disableRestrictedCheck                = true;
    private String              externalResourceDir                   = null;
    private List<String>        propertyOptions                       = null;
    private String              generatedDirectory                    = null;

    // add for AppScale
    private String              db_location;
    private String              login_server;
    private String              cookie;
    private String              appscale_version;
    private String              admin_console_version;

    private final List<Option>  PARSERS                               = buildOptions(this);
    private static final String PREFIX                                = "When generating a war directory,";

    private static List<Option> getBuiltInOptions( DevAppServerMain main )
    {
        return Arrays.asList(new Option[] { new Option("h", "help", true)
        {
            public void apply()
            {
                System.out.println("HELP ARG WAS GIVEN");
                DevAppServerMain.printHelp(System.err);
                System.exit(0);
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --help, -h                 Show this help message and exit.");
            }
        }, new DevAppServerOption(main, "s", "server", false)
        {
            public void apply()
            {
                this.main.server = getValue();
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --server=SERVER            The server to use to determine the latest", "  -s SERVER                   SDK version.");
            }
        }, new DevAppServerOption(main, "a", "address", false)
        {
            public void apply()
            {
                this.main.address = getValue();
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --address=ADDRESS          The address of the interface on the local machine", "  -a ADDRESS                  to bind to (or 0.0.0.0 for all interfaces).");
            }
        }, new DevAppServerOption(main, "p", "port", false)
        {
            public void apply()
            {
                this.main.port = Integer.valueOf(getValue()).intValue();
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --port=PORT                The port number to bind to on the local machine.", "  -p PORT");
            }
        }, new DevAppServerOption(main, null, "sdk_root", false)
        {
            public void apply()
            {
                System.setProperty("appengine.sdk.root", getValue());
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --sdk_root=DIR             Overrides where the SDK is located.");
            }
        }, new DevAppServerOption(main, null, "disable_update_check", true)
        {
            public void apply()
            {
                this.main.disableUpdateCheck = true;
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --disable_update_check     Disable the check for newer SDK versions.");
            }
        }, new DevAppServerOption(main, null, "generated_dir", false)
        {
            public void apply()
            {
                this.main.generatedDirectory = getValue();
            }

            public List<String> getHelpLines()
            {
                return ImmutableList.of(" --generated_dir=DIR        Set the directory where generated files are created.");
            }
        }, new DevAppServerOption(main, null, "disable_restricted_check", true)
        {
            public void apply()
            {
                this.main.disableRestrictedCheck = true;
            }
        }, new DevAppServerOption(main, null, "external_resource_dir", false)
        {
            public void apply()
            {
                this.main.externalResourceDir = getValue();
            }
        }, new DevAppServerOption(main, null, "property", false)
        {
            public void apply()
            {
                this.main.propertyOptions = getValues();
            }
            /*
             * AppScale added all of the below to end of list
             */
        }, new DevAppServerOption(main, null, "datastore_path", false)
        {
            public void apply()
            {
                this.main.db_location = getValue();
                System.setProperty("DB_LOCATION", this.main.db_location);
            }
        }, new DevAppServerOption(main, null, "login_server", false)
        {
            public void apply()
            {
                this.main.login_server = getValue();
                System.setProperty("LOGIN_SERVER", this.main.login_server);
            }
        }, new DevAppServerOption(main, null, "cookie_secret", false)
        {
            public void apply()
            {
                this.main.cookie = getValue();
                System.setProperty("COOKIE_SECRET", this.main.cookie);
            }
        }, new DevAppServerOption(main, null, "appscale_version", false)
        {
            public void apply()
            {
                this.main.appscale_version = getValue();
                System.setProperty("APP_SCALE_VERSION", this.main.appscale_version);
            }
        }, new DevAppServerOption(main, null, "admin_console_version", false)
        { // changed from admin_console_server
                    public void apply()
                    {
                        this.main.admin_console_version = getValue();
                        System.setProperty("ADMIN_CONSOLE_VERSION", this.main.admin_console_version);
                    }
                }, new DevAppServerOption(main, null, "NGINX_ADDRESS", false)
                {
                    public void apply()
                    {
                        System.setProperty("NGINX_ADDR", getValue());
                    }
                }, new DevAppServerOption(main, null, "NGINX_PORT", false)
                {
                    public void apply()
                    {
                        System.setProperty("NGINX_PORT", getValue());
                    }
                } });
    }

    private static List<Option> buildOptions( DevAppServerMain main )
    {
        List options = getBuiltInOptions(main);
        for (SDKRuntimePlugin runtimePlugin : SDKPluginManager.findAllRuntimePlugins())
        {
            options = runtimePlugin.customizeDevAppServerOptions(options);
        }
        return options;
    }

    public static void main( String[] args ) throws Exception
    {
        recordTimeZone();
        Logging.initializeLogging();
        if (System.getProperty("os.name").equalsIgnoreCase("Mac OS X"))
        {
            Toolkit.getDefaultToolkit();
        }
        new DevAppServerMain(args);
    }

    private static void recordTimeZone()
    {
        originalTimeZone = System.getProperty("user.timezone");
    }

    public DevAppServerMain( String[] args ) throws Exception
    {
        Parser parser = new Parser();
        Parser.ParseResult result = parser.parseArgs(this.ACTION, this.PARSERS, args);
        result.applyArgs();
    }

    public static void printHelp( PrintStream out )
    {
        System.out.println("Printing help lines");
        out.println("Usage: <dev-appserver> [options] <app directory>");
        out.println("");
        out.println("Options:");
        for (Option option : buildOptions(null))
        {
            for (String helpString : option.getHelpLines())
            {
                out.println(helpString);
            }
        }
        out.println(" --jvm_flag=FLAG            Pass FLAG as a JVM argument. May be repeated to");
        out.println("                              supply multiple flags.");
    }

    public static void validateWarPath( File war )
    {
        if (!war.exists())
        {
            System.out.println("Unable to find the webapp directory " + war);
            printHelp(System.err);
            System.exit(1);
        }
        else if (!war.isDirectory())
        {
            System.out.println("dev_appserver only accepts webapp directories, not war files.");
            printHelp(System.err);
            System.exit(1);
        }
    }

    private void validateArgsForWarGeneration( List<String> args )
    {
        ifNotWarGenConditionExit(this.externalResourceDir != null, "--external_resource_dir must also be specified.");

        File appYamlFile = new File(this.externalResourceDir, "app.yaml");
        ifNotWarGenConditionExit(appYamlFile.isFile(), "the external resource directory must contain a file named app.yaml.");

        ifNotWarGenConditionExit(args.size() == 0, "the command line should not include a war directory argument.");
    }

    @VisibleForTesting
    static Map<String, String> parsePropertiesList( List<String> properties )
    {
        Map parsedProperties = new HashMap();
        if (properties != null)
        {
            for (String property : properties)
            {
                String[] propertyKeyValue = property.split("=", 2);
                if (propertyKeyValue.length == 2)
                    parsedProperties.put(propertyKeyValue[0], propertyKeyValue[1]);
                else if (propertyKeyValue[0].startsWith("no"))
                    parsedProperties.put(propertyKeyValue[0].substring(2), "false");
                else
                {
                    parsedProperties.put(propertyKeyValue[0], "true");
                }
            }
        }
        return parsedProperties;
    }

    private static void ifNotWarGenConditionExit( boolean condition, String suffix )
    {
        if (!condition)
        {
            System.err.println("When generating a war directory, " + suffix);
            System.exit(1);
        }
    }

    class StartAction extends Action
    {
        StartAction()
        {
            super();
        }

        public void apply()
        {
            List args = getArgs();
            try
            {
                File externalResourceDir = getExternalResourceDir();
                if (args.size() != 1)
                {
		    System.out.println("ARGS SIZE WASNT 1");
                    DevAppServerMain.printHelp(System.err);
                    System.exit(1);
                }
                File appDir = new File((String)args.get(0)).getCanonicalFile();
                DevAppServerMain.validateWarPath(appDir);

                SDKRuntimePlugin runtimePlugin = SDKPluginManager.findRuntimePlugin(appDir);
                if (runtimePlugin != null)
                {
                    SDKRuntimePlugin.ApplicationDirectories appDirs = runtimePlugin.generateApplicationDirectories(appDir);
                    appDir = appDirs.getWarDir();
                    externalResourceDir = appDirs.getExternalResourceDir();
                }

                UpdateCheck updateCheck = new UpdateCheck(DevAppServerMain.this.server, appDir, true);
                if ((updateCheck.allowedToCheckForUpdates()) && (!DevAppServerMain.this.disableUpdateCheck))
                {
                    updateCheck.maybePrintNagScreen(System.err);
                }
                updateCheck.checkJavaVersion(System.err);

                DevAppServer server = new DevAppServerFactory().createDevAppServer(appDir, externalResourceDir, DevAppServerMain.this.address, DevAppServerMain.this.port);

                Map properties = System.getProperties();

                Map stringProperties = properties;
                setTimeZone(stringProperties);
                setGeneratedDirectory(stringProperties);
                if (DevAppServerMain.this.disableRestrictedCheck)
                {
                    stringProperties.put("appengine.disableRestrictedCheck", "");
                }
                setRdbmsPropertiesFile(stringProperties, appDir, externalResourceDir);
                stringProperties.putAll(DevAppServerMain.parsePropertiesList(DevAppServerMain.this.propertyOptions));
                server.setServiceProperties(stringProperties);

                server.start();
                try
                {
                    while (true)
                    {
                        Thread.sleep(3600000L);
                    }
                }
                catch (InterruptedException e)
                {
                    System.out.println("Shutting down.");
                    System.exit(0);
                }
            }
            catch (Exception ex)
            {
                ex.printStackTrace();
                System.exit(1);
            }
        }

        private void setTimeZone( Map<String, String> serviceProperties )
        {
            String timeZone = (String)serviceProperties.get("appengine.user.timezone");
            if (timeZone != null)
                TimeZone.setDefault(TimeZone.getTimeZone(timeZone));
            else
            {
                timeZone = DevAppServerMain.originalTimeZone;
            }
            serviceProperties.put("appengine.user.timezone.impl", timeZone);
        }

        private void setGeneratedDirectory( Map<String, String> stringProperties )
        {
            if (DevAppServerMain.this.generatedDirectory != null)
            {
                File dir = new File(DevAppServerMain.this.generatedDirectory);
                String error = null;
                if (dir.exists())
                {
                    if (!dir.isDirectory())
                        error = DevAppServerMain.this.generatedDirectory + " is not a directory.";
                    else if (!dir.canWrite()) error = DevAppServerMain.this.generatedDirectory + " is not writable.";
                }
                else if (!dir.mkdirs())
                {
                    error = "Could not make " + DevAppServerMain.this.generatedDirectory;
                }
                if (error != null)
                {
                    System.err.println(error);
                    System.exit(1);
                }
                stringProperties.put("appengine.generated.dir", DevAppServerMain.this.generatedDirectory);
            }
        }

        private void setRdbmsPropertiesFile( Map<String, String> stringProperties, File appDir, File externalResourceDir )
        {
            if (stringProperties.get("rdbms.properties.file") != null)
            {
                return;
            }
            File file = findRdbmsPropertiesFile(externalResourceDir);
            if (file == null)
            {
                file = findRdbmsPropertiesFile(appDir);
            }
            if (file != null)
            {
                String path = file.getPath();
                System.out.println("Reading local rdbms properties from " + path);
                stringProperties.put("rdbms.properties.file", path);
            }
        }

        private File findRdbmsPropertiesFile( File dir )
        {
            File candidate = new File(dir, ".local.rdbms.properties");
            if ((candidate.isFile()) && (candidate.canRead()))
            {
                return candidate;
            }
            return null;
        }

        private File getExternalResourceDir()
        {
            if (DevAppServerMain.this.externalResourceDir == null)
            {
                return null;
            }
            DevAppServerMain.this.externalResourceDir = DevAppServerMain.this.externalResourceDir.trim();
            String error = null;
            File dir = null;
            if (DevAppServerMain.this.externalResourceDir.isEmpty())
            {
                error = "The empty string was specified for external_resource_dir";
            }
            else
            {
                dir = new File(DevAppServerMain.this.externalResourceDir);
                if (dir.exists())
                {
                    if (!dir.isDirectory()) error = DevAppServerMain.this.externalResourceDir + " is not a directory.";
                }
                else
                {
                    error = "No such directory: " + DevAppServerMain.this.externalResourceDir;
                }
            }
            if (error != null)
            {
                System.err.println(error);
                System.exit(1);
            }
            return dir;
        }
    }

    private static abstract class DevAppServerOption extends Option
    {
        protected DevAppServerMain main;

        DevAppServerOption( DevAppServerMain main, String shortName, String longName, boolean isFlag )
        {
            super(shortName, longName, isFlag);
            this.main = main;
        }
    }
}
