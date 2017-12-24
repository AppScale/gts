package com.google.appengine.tools.development;

import java.util.Set;

public class ApiProxyLocalFactory {
    LocalServerEnvironment localServerEnvironment;

    public ApiProxyLocal create(LocalServerEnvironment localServerEnvironment) {
        return new ApiProxyLocalImpl(localServerEnvironment);
    }

    public ApiProxyLocal create(LocalServerEnvironment localServerEnvironment, Set apisUsingPythonStubs) {
        return ApiProxyLocalImpl.getApiProxyLocal(localServerEnvironment, apisUsingPythonStubs);
    }
}
