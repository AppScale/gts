// Copyright 2010 Google Inc. All Rights Reserved.
// Modified for AppScale authentication.
package com.google.appengine.tools.remoteapi;

import com.google.appengine.api.users.dev.LoginCookieUtils;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.Delegate;
import com.google.apphosting.api.ApiProxy.Environment;

/* The imports were changed to point to the repackaged classes. */
import com.google.appengine.repackaged.org.apache.commons.httpclient.Cookie;
import com.google.appengine.repackaged.org.apache.commons.httpclient.NameValuePair;
import com.google.appengine.repackaged.org.apache.commons.httpclient.HttpClient;
import com.google.appengine.repackaged.org.apache.commons.httpclient.HttpStatus;
import com.google.appengine.repackaged.org.apache.commons.httpclient.methods.PostMethod;

import java.net.URLEncoder;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.ConsoleHandler;
import java.util.logging.Formatter;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import java.util.logging.StreamHandler;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Installs and uninstalls the remote API. While the RemoteApi is installed,
 * all App Engine calls made by the same thread that performed the installation
 * will be sent to a remote server.
 *
 * <p>Instances of this class can only be used on a single thread.</p>
 *
 */
public class RemoteApiInstaller {
  private static final Pattern PAIR_REGEXP =
      Pattern.compile("([a-z0-9_-]+): +'?([:~.a-z0-9_-]+)'?");

  /**
   * A key that can be put into {@link Environment#getAttributes()} to override the app id used by
   * the Datastore API.  Note that this is copied from
   * com.google.appengine.api.datastore.DatastoreApiHelper to avoid a dependency on that class.  It
   * must be kept in sync.
   * TODO(user): Can we just depend on that class?
   */
  static final String DATASTORE_APP_ID_OVERRIDE_KEY =
      "com.google.appengine.datastore.AppIdOverride";

  private static ConsoleHandler remoteMethodHandler;

  private static synchronized StreamHandler getStreamHandler() {
    if (remoteMethodHandler == null) {
      remoteMethodHandler = new ConsoleHandler();
      remoteMethodHandler.setFormatter(new Formatter() {
        @Override
        public String format(LogRecord record) {
          return record.getMessage() + "\n";
        }
      });
      remoteMethodHandler.setLevel(Level.FINE);
    }
    return remoteMethodHandler;
  }

  private InstallerState installerState;

  /**
   * Installs the remote API using the provided options.  Logs into the remote
   * application using the credentials available via these options.
   *
   * <p>Warning: This method only installs the remote API on the current
   * thread.  Do not share this instance across threads!</p>
   *
   * @throws IllegalArgumentException if the server or credentials weren't provided.
   * @throws IllegalStateException if already installed
   * @throws LoginException if unable to log in.
   * @throws IOException if unable to connect to the remote API.
   */
  public void install(RemoteApiOptions options) throws IOException {
    options = options.copy();
    if (options.getHostname() == null) {
      throw new IllegalArgumentException("server not set in options");
    }
    if (options.getUserEmail() == null) {
      throw new IllegalArgumentException("credentials not set in options");
    }

    synchronized (getClass()) {
      if (installerState != null) {
        throw new IllegalStateException("remote API is already installed");
      }
      @SuppressWarnings("unchecked")
      Delegate<Environment> originalDelegate = ApiProxy.getDelegate();
      Environment originalEnv = ApiProxy.getCurrentEnvironment();
      AppEngineClient installedClient = login(options);
      RemoteApiDelegate remoteApiDelegate;
      if (originalDelegate instanceof ThreadLocalDelegate) {
        ThreadLocalDelegate<Environment> installedDelegate =
            (ThreadLocalDelegate<Environment>) originalDelegate;
        Delegate<Environment> globalDelegate = installedDelegate.getGlobalDelegate();
        remoteApiDelegate = createDelegate(options, installedClient, globalDelegate);
        if (installedDelegate.getDelegateForThread() != null) {
          throw new IllegalStateException("remote API is already installed");
        }
        installedDelegate.setDelegateForThread(remoteApiDelegate);
      } else {
        remoteApiDelegate = createDelegate(options, installedClient, originalDelegate);
        ApiProxy.setDelegate(new ThreadLocalDelegate<Environment>(
            originalDelegate, remoteApiDelegate));
      }
      Environment installedEnv = null;
      String appIdOverrideToRestore = null;
      if (originalEnv == null) {
        installedEnv = createEnv(options, installedClient);
        ApiProxy.setEnvironmentForCurrentThread(installedEnv);
      } else {
        appIdOverrideToRestore =
            (String) originalEnv.getAttributes().get(DATASTORE_APP_ID_OVERRIDE_KEY);
        originalEnv.getAttributes().put(DATASTORE_APP_ID_OVERRIDE_KEY, installedClient.getAppId());
      }

      installerState = new InstallerState(
          originalEnv,
          installedClient,
          remoteApiDelegate,
          installedEnv,
          appIdOverrideToRestore);
    }
  }

  /**
   * The state related to the installation of a {@link RemoteApiInstaller}.
   * It's just a struct, but it makes it easy for us to ensure that we don't
   * end up in an inconsistent state when installation fails part-way through.
   */
  private static class InstallerState { private final Environment originalEnv;
    private final AppEngineClient installedClient;
    private final RemoteApiDelegate remoteApiDelegate; private final Environment installedEnv; String appIdOverrideToRestore;

    InstallerState(
        Environment originalEnv,
        AppEngineClient installedClient,
        RemoteApiDelegate remoteApiDelegate,
        Environment installedEnv,
        String appIdOverrideToRestore) {
      this.originalEnv = originalEnv;
      this.installedClient = installedClient;
      this.remoteApiDelegate = remoteApiDelegate;
      this.installedEnv = installedEnv;
      this.appIdOverrideToRestore = appIdOverrideToRestore;
    }
  }
  /**
   * Uninstalls the remote API. If any async calls are in progress, waits for
   * them to finish.
   *
   * <p>If the remote API isn't installed, this method has no effect.</p>
   */
  public void uninstall() {
    synchronized (getClass()) {
      if (installerState == null) {
        throw new IllegalArgumentException("remote API is already uninstalled");
      }
      if (installerState.installedEnv != null &&
          installerState.installedEnv != ApiProxy.getCurrentEnvironment()) {
        throw new IllegalStateException(
          "Can't uninstall because the current environment has been modified.");
      }
      ApiProxy.Delegate<?> currentDelegate = ApiProxy.getDelegate();
      if (!(currentDelegate instanceof ThreadLocalDelegate)) {
        throw new IllegalStateException(
            "Can't uninstall because the current delegate has been modified.");
      }
      ThreadLocalDelegate<?> tld = (ThreadLocalDelegate<?>) currentDelegate;
      if (tld.getDelegateForThread() == null) {
        throw new IllegalArgumentException("remote API is already uninstalled");
      }
      tld.clearThreadDelegate();

      if (installerState.installedEnv != null) {
        ApiProxy.setEnvironmentForCurrentThread(installerState.originalEnv);
      } else {
        if (installerState.appIdOverrideToRestore != null) {
          ApiProxy.getCurrentEnvironment().getAttributes().put(
              DATASTORE_APP_ID_OVERRIDE_KEY, installerState.appIdOverrideToRestore);
        } else {
          ApiProxy.getCurrentEnvironment().getAttributes().remove(DATASTORE_APP_ID_OVERRIDE_KEY);
        }
      }

      installerState.remoteApiDelegate.shutdown();
      installerState = null;
    }
  }

  /**
   * Returns a string containing the cookies associated with this
   * connection. The string can be used to create a new connection
   * without logging in again by using {@link RemoteApiOptions#reuseCredentials}.
   * By storing credentials to a file, we can avoid repeated password
   * prompts in command-line tools. (Note that the cookies will expire
   * based on the setting under Application Settings in the admin console.)
   *
   * <p>Beware: it's important to keep this string private, as it
   * allows admin access to the app as the current user.</p>
   */
  public String serializeCredentials() {
    return installerState.installedClient.serializeCredentials();
  }

  /**
   * Starts logging remote API method calls to the console. (Useful within tests.)
   */
  public void logMethodCalls() {
    Logger logger = Logger.getLogger(RemoteApiDelegate.class.getName());
    logger.setLevel(Level.FINE);
    if (!Arrays.asList(logger.getHandlers()).contains(getStreamHandler())) {
      logger.addHandler(getStreamHandler());
    }
  }

  public void resetRpcCount() {
    installerState.remoteApiDelegate.resetRpcCount();
  }

  /**
   * Returns the number of RPC calls made since the API was installed
   * or {@link #resetRpcCount} was called.
   */
  public int getRpcCount() {
    return installerState.remoteApiDelegate.getRpcCount();
  }

  AppEngineClient login(RemoteApiOptions options) throws IOException {
    return loginImpl(options);
  }

  RemoteApiDelegate createDelegate(RemoteApiOptions options, AppEngineClient client, Delegate<Environment> originalDelegate) {
    return RemoteApiDelegate.newInstance(new RemoteRpc(client), options, originalDelegate);
  }

  Environment createEnv(RemoteApiOptions options, AppEngineClient client) {
    return new ToolEnvironment(client.getAppId(), options.getUserEmail());
  }

  /**
   * Submits credentials and gets cookies for logging in to AppScale.
   * (Also downloads the appId from the remote API.)
   * @return an AppEngineClient containing credentials (if successful)
   * @throws LoginException for a login failure
   * @throws IOException for other connection failures
   *
   * Modified to only get credentials for AppScale.
   */
  private AppEngineClient loginImpl(RemoteApiOptions options) throws IOException {
    List<Cookie> authCookies;
    if (!authenticationRequiresCookies(options)) {
      authCookies = Collections.emptyList();
    } else if (options.getCredentialsToReuse() != null) {
      authCookies = parseSerializedCredentials(options.getUserEmail(), options.getHostname(),
          options.getCredentialsToReuse());
    } else {
      authCookies = getAppScaleServerCookie(options.getHostname(), options.getUserEmail(), options.getPassword());
    }

    String appId = getAppIdFromServer(authCookies, options);
    return createAppEngineClient(options, authCookies, appId);
  }

  /**
   * @return {@code true} if the authentication to support the {@link RemoteApiOptions} requires
   *         cookies, {@code false} otherwise
   */
  boolean authenticationRequiresCookies(final RemoteApiOptions options) {
    return true;
  }

  AppEngineClient createAppEngineClient(RemoteApiOptions options,
      List<Cookie> authCookies, String appId) {
    if (ApiProxy.getCurrentEnvironment() != null) {
      return new HostedAppEngineClient(options, authCookies, appId);
    }
    return new StandaloneAppEngineClient(options, authCookies, appId);
  }

  /**
   * Fetches the AppScale Cookie for being considered the admin.
   */
  public static List<Cookie> getAppScaleServerCookie(String hostname, String email, String password) {
    HttpClient client = new HttpClient();
    PostMethod method = new PostMethod("https://" + hostname + ":1443/users/authenticate");
    NameValuePair[] data = {
      new NameValuePair("user_email", email),
      new NameValuePair("user_password", password)
    };
    method.setRequestBody(data);
    List<Cookie> authCookies = new ArrayList<Cookie>();
    try {
      client.executeMethod(method);
      Cookie[] cookies = client.getState().getCookies();
      for (int ii = 0; ii < cookies.length; ii++) {
        Cookie cookie = cookies[ii];
        authCookies.add(cookie);
      }
    } catch(Exception e){
      System.err.println("Error getting AppScale Cookie!");
      System.err.println(e);
      e.printStackTrace();
    } finally {
      method.releaseConnection();
    }

    return authCookies;
  }

  String getAppIdFromServer(List<Cookie> authCookies, RemoteApiOptions options)
      throws IOException {
    AppEngineClient tempClient = createAppEngineClient(options, authCookies, null);
    AppEngineClient.Response response = tempClient.get(options.getRemoteApiPath());
    int status = response.getStatusCode();
    if (status != 200) {
      if (response.getBodyAsBytes() == null) {
        throw new IOException("can't get appId from remote api; status code = " + status);
      } else {
        throw new IOException("can't get appId from remote api; status code = " + status
            + ", body: " + response.getBodyAsString());
      }
    }
    String body = response.getBodyAsString();
    Map<String, String> props = parseYamlMap(body);
    String appId = props.get("app_id");
    if (appId == null) {
      throw new IOException("unexpected response from remote api: " + body);
    }
    return appId;
  }

  /**
   * Parses the response from the remote API as a YAML map.
   */
  static Map<String, String> parseYamlMap(String input) {
    Map<String, String> result = new HashMap<String, String>();
    input = input.trim();
    if (!input.startsWith("{") || !input.endsWith("}")) {
      return Collections.emptyMap();
    }
    input = input.substring(1, input.length() - 1);

    String[] pairs = input.split(", +");
    for (String pair : pairs) {
      Matcher matcher = PAIR_REGEXP.matcher(pair);
      if (matcher.matches()) {
        result.put(matcher.group(1), matcher.group(2));
      }
    }
    return result;
  }

  static List<Cookie> parseSerializedCredentials(String expectedEmail, String expectedHost, String serializedCredentials) throws IOException {
    Map<String, List<String>> props = parseProperties(serializedCredentials);
    checkOneProperty(props, "email");
    checkOneProperty(props, "host");
    String email = props.get("email").get(0);
    if (!expectedEmail.equals(email)) {
      throw new IOException("credentials don't match current user email");
    }
    String host = props.get("host").get(0);
    if (!expectedHost.equals(host)) {
      throw new IOException("credentials don't match current host");
    }

    List<Cookie> result = new ArrayList<Cookie>();
    for (String line : props.get("cookie")) {
      result.add(parseCookie(line, host));
    }
    return result;
  }

  private static Cookie parseCookie(String line, String host) throws IOException {
    int firstEqual = line.indexOf('=');
    if (firstEqual < 1) {
      throw new IOException("invalid cookie in credentials");
    }
    String key = line.substring(0, firstEqual);
    String value = line.substring(firstEqual + 1);
    Cookie cookie = new Cookie(host, key, value);
    cookie.setPath("/");
    return cookie;
  }

  private static void checkOneProperty(Map<String, List<String>> props, String key)
      throws IOException {
    if (props.get(key).size() != 1) {
      String message = "invalid credential file (should have one property named '" + key + "')";
      throw new IOException(message);
    }
  }

  private static Map<String, List<String>> parseProperties(String serializedCredentials) {
    Map<String, List<String>> props = new HashMap<String, List<String>>();
    for (String line : serializedCredentials.split("\n")) {
      line = line.trim();
      if (!line.startsWith("#") && line.contains("=")) {
        int firstEqual = line.indexOf('=');
        String key = line.substring(0, firstEqual);
        String value = line.substring(firstEqual + 1);
        List<String> values = props.get(key);
        if (values == null) {
          values = new ArrayList<String>();
          props.put(key, values);
        }
        values.add(value);
      }
    }
    return props;
  }
}
