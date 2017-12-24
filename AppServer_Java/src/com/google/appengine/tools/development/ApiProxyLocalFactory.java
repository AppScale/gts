package com.google.appengine.tools.development;

public class ApiProxyLocalFactory {
    LocalServerEnvironment localServerEnvironment;

    public ApiProxyLocal create(LocalServerEnvironment localServerEnvironment) {
        return new ApiProxyLocalImpl(localServerEnvironment);
    }
}
