package com.google.appengine.api.users.dev;

import java.io.IOException;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public final class LocalLoginServlet extends HttpServlet {

	private static final long serialVersionUID = 3436539147212984827L;
	private static final String login_server = System
			.getProperty("LOGIN_SERVER");
	private static final String CONTINUE_PARAM = "continue";

	public void doGet(HttpServletRequest req, HttpServletResponse resp)
			throws IOException {

		// String continueUrl = req.getParameter("continue");
		// String email = "test@example.com";
		// String isAdminChecked = "";
		// LoginCookieUtils.CookieData cookieData = LoginCookieUtils
		// .getCookieData(req);
		// if (cookieData != null) {
		// email = cookieData.getEmail();
		// if (cookieData.isAdmin()) {
		// isAdminChecked = " checked='true'";
		// }
		// }
		// resp.setContentType("text/html");
		//
		// PrintWriter out = resp.getWriter();
		// out.println("<html>");
		// out.println("<body>");
		// out
		// .println("<form method='post' style='text-align:center; font:13px sans-serif'>");
		//
		// out
		// .println("<div style='width: 20em; margin: 1em auto; text-align: left; padding: 0 2em 1.25em 2em; background-color: #d6e9f8; border: 2px solid #67a7e3'>");
		//
		// out.println("<h3>Not logged in</h3>");
		// out.println("<p style='padding: 0; margin: 0'>");
		// out.println("<label for='email' style='width: 3em'>Email:</label>");
		// out.println(" <input type='text' name='email' id='email'value='"
		// + email + "'>");
		// out.println("</p>");
		// out.println("<p style='margin: .5em 0 0 3em; font-size:12px'>");
		// out.println("<input type='checkbox' name='isAdmin' id='isAdmin'"
		// + isAdminChecked + ">");
		// out.println(" <label for='isAdmin'>Sign in as Administrator</label>");
		// out.println("</p>");request.toFlatString
		// out.println("<input type='hidden' name='continue' value='"
		// + continueUrl + "'>");
		//
		// out.println("<p style='margin-left: 3em;'>");
		// out.println("<input name='action' type='submit' value='Log In'>");
		// out.println("<input name='action' type='submit' value='Log Out'>");
		// out.println("</p>");
		// out.println("</div>");
		// out.println("</form>");
		// out.println("</body>");
		// out.println("</html>");
		LoginCookieUtils.removeCookie(req, resp);

		String login_service_endpoint = "http://" + login_server + "/login";
		// if (debug)
		System.out.println("login_service: " + login_service_endpoint);
		String continue_url = req.getParameter("continue");
		// String host = "http://"+System.getProperty("MY_IP_ADDRESS");
		String host = "http://" + System.getProperty("NGINX_ADDR");
		// if (debug)
		System.out.println("host: " + host);
		// if(!System.getProperty("MY_PORT").equals("80"))
		// host = host + ":" + System.getProperty("MY_PORT");
		if (!System.getProperty("NGINX_PORT").equals("80"))
			host = host + ":" + System.getProperty("NGINX_PORT");
		String ah_path = System.getProperty("PATH_INFO");
		String ah_login_url = host;
		if (ah_path != null)
			ah_login_url += ah_path;
		String redirect_url = login_service_endpoint + "?" + CONTINUE_PARAM
				+ "=" + ah_login_url + "?" + CONTINUE_PARAM + "="
				+ continue_url;
		redirect_url.replace(":", "%3A");
		redirect_url.replace("?", "%3F");
		redirect_url.replace("=", "%3D");
		System.out.println("redirect url: " + redirect_url);
		resp.sendRedirect(redirect_url);
	}

	public void doPost(HttpServletRequest req, HttpServletResponse resp)
			throws IOException {
		// String continueUrl = req.getParameter("continue");
		// String email = req.getParameter("email");
		// boolean logout =
		// "Log Out".equalsIgnoreCase(req.getParameter("action"));
		// boolean isAdmin = "on".equalsIgnoreCase(req.getParameter("isAdmin"));
		//
		// if (logout) {
		// LoginCookieUtils.removeCookie(req, resp);
		// } else {
		// resp.addCookie(LoginCookieUtils.createCookie(email, isAdmin));
		// }
		//
		// resp.sendRedirect(continueUrl);
	}
}