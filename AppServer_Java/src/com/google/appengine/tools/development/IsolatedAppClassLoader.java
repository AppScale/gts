package com.google.appengine.tools.development;

import com.google.appengine.tools.info.SdkImplInfo;
import com.google.appengine.tools.info.SdkInfo;
import com.google.apphosting.utils.io.IoUtil;
import java.io.File;
import java.io.FilePermission;
import java.io.IOException;
import java.lang.reflect.ReflectPermission;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLClassLoader;
import java.net.URLConnection;
import java.security.AccessController;
import java.security.AllPermission;
import java.security.CodeSource;
import java.security.Permission;
import java.security.PermissionCollection;
import java.security.Permissions;
import java.security.Policy;
import java.security.Policy.Parameters;
import java.security.PrivilegedAction;
import java.security.ProtectionDomain;
import java.security.Provider;
import java.security.UnresolvedPermission;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.List;
import java.util.PropertyPermission;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.logging.LoggingPermission;

class IsolatedAppClassLoader extends URLClassLoader
{
  private static Logger logger = Logger.getLogger(IsolatedAppClassLoader.class.getName());
  private final PermissionCollection appPermissions;
  private final Permissions appPermissionsAsPermissions;
  private final ClassLoader devAppServerClassLoader;
  private final Set<URL> sharedCodeLibs;
  private final Set<URL> agentRuntimeLibs;

  public IsolatedAppClassLoader(File appRoot, URL[] urls, ClassLoader devAppServerClassLoader)
  {
    super(urls, null);
    checkWorkingDirectory(appRoot);
    this.appPermissions = createAppPermissions(appRoot);
    this.appPermissionsAsPermissions = new Permissions();
    addAllPermissions(this.appPermissions, this.appPermissionsAsPermissions);
    installPolicyProxy(appRoot);
    this.devAppServerClassLoader = devAppServerClassLoader;
    this.sharedCodeLibs = new HashSet(SdkInfo.getSharedLibs());
    this.agentRuntimeLibs = new HashSet(SdkImplInfo.getAgentRuntimeLibs());
  }

  private static void checkWorkingDirectory(File appRoot)
  {
    File workingDir = new File(System.getProperty("user.dir"));

    String canonicalWorkingDir = null;
    String canonicalAppRoot = null;
    try
    {
      canonicalWorkingDir = workingDir.getCanonicalPath();
      canonicalAppRoot = appRoot.getCanonicalPath();
    } catch (IOException e) {
      logger.log(Level.FINE, "Unable to compare the working directory and app root.", e);
    }

    if (!canonicalWorkingDir.equals(canonicalAppRoot)) {
      String newLine = System.getProperty("line.separator");
      String workDir = workingDir.getAbsolutePath();
      String appDir = appRoot.getAbsolutePath();
      String msg = "Your working directory, (" + workDir + ") is not equal to your " + newLine + "web application root (" + appDir + ")" + newLine + "You will not be able to access files from your working directory on the " + "production server." + newLine;

      logger.warning(msg);
    }
  }

  protected synchronized Class<?> loadClass(String name, boolean resolve)
    throws ClassNotFoundException
  {
    try
    {
      final Class c = this.devAppServerClassLoader.loadClass(name);

      CodeSource source = (CodeSource)AccessController.doPrivileged(new PrivilegedAction()
      {
        public CodeSource run() {
          return c.getProtectionDomain().getCodeSource();
        }
      });
      if (source == null) {
        return c;
      }

      URL location = source.getLocation();
      if ((this.sharedCodeLibs.contains(location)) || (location.getFile().endsWith("/appengine-agent.jar")))
      {
        if (resolve) {
          resolveClass(c);
        }
        return c;
      }

    }
    catch (ClassNotFoundException e)
    {
    }

    return super.loadClass(name, resolve);
  }

  protected PermissionCollection getPermissions(CodeSource codesource)
  {
    PermissionCollection permissions = super.getPermissions(codesource);
    if (this.agentRuntimeLibs.contains(codesource.getLocation()))
      permissions.add(new AllPermission());
    else {
      addAllPermissions(this.appPermissions, permissions);
    }
    return permissions;
  }

  public Permissions getAppPermissions() {
    return this.appPermissionsAsPermissions;
  }

  private PermissionCollection createAppPermissions(File appRoot) {
    PermissionCollection permissions = new Permissions();

    permissions.add(new FilePermission(appRoot.getAbsolutePath() + File.separatorChar + "-", "read"));

    addAllPermissions(buildPermissionsToReadAppFiles(appRoot), permissions);

    if (Boolean.valueOf(System.getProperty("--enable_all_permissions")).booleanValue()) {
      permissions.add(new AllPermission());
      return permissions;
    }

    permissions.add(new RuntimePermission("getClassLoader"));
    permissions.add(new RuntimePermission("setContextClassLoader"));
    permissions.add(new RuntimePermission("createClassLoader"));
    permissions.add(new RuntimePermission("getProtectionDomain"));
    permissions.add(new RuntimePermission("accessDeclaredMembers"));
    permissions.add(new ReflectPermission("suppressAccessChecks"));
    permissions.add(new LoggingPermission("control", ""));
    permissions.add(new RuntimePermission("getStackTrace"));
    permissions.add(new RuntimePermission("getenv.*"));
    permissions.add(new RuntimePermission("setIO"));
    permissions.add(new PropertyPermission("*", "read,write"));

    permissions.add(new RuntimePermission("loadLibrary.keychain"));

    permissions.add(new UnresolvedPermission("javax.jdo.spi.JDOPermission", "getMetadata", null, null));

    permissions.add(new UnresolvedPermission("javax.jdo.spi.JDOPermission", "setStateManager", null, null));

    permissions.add(new UnresolvedPermission("javax.jdo.spi.JDOPermission", "manageMetadata", null, null));

    permissions.add(new UnresolvedPermission("javax.jdo.spi.JDOPermission", "closePersistenceManagerFactory", null, null));

    permissions.add(new UnresolvedPermission("groovy.security.GroovyCodeSourcePermission", "*", null, null));

    permissions.add(new FilePermission(System.getProperty("user.dir") + File.separatorChar + "-", "read"));

    permissions.add(getJreReadPermission());

    for (File f : SdkInfo.getSharedLibFiles()) {
      permissions.add(new FilePermission(f.getAbsolutePath(), "read"));
    }

    permissions.setReadOnly();

    return permissions;
  }

  private void installPolicyProxy(File appRoot)
  {
    Policy p = Policy.getPolicy();
    if (p instanceof ProxyPolicy) {
      return;
    }
    Policy.setPolicy(new ProxyPolicy(p, appRoot));
  }

  private static PermissionCollection buildPermissionsToReadAppFiles(File contextRoot)
  {
    PermissionCollection permissions = new Permissions();
    String path = contextRoot.getAbsolutePath();
    permissions.add(new FilePermission(path, "read"));
    permissions.add(new FilePermission(path + "/-", "read"));

    List<File> allFiles = IoUtil.getFilesAndDirectories(contextRoot);

    for (File file : allFiles) {
      String filePath = file.getAbsolutePath();
      permissions.add(new FilePermission(filePath, "read"));
    }

    permissions.setReadOnly();
    return permissions;
  }

  private static Permission getReadPermission(URL url) {
    Permission p = null;
    try {
      URLConnection urlConnection = url.openConnection();
      p = urlConnection.getPermission();
    } catch (IOException e) {
      throw new RuntimeException("Unable to obtain the permission for " + url, e);
    }
    return new FilePermission(p.getName(), "read");
  }

  private static Permission getJreReadPermission() {
    return getReadPermission(Object.class.getResource("/java/lang/Object.class"));
  }

  private static void addAllPermissions(PermissionCollection src, PermissionCollection dest)
  {
    Enumeration srcElements = src.elements();
    while (srcElements.hasMoreElements())
      dest.add((Permission)srcElements.nextElement());
  }

  class ProxyPolicy extends Policy
  {
    private Policy delegate;
    private File appRoot;

    ProxyPolicy(Policy delegate, File appRoot)
    {
      this.delegate = delegate;
      this.appRoot = appRoot;
    }

    public Provider getProvider()
    {
      return this.delegate.getProvider();
    }

    public String getType()
    {
      return this.delegate.getType();
    }

    public Policy.Parameters getParameters()
    {
      return this.delegate.getParameters();
    }

    public PermissionCollection getPermissions(final CodeSource codeSource)
    {
      return (PermissionCollection)AccessController.doPrivileged(new PrivilegedAction()
      {
        public PermissionCollection run()
        {
          PermissionCollection delegatePerms = IsolatedAppClassLoader.ProxyPolicy.this.delegate.getPermissions(codeSource);
          try
          {
            if (IsolatedAppClassLoader.ProxyPolicy.this.appRoot.toURL().equals(codeSource.getLocation())) {
              Permissions newPerms = new Permissions();
              IsolatedAppClassLoader.addAllPermissions(delegatePerms, newPerms);
              IsolatedAppClassLoader.addAllPermissions(IsolatedAppClassLoader.this.appPermissions, newPerms);
              return newPerms;
            }
          } catch (MalformedURLException ex) {
            throw new RuntimeException("Could not turn " + IsolatedAppClassLoader.ProxyPolicy.this.appRoot + "into a URL", ex);
          }
          return delegatePerms;
        }
      });
    }

    public PermissionCollection getPermissions(ProtectionDomain domain)
    {
      return getPermissions(domain.getCodeSource());
    }

    public boolean implies(final ProtectionDomain domain, final Permission permission)
    {
      return ((Boolean)AccessController.doPrivileged(new PrivilegedAction() {
        public Boolean run() {
          return Boolean.valueOf(IsolatedAppClassLoader.ProxyPolicy.this.delegate.implies(domain, permission));
        }
      })).booleanValue();
    }

    public void refresh()
    {
      this.delegate.refresh();
    }
  }
}