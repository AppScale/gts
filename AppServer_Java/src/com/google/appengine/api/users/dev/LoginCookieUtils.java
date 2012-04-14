package com.google.appengine.api.users.dev;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.logging.Level;
import java.util.logging.Logger;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public final class LoginCookieUtils {
    public static final String COOKIE_PATH = "/";
    public static final String COOKIE_NAME = "dev_appserver_login";
    private static final int COOKIE_AGE = -1;
    private static final Logger logger = Logger.getLogger(LoginCookieUtils.class.getName());
    // used for parsing cookie
    private static final String hextab = "0123456789abcdef";

    /*
     * this method should not be called since load balancer create cookies
     */
    public static Cookie createCookie(String email, boolean isAdmin) {
        String userId = encodeEmailAsUserId(email);
        Cookie cookie = new Cookie("dev_appserver_login", email + ":" + isAdmin + ":" + userId);
        cookie.setPath(COOKIE_PATH);
        cookie.setMaxAge(COOKIE_AGE);
        logger.warning("creating cookie by original jetty server, should be done by AppLoadBalancer");
        logger.warning("cookie is: " + cookie.toString());
        return cookie;
    }

    /*
     * this method should not be called since load balancer revoke cookies
     */
    public static void removeCookie(HttpServletRequest req, HttpServletResponse resp) {
        Cookie cookie = findCookie(req);
        if (cookie != null) {
            cookie.setPath("/");
            cookie.setMaxAge(0);
            resp.addCookie(cookie);
            logger.warning("revoking cookie by original jetty server, should be done by AppLoadBalancer");
            logger.warning("cookie is: " + cookie.toString());
        }
    }

    public static AppScaleCookieData getCookieData(HttpServletRequest req) {
        Cookie cookie = findCookie(req);
        if (cookie == null) {
            return null;
        }
        return parseCookie(cookie);
    }

    public static String encodeEmailAsUserId(String email) {
        try {
            MessageDigest md5 = MessageDigest.getInstance("MD5");
            md5.update(email.toLowerCase().getBytes());
            StringBuilder builder = new StringBuilder();
            builder.append("1");
            for (byte b : md5.digest()) {
                builder.append(String.format("%02d", new Object[] { Integer.valueOf(b & 0xFF) }));
            }
            return builder.toString().substring(0, 20);
        } catch (NoSuchAlgorithmException ex) {
            logger.warning("encoding email failed");
        }
        return "";
    }

    private static AppScaleCookieData parseCookie(Cookie cookie) {
        String value = cookie.getValue();
        //logger.log(Level.FINE, "original cookie: " + value);
        // replace chars
        value = value.replace("%3A", ":");
        value = value.replace("%40", "@");
        value = value.replace("%2C", ",");
        //logger.log(Level.FINE, "cookie after replacement: " + value);
        String[] parts = value.split(":");
        if (parts.length < 4) {
            logger.log(Level.SEVERE, "invalid cookie");
            return new AppScaleCookieData("", false, "", false);
        }
        String email = parts[0];
        String nickname = parts[1];
        boolean admin = false;
        String adminList[] = parts[2].split(",");
        String curApp = System.getProperty("APPLICATION_ID");
        if (curApp == null) {
            logger.log(Level.FINE, "Current app is not set when placing cookie!");
        } else {
            for (int i = 0; i < adminList.length; i++) {
                if (adminList[i].equals(curApp)) {
                    //logger.log(Level.FINE, "set admin to true");
                    admin = true;
                }
            }
        }
        String hsh = parts[3];
        boolean valid_cookie = true;
        String cookie_secret = System.getProperty("COOKIE_SECRET");
        if (cookie_secret == "") {
            //logger.log(Level.SEVERE, "cookie_secret is not set");
            return new AppScaleCookieData("", false, "", false);
        }
        if (email.equals("")) {
            //logger.log(Level.FINE, "email is empty!");
            nickname = "";
            admin = false;
        } else {
            try {
                MessageDigest sha = MessageDigest.getInstance("SHA");
                sha.update((email + nickname + parts[2] + cookie_secret).getBytes());
                StringBuilder builder = new StringBuilder();
                // padding 0
                for (byte b : sha.digest()) {
                    byte tmphigh = (byte) (b >> 4);
                    tmphigh = (byte) (tmphigh & 0xf);
                    builder.append(hextab.charAt(tmphigh));
                    byte tmplow = (byte) (b & 0xf);
                    builder.append(hextab.charAt(tmplow));
                }
                String vhsh = builder.toString();
                if (!vhsh.equals(hsh)) {
                    //logger.warning("has not same: original: " + hsh + ", but expected: " + vhsh);
                    valid_cookie = false;
                } else {}
            } catch (NoSuchAlgorithmException e) {
                logger.log(Level.SEVERE, "Decoding cookie failed");
                return new AppScaleCookieData("", false, "", false);
            }
        }
        return new AppScaleCookieData(email, admin, nickname, valid_cookie);
    }

    private static Cookie findCookie(HttpServletRequest req) {
        Cookie[] cookies = req.getCookies();
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (cookie.getName().equals(COOKIE_NAME)) {
                    return cookie;
                }
            }
        }
        return null;
    }

    public static final class AppScaleCookieData {
        private final String email;
        private final boolean isAdmin;
        private final String nickname;
        private final boolean valid;

        public AppScaleCookieData(String email, boolean isAdmin, String nickname, boolean isValid) {
            this.email = email;
            this.isAdmin = isAdmin;
            this.nickname = nickname;
            this.valid = isValid;
        }

        public String getEmail() {
            return this.email;
        }

        public boolean isAdmin() {
            return this.isAdmin;
        }

        public String getUserId() {
            return this.nickname;
        }

        public boolean isValid() {
            return this.valid;
        }
    }
}
