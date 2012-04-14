package com.google.appengine.api.users.dev;

import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public final class LocalLoginServlet extends HttpServlet {
    private static final Logger logger = Logger.getLogger(LocalLoginServlet.class.getName());
    private static final long serialVersionUID = 1L;
    private static final String login_server = System.getProperty("LOGIN_SERVER");
    private static final String CONTINUE_PARAM = "continue";

    public void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        LoginCookieUtils.removeCookie(req, resp);
        String login_service_endpoint = "http://" + login_server + "/login";
        // logger.log(Level.FINE, "login_service: " + login_service_endpoint);
        //logger.info("login_service: " + login_service_endpoint);

        String continue_url = req.getParameter("continue");
        String host = "http://" + System.getProperty("NGINX_ADDR");
        //logger.log(Level.FINE, "host: " + host);
        //logger.info("host: " + host);
        if (!System.getProperty("NGINX_PORT").equals("80"))
            host = host + ":" + System.getProperty("NGINX_PORT");
        String ah_path = System.getProperty("PATH_INFO");
        String ah_login_url = host;
        if (ah_path != null)
            ah_login_url += ah_path;
        String redirect_url = login_service_endpoint + "?" + CONTINUE_PARAM + "=" + ah_login_url + "?" + CONTINUE_PARAM
                + "=" + continue_url;
        redirect_url.replace(":", "%3A");
        redirect_url.replace("?", "%3F");
        redirect_url.replace("=", "%3D");
        //logger.log(Level.FINE, "redirect url: " + redirect_url);
        //logger.info("redirect url: " + redirect_url);
        resp.sendRedirect(redirect_url);
    }

    public void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
    }
}
