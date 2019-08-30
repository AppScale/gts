package com.google.appengine.api.users.dev;


import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.util.Map;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;

import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.Environment;
import com.google.apphosting.api.UserServicePb;


@ServiceProvider(LocalRpcService.class)
public final class LocalUserService extends AbstractLocalRpcService
{
    /*
     * AppScale - every method in this class has been modified
     */
    private static final String LOGIN_URL    = "/_ah/login";
    public static final String  PACKAGE      = "user";
    private static final String LOGIN_SERVER = System.getProperty("LOGIN_SERVER");

    public static final String OAUTH_CONSUMER_KEY_PROPERTY = "oauth.consumer_key";
    public static final String OAUTH_EMAIL_PROPERTY = "oauth.email";
    public static final String OAUTH_USER_ID_PROPERTY = "oauth.user_id";
    public static final String OAUTH_AUTH_DOMAIN_PROPERTY = "oauth.auth_domain";
    public static final String OAUTH_IS_ADMIN_PROPERTY = "oauth.is_admin";
    private String oauthConsumerKey = "example.com";
    private String oauthEmail = "example@example.com";
    private String oauthUserId = "0";
    private String oauthAuthDomain = "gmail.com";
    private boolean oauthIsAdmin = false;
    private final String NGINX_ADDR = "NGINX_ADDR";
    private final String DASHBOARD_HTTPS_PORT = "1443";
    private final String apiProxyRequest = "com.google.appengine.http_servlet_request";
    private final String loginURLError = "Could not create URL for createLoginURL request!";
    private final String logoutURLError = "Could not create URL for createLogoutURL request!";


    public UserServicePb.CreateLoginURLResponse createLoginURL( LocalRpcService.Status status, UserServicePb.CreateLoginURLRequest request )
    {
        UserServicePb.CreateLoginURLResponse response = new UserServicePb.CreateLoginURLResponse();
        String destinationUrl = request.getDestinationUrl();
        if(destinationUrl != null && destinationUrl.startsWith("/"))
        {
            Environment env = ApiProxy.getCurrentEnvironment();
            if (env == null) {
                throw new RuntimeException(loginURLError);
            }
            HttpServletRequest req = (HttpServletRequest) env.getAttributes().get(apiProxyRequest);
            if (req == null) {
                throw new RuntimeException(loginURLError);
            }
            String host = req.getHeader("Host");
            String forwardedProto = req.getHeader("X-Forwarded-Proto");
            if (forwardedProto == null) {
              forwardedProto = "http";
            }
            if (host == null) {
                throw new RuntimeException(loginURLError);
            }

            // Construct the url.
            destinationUrl = forwardedProto + "://" + host + destinationUrl;
        }

        response.setLoginUrl(LOGIN_URL + "?continue=" + encode(destinationUrl));
        return response;
    }

    public UserServicePb.CreateLogoutURLResponse createLogoutURL( LocalRpcService.Status status, UserServicePb.CreateLogoutURLRequest request )
    {
        UserServicePb.CreateLogoutURLResponse response = new UserServicePb.CreateLogoutURLResponse();

        // Get the port we just came from.
        Environment env = ApiProxy.getCurrentEnvironment();
        if (env == null) {
            throw new RuntimeException(logoutURLError);
        }
        HttpServletRequest req = (HttpServletRequest) env.getAttributes().get(apiProxyRequest);
        if (req == null) {
            throw new RuntimeException(logoutURLError);
        }

        String host = req.getHeader("Host");
        String forwardedProto = req.getHeader("X-Forwarded-Proto");
        if (forwardedProto == null) {
          forwardedProto = "http";
        }
        if (host == null) {
            throw new RuntimeException(loginURLError);
        }

        // Construct the url.
        String destinationUrl = forwardedProto + "://" + host;

        String redirect_url = "https://" + LOGIN_SERVER + ":" + DASHBOARD_HTTPS_PORT + "/logout?continue=" + destinationUrl;
        response.setLogoutUrl(redirect_url);

        return response;
    }

    public UserServicePb.CheckOAuthSignatureResponse checkOAuthSignature( LocalRpcService.Status status, UserServicePb.CheckOAuthSignatureRequest request )
    {
        UserServicePb.CheckOAuthSignatureResponse response = new UserServicePb.CheckOAuthSignatureResponse();
        response.setOauthConsumerKey(this.oauthConsumerKey);
        return response;
    }

    public UserServicePb.GetOAuthUserResponse getOAuthUser( LocalRpcService.Status status, UserServicePb.GetOAuthUserRequest request )
    {
        UserServicePb.GetOAuthUserResponse response = new UserServicePb.GetOAuthUserResponse();
        response.setEmail(this.oauthEmail);
        response.setUserId(this.oauthUserId);
        response.setAuthDomain(this.oauthAuthDomain);
        response.setIsAdmin(this.oauthIsAdmin);

        return response;
    }

    public String getPackage()
    {
        return "user";
    }

    public void init( LocalServiceContext context, Map<String, String> properties )
    {
      String oauthConsumerKeyProp = (String)properties.get("oauth.consumer_key");
      if (oauthConsumerKeyProp != null) {
        this.oauthConsumerKey = oauthConsumerKeyProp;
      }
      String oauthEmailProp = (String)properties.get("oauth.email");
      if (oauthEmailProp != null) {
        this.oauthEmail = oauthEmailProp;
      }
      String oauthUserIdProp = (String)properties.get("oauth.user_id");
      if (oauthUserIdProp != null) {
        this.oauthUserId = oauthUserIdProp;
      }
      String oauthAuthDomainProp = (String)properties.get("oauth.auth_domain");
      if (oauthAuthDomainProp != null) {
        this.oauthAuthDomain = oauthAuthDomainProp;
      }
      String oauthIsAdminProp = (String)properties.get("oauth.is_admin");
      if (oauthIsAdminProp != null)
        this.oauthIsAdmin = Boolean.valueOf(oauthIsAdminProp).booleanValue();
    }

    public void start()
    {}

    public void stop()
    {}

    private static String encode( String url )
    {
        try
        {
            return URLEncoder.encode(url, "UTF-8");
        }
        catch (UnsupportedEncodingException ex)
        {
            throw new RuntimeException("Could not find UTF-8 encoding", ex);
        }
    }
}
