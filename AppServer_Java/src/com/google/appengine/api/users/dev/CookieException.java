package com.google.appengine.api.users.dev;

public class CookieException extends Exception {

	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;
	private String msg;
	public CookieException(String string) {
		this.msg = string;
	}
	@Override
	public String getMessage() {
		return super.getMessage()+" "+msg;
	}
	
	
	
}
