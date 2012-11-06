package com.google.appengine.api.users.dev;


import java.io.IOException;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;


public final class LocalLogoutServlet extends HttpServlet
{
	private static final long	serialVersionUID	= 1L;

	public void doGet( HttpServletRequest req, HttpServletResponse resp ) throws IOException
	{
		String continueUrl = req.getParameter("continue");
		/*
		 * AppScale - removed code that removes cookies
		 */
		resp.sendRedirect(continueUrl);
	}
}
