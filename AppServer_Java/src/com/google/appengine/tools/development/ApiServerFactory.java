package com.google.appengine.tools.development;

public class ApiServerFactory {
    private static ApiServer instance;

    public static ApiServer getApiServer(String pathToApiServer) {
        if (instance == null) {
            instance = new ApiServer(pathToApiServer);
            addShutdownHook(instance);
        }

        return instance;
    }

    private static void addShutdownHook(final ApiServer apiServer) {
        Runtime.getRuntime().addShutdownHook(new Thread() {
            public void run() {
                apiServer.close();
            }
        });
    }
}
