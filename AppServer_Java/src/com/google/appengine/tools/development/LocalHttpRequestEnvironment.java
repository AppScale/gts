package com.google.appengine.tools.development;

import java.util.logging.Level;
import java.util.logging.Logger;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.users.dev.LoginCookieUtils;
import com.google.apphosting.utils.config.AppEngineWebXml;

/**
 * {@code LocalHttpRequestEnvironment} is a simple {@link LocalEnvironment} that
 * retrieves authentication details from the cookie that is maintained by the
 * stub implementation of {@link UserService}.
 * 
 */

class LocalHttpRequestEnvironment extends LocalEnvironment {
    private static final Logger logger = Logger.getLogger(LocalHttpRequestEnvironment.class.getName());
    /**
     * The name of the HTTP header specifying the default namespace for API
     * calls.
     */

    static final String DEFAULT_NAMESPACE_HEADER = "X-AppEngine-Default-Namespace";
    static final String CURRENT_NAMESPACE_HEADER = "X-AppEngine-Current-Namespace";
    private static final String CURRENT_NAMESPACE_KEY = NamespaceManager.class.getName() + ".currentNamespace";

    private static final String APPS_NAMESPACE_KEY = NamespaceManager.class.getName() + ".appsNamespace";
    private static final String USER_ID_KEY = "com.google.appengine.api.users.UserService.user_id_key";
    private static final String USER_ORGANIZATION_KEY = "com.google.appengine.api.users.UserService.user_organization";
    private LoginCookieUtils.AppScaleCookieData loginCookieData = null;

    private static final String COOKIE_NAME = "dev_appserver_login";

    public LocalHttpRequestEnvironment(AppEngineWebXml appEngineWebXml, HttpServletRequest request) {
        super(appEngineWebXml);
        this.loginCookieData = LoginCookieUtils.getCookieData(request);
        if (this.loginCookieData == null) {
            logger.log(Level.FINE, "cookie is null, this user is not logged in");
        } else if (!this.loginCookieData.isValid()) {
            clearCookie(request);
            logger.log(Level.FINE, "cookie is not valid: " + this.loginCookieData.toString());
            loginCookieData = null;
        } else {
            logger.log(Level.FINE, "get valid cookie for: " + loginCookieData.getUserId() + "admin: "
                    + loginCookieData.isAdmin());
        }
        String requestNamespace = request.getHeader(DEFAULT_NAMESPACE_HEADER);
        if (requestNamespace != null) {
            this.attributes.put(APPS_NAMESPACE_KEY, requestNamespace);
        }
        String currentNamespace = request.getHeader(CURRENT_NAMESPACE_HEADER);
        if (currentNamespace != null) {
            this.attributes.put(CURRENT_NAMESPACE_KEY, currentNamespace);
        }
        if (this.loginCookieData != null) {
            this.attributes.put(USER_ID_KEY, this.loginCookieData.getUserId());
            this.attributes.put(USER_ORGANIZATION_KEY, "");
        }
    }

    public boolean isLoggedIn() {
        return (this.loginCookieData != null && this.loginCookieData.isValid());
    }

    public String getEmail() {
        if (this.loginCookieData == null) {
            return null;
        }
        return this.loginCookieData.getEmail();
    }

    public boolean isAdmin() {
        return (this.loginCookieData != null && this.loginCookieData.isAdmin());
    }

    private void clearCookie(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (cookie.getName().equals(COOKIE_NAME)) {
                    System.out.println("removing");
                    logger.log(Level.FINE, "removing cookie: " + cookie.getName() + ":" + cookie.getValue());
                    cookie.setMaxAge(0);
                    cookie.setPath("/");
                }
            }
        }
    }
}