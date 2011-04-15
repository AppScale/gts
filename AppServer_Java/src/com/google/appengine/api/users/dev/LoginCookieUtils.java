package com.google.appengine.api.users.dev;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public final class LoginCookieUtils {
	private static final String COOKIE_PATH = "/";
	private static final String COOKIE_NAME = "dev_appserver_login";
	private static final int COOKIE_AGE = -1;

	private static String hextab = "0123456789abcdef";

	public static Cookie createCookie(String email, boolean isAdmin) {
		String userId = encodeEmailAsUserId(email);
		System.out
				.println("Error: creating data by original jetty server, should be done by AppLoadBalancer!");
		Cookie cookie = new Cookie("dev_appserver_login", email + ":" + isAdmin
				+ ":" + userId);
		cookie.setPath(COOKIE_PATH);
		cookie.setMaxAge(COOKIE_AGE);
		return cookie;
	}

	/**
	 * this method should never be called since AppLofindCookieadBalancer
	 * handles cookie revocation
	 */
	public static void removeCookie(HttpServletRequest req,
			HttpServletResponse resp) {
		Cookie cookie = findCookie(req);
		if (cookie == null) {
			return;
		}
		System.out.println("cookie removed!");
		cookie.setPath(COOKIE_PATH);

		cookie.setMaxAge(0);

		resp.addCookie(cookie);
	}

	/**
	 * used by appscale to get the data in cookie
	 */
	public static MyCookieData getCookieData(HttpServletRequest req) {
		Cookie cookie = findCookie(req);
		if (cookie == null) {
			return null;
		}
		try {
			return parseCookie(cookie);
		} catch (CookieException e) {
			e.printStackTrace();
			return null;
		}
	}

	static String encodeEmailAsUserId(String email) {
		try {
			MessageDigest md5 = MessageDigest.getInstance("MD5");
			md5.update(email.toLowerCase().getBytes());
			StringBuilder builder = new StringBuilder();
			builder.append("1");
			for (byte b : md5.digest()) {
				builder.append(String.format("%02d", new Object[] { Integer
						.valueOf(b & 0xFF) }));
			}
			return builder.toString().substring(0, 20);
		} catch (NoSuchAlgorithmException ex) {
		}
		return "";
	}

	private static MyCookieData parseCookie(Cookie cookie)
			throws CookieException {
		String value = cookie.getValue();
		// ***** original code of GAEJ *****//
		// String[] parts = value.split(":");
		// String userId = null;
		// if (parts.length > 2) {
		// userId = parts[2];
		// }
		// return new CookieData(parts[0],
		// Boolean.parseBoolean(parts[1]), userId);
		// ***** start modification at Feb 18, 2010 : 12:31:29 AM , by Yiming Li
		// *****//
		System.out.println("original cookie: " + value);
		// replace chars
		value = value.replace("%3A", ":");
		value = value.replace("%40", "@");
		System.out.println("cookie after replacement: " + value);
		String[] parts = value.split(":");
		if (parts.length < 4)
			throw new CookieException("only " + parts.length
					+ " parts in the cookie! " + value);
		String email = parts[0];
		String nickname = parts[1];
		boolean admin = false;
		String adminList[] = parts[2].split(",");
		String curApp = System.getProperty("APPLICATION_ID");
		if (curApp == null) {
			System.out.println("current app is not set!");
		} else {
			for (int i = 0; i < adminList.length; i++) {
				if (adminList[i].equals(curApp)) {
					System.out.println("set admin to true");
					admin = true;
				}
			}
		}

		// boolean admin = Boolean.getBoolean(parts[2].toLowerCase());
		String hsh = parts[3];
		boolean valid_cookie = true;
		String cookie_secret = System.getProperty("COOKIE_SECRET");

		if (cookie_secret == "")
			throw new CookieException("cookie secret is not set");

		if (email.equals("")) {
			System.out.println("email is empty!");
			nickname = "";
			admin = false;
		} else {
			try {
				MessageDigest sha = MessageDigest.getInstance("SHA");
				sha.update((email + nickname + parts[2] + cookie_secret)
						.getBytes());
				StringBuilder builder = new StringBuilder();
				// padding 0
				for (byte b : sha.digest()) {
					// System.out.print(b);
					// if (b == 0x00){
					// builder.append("00");
					// continue;
					// }
					// if (b < 0xf)
					// builder.append("0");
					// builder.append(Integer.toHexString(b & 0xff));
					byte tmphigh = (byte) (b >> 4);
					tmphigh = (byte) (tmphigh & 0xf);
					builder.append(hextab.charAt(tmphigh));
					byte tmplow = (byte) (b & 0xf);
					builder.append(hextab.charAt(tmplow));

				}
				System.out.println();
				String vhsh = builder.toString();
				if (!vhsh.equals(hsh)) {
					System.out.println("hash not same!");
					System.out.println("hash passed in: " + hsh);
					System.out.println("hash generated: " + vhsh);
					valid_cookie = false;
				} else
					System.out.println("cookie match!");
			} catch (NoSuchAlgorithmException ex) {

			}
		}
		return new MyCookieData(email, admin, nickname, valid_cookie);
	}

	// ***** end modification *****//

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

	
	public static class MyCookieData {
		private final String email;
		private final boolean isAdmin;
		private final String nickName;
		private final boolean valid;

		public MyCookieData(String email, boolean isAdmin, String nickName,
				boolean valid) {
			this.email = email;
			this.isAdmin = isAdmin;
			this.nickName = nickName;
			this.valid = valid;
		}

		public String getEmail() {
			return email;
		}

		public boolean isAdmin() {
			return isAdmin;
		}

		public String getNickName() {
			return nickName;
		}

		public boolean isValid() {
			return valid;
		}

	}

}

/*
 * Location:
 * C:\Users\nicneo\Desktop\appengine-java-sdk-1.3.1\appengine-java-sdk-
 * 1.3.1\lib\impl\appengine-api-stubs.jar Qualified Name:
 * com.google.appengine.api.users.dev.LoginCookieUtils JD-Core Version: 0.5.3
 */