package com.google.appengine.api.users.dev;


import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
/*
 * AppScale -- added two imports
 */
import java.util.logging.Logger;
import java.util.logging.Level;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;


public final class LoginCookieUtils
{
    public static final String  COOKIE_PATH             = "/";
    public static final String  COOKIE_NAME             = "dev_appserver_login";
    private static final int    COOKIE_AGE              = -1;
    private final static String SHA                     = "SHA";
    private final static String MD5                     = "MD5";
    private static final String EMAIL_PREPEND           = "1";
    private static final String APPLICATION_ID_PROPERTY = "APPLICATION_ID";
    private static final String COOKIE_SECRET_PROPERTY  = "COOKIE_SECRET";

    /*
     * AppScale -- added next two final variables
     */
    private static final Logger logger                  = Logger.getLogger(LoginCookieUtils.class.getName());
    // used for parsing cookie
    private static final String hextab                  = "0123456789abcdef";

    /*
     * AppScale -- replaced method body -- should not be called b/c
     * AppDashboard handles this now, this method is not called
     * so adding Exception to catch when it is
     */
    public static Cookie createCookie( String email, boolean isAdmin )
    {
        if (true) throw new UnsupportedOperationException("Unexpected code path: createCookie(String,boolean) in LoginCookieUtils.");
        String userId = encodeEmailAsUserId(email);
        Cookie cookie = new Cookie("dev_appserver_login", email + ":" + isAdmin + ":" + userId);
        cookie.setPath(COOKIE_PATH);
        cookie.setMaxAge(COOKIE_AGE);
        logger.warning("Creating cookie by original jetty server, should be done by AppDashboard");
        logger.warning("Cookie is: " + cookie.toString());
        return cookie;
    }

    /*
     * AppScale -- replaced method body this method should not be called b/c
     * AppDashboard handles this now Chandra says: but it is called when a
     * login route is requested when cookie is null (so throw exception on an
     * attemp to remove a valid cookie) If these are not the semantics we want,
     * then replace this method so that it is correct.
     */
    public static void removeCookie( HttpServletRequest req, HttpServletResponse resp )
    {
        Cookie cookie = findCookie(req);
        if (cookie != null)
        {
            if (true) throw new UnsupportedOperationException("Unexpected code path: removeCookie(String,boolean) in LoginCookieUtils.");
            cookie.setPath("/");
            cookie.setMaxAge(0);
            resp.addCookie(cookie);
            logger.warning("Revoking cookie by original jetty server, should be done by AppDashboard");
            logger.warning("Cookie is: " + cookie.toString());
        }
        else
        {
            logger.info("DevAppServer/jetty server LoginCookieUtils removeCookie on null cookie (as expected)");
        }
    }

    public static AppScaleCookieData getCookieData( HttpServletRequest req )
    {
        Cookie cookie = findCookie(req);
        if (cookie == null)
        {
            return null;
        }
        return parseCookie(cookie);
    }

    public static String encodeEmailAsUserId( String email )
    {
        try
        {
            MessageDigest md5 = MessageDigest.getInstance(MD5);
            md5.update(email.toLowerCase().getBytes());
            StringBuilder builder = new StringBuilder();
            builder.append(EMAIL_PREPEND);
            for (byte b : md5.digest())
            {
                builder.append(String.format("%02d", new Object[] { Integer.valueOf(b & 0xFF) }));
            }
            return builder.toString().substring(0, 20);
        }
        catch (NoSuchAlgorithmException ex)
        {
        }
        return "";
    }

    /*
     * AppScale - replaced method
     */
    private static AppScaleCookieData parseCookie( Cookie cookie )
    {
        String value = cookie.getValue();
        // replace chars
        value = value.replace("%3A", ":");
        value = value.replace("%40", "@");
        value = value.replace("%2C", ",");
        String[] parts = value.split(":");
        if (parts.length < 4)
        {
            logger.log(Level.SEVERE, "Invalid cookie");
            return new AppScaleCookieData("", false, "", false);
        }
        String email = parts[0];
        String nickname = parts[1];
        boolean admin = false;
        String adminList[] = parts[2].split(",");
        String curApp = System.getProperty(APPLICATION_ID_PROPERTY);
        if (curApp == null)
        {
            logger.log(Level.FINE, "Current app is not set when placing cookie!");
        }
        else
        {
            for (int i = 0; i < adminList.length; i++)
            {
                if (adminList[i].equals(curApp))
                {
                    // logger.log(Level.FINE, "set admin to true");
                    admin = true;
                }
            }
        }
        String hsh = parts[3];
        boolean valid_cookie = true;
        String cookie_secret = System.getProperty(COOKIE_SECRET_PROPERTY);
        if (cookie_secret == "")
        {
            return new AppScaleCookieData("", false, "", false);
        }
        if (email.equals(""))
        {
            nickname = "";
            admin = false;
        }
        else
        {
            try
            {
                MessageDigest sha = MessageDigest.getInstance(SHA);
                sha.update((email + nickname + parts[2] + cookie_secret).getBytes());
                StringBuilder builder = new StringBuilder();
                // padding 0
                for (byte b : sha.digest())
                {
                    byte tmphigh = (byte)(b >> 4);
                    tmphigh = (byte)(tmphigh & 0xf);
                    builder.append(hextab.charAt(tmphigh));
                    byte tmplow = (byte)(b & 0xf);
                    builder.append(hextab.charAt(tmplow));
                }
                String vhsh = builder.toString();
                if (!vhsh.equals(hsh))
                {
                    valid_cookie = false;
                }
                else
                {
                }
            }
            catch (NoSuchAlgorithmException e)
            {
                logger.log(Level.SEVERE, "Decoding cookie failed");
                return new AppScaleCookieData("", false, "", false);
            }
        }
        return new AppScaleCookieData(email, admin, nickname, valid_cookie);
    }

    private static Cookie findCookie( HttpServletRequest req )
    {
        Cookie[] cookies = req.getCookies();
        if (cookies != null)
        {
            for (Cookie cookie : cookies)
            {
                if (cookie.getName().equals("dev_appserver_login"))
                {
                    return cookie;
                }
            }
        }
        return null;
    }

    public static final class AppScaleCookieData
    {
        private final String  email;
        private final boolean isAdmin;
        private final String  nickname;
        private final boolean valid;

        public AppScaleCookieData( String email, boolean isAdmin, String nickname, boolean isValid )
        {
            this.email = email;
            this.isAdmin = isAdmin;
            this.nickname = nickname;
            this.valid = isValid;
        }

        public String getEmail()
        {
            return this.email;
        }

        public boolean isAdmin()
        {
            return this.isAdmin;
        }

        public String getUserId()
        {
            return this.nickname;
        }

        public boolean isValid()
        {
            return this.valid;
        }
    }
}
