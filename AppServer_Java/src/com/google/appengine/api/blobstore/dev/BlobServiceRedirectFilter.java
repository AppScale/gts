package com.google.appengine.api.blobstore.dev;

import java.io.IOException;

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;

public class BlobServiceRedirectFilter implements Filter {

    @Override
    public void destroy() {

    }

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) throws IOException,
            ServletException {
        //System.out.println("in BlobServiceRedirect");
        //System.out.println("remote host: " + req.getRemoteAddr());
        //System.out.println("remote address: " + req.getRemoteAddr());
        //System.out.println("remote port: " + req.getRemotePort());
        chain.doFilter(req, res);

    }

    @Override
    public void init(FilterConfig arg0) throws ServletException {

    }

}
