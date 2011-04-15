package com.google.appengine.tools.development;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import com.google.appengine.api.users.dev.LoginCookieUtils;


import com.google.apphosting.utils.config.AppEngineWebXml;

class LocalHttpRequestEnvironment extends LocalEnvironment {
	private static final String DEFAULT_NAMESPACE_HEADER = "X-AppEngine-Default-Namespace";
	private static final String USER_ID_KEY = "com.google.appengine.api.users.UserService.user_id_key";
	private static final String USER_ORGANIZATION_KEY = "com.google.appengine.api.users.UserService.user_organization";
	private String requestNamespace;
	private static final String COOKIE_NAME = "dev_appserver_login";
	private LoginCookieUtils.MyCookieData loginCookieData = null;

	public LocalHttpRequestEnvironment(AppEngineWebXml appEngineWebXml,
			HttpServletRequest request) {
		super(appEngineWebXml);


		this.loginCookieData = LoginCookieUtils.getCookieData(request);
		if (this.loginCookieData == null)
			System.out.println("cookie is null, this user is not login");
		else {
			System.out.println("cookie is not null, this user's email is: "
					+ this.loginCookieData.getEmail() + " he/she is admin? "
					+ this.loginCookieData.isAdmin() + " with nickname: "
					+ this.loginCookieData.getNickName());
			if (!this.loginCookieData.isValid()) {
				System.out
						.println("in init cookie: cookie is not valid! remove it");
				clearCookie(request);
				loginCookieData = null;
			}
		}
		this.requestNamespace = request.getHeader(DEFAULT_NAMESPACE_HEADER);
		if (this.requestNamespace == null) {
			this.requestNamespace = "";
		}
		// request.
		// put nickname into hash ? or email is better?
		if (this.loginCookieData != null)
			this.attributes.put(
					USER_ID_KEY,
					this.loginCookieData.getNickName());
		this.attributes.put(
				USER_ORGANIZATION_KEY,
				"");

	}

	private void clearCookie(HttpServletRequest request) {
		Cookie[] cookies = request.getCookies();
		if (cookies != null) {
			for (Cookie cookie : cookies) {
				System.out.println(cookie.getName() + ":" + cookie.getValue());
				if (cookie.getName().equals(COOKIE_NAME)) {
					System.out.println("removing");
					// cookie = null;
					cookie.setMaxAge(0);
					cookie.setPath("/");
				}
			}
		}
		if (cookies != null) {
			for (Cookie cookie : cookies) {
				System.out.println(cookie.getName() + ":" + cookie.getValue());
				if (cookie.getName().equals(COOKIE_NAME)) {
					System.out.println("removing");
					// cookie = null;
					cookie.setMaxAge(0);
					cookie.setPath("/");

				}
			}
		}
	}

	public boolean isLoggedIn() {
		if (this.loginCookieData != null) {
			System.out.println("user data is not null");
			if (this.loginCookieData.isValid())
				return true;
			else {
				System.out.println("invalid should cookie remove it!");
				return false;
			}
		}
		return false;
	}

	public String getEmail() {
		if (this.loginCookieData == null) {
			return null;
		}
		return this.loginCookieData.getEmail();
	}

	public boolean isAdmin() {
		if (this.loginCookieData == null) {
			return false;
		}
		return this.loginCookieData.isAdmin();
	}

	public String getRequestNamespace() {
		return this.requestNamespace;
	}
}