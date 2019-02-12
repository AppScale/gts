package com.google.appengine.tools.development;

import com.google.appengine.tools.info.SdkImplInfo;
import com.google.appengine.tools.info.SdkInfo;
import java.io.File;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLClassLoader;
import java.security.AllPermission;
import java.security.CodeSource;
import java.security.PermissionCollection;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Logger;

class DevAppServerClassLoader extends URLClassLoader {
    private final ClassLoader delegate;
    private static final String DEV_APP_SERVER_INTERFACE = "com.google.appengine.tools.development.DevAppServer";
    private static final String APP_CONTEXT_INTERFACE = "com.google.appengine.tools.development.AppContext";
    private static final String DEV_APP_SERVER_AGENT = "com.google.appengine.tools.development.agent.AppEngineDevAgent";
    private static final String DEV_SOCKET_IMPL_FACTORY = "com.google.appengine.tools.development.DevSocketImplFactory";
    private static final Logger logger = Logger.getLogger(DevAppServerClassLoader.class.getName());

    public static DevAppServerClassLoader newClassLoader(ClassLoader delegate) {
        List<URL> libs = new ArrayList(SdkInfo.getSharedLibs());
        libs.addAll(SdkImplInfo.getImplLibs());
        libs.addAll(SdkImplInfo.getUserJspLibs());

        // AppScale: Add appengine-testing.jar from the 1.9.55 SDK to allow the ApiServer to convert error codes to
        // exceptions.
        File sdkRoot = SdkInfo.getSdkRoot();
        try {
            URL testingJar = new URL("file:" + sdkRoot + "/lib/testing/appengine-testing.jar");
            libs.add(testingJar);
        } catch (MalformedURLException e) {
            logger.warning("Unable to add appengine-testing.jar to path");
        }
        // End AppScale.

        return new DevAppServerClassLoader((URL[])libs.toArray(new URL[libs.size()]), delegate);
    }

    DevAppServerClassLoader(URL[] urls, ClassLoader delegate) {
        super(urls, (ClassLoader)null);
        this.delegate = delegate;
    }

    protected synchronized Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
        if (!name.equals("com.google.appengine.tools.development.DevAppServer") && !name.equals("com.google.appengine.tools.development.AppContext") && !name.equals("com.google.appengine.tools.development.agent.AppEngineDevAgent") && !name.equals("com.google.appengine.tools.development.DevSocketImplFactory") && !name.startsWith("com.google.appengine.tools.info.") && !name.startsWith("com.google.appengine.tools.plugins")) {
            return super.loadClass(name, resolve);
        } else {
            Class<?> c = this.delegate.loadClass(name);
            if (resolve) {
                this.resolveClass(c);
            }

            return c;
        }
    }

    protected PermissionCollection getPermissions(CodeSource codesource) {
        PermissionCollection permissions = super.getPermissions(codesource);
        permissions.add(new AllPermission());
        return permissions;
    }
}
