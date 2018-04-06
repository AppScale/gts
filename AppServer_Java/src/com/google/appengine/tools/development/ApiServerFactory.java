package com.google.appengine.tools.development;

public class ApiServerFactory {
    private static ApiServer instance;
    private static ApiServer externalServer;

    public static ApiServer getApiServer(String pathToApiServer) {
        if (instance == null) {
            instance = new ApiServer(pathToApiServer);
            addShutdownHook(instance);
        }

        return instance;
    }

    public static ApiServer getApiServer(int externalServerPort) {
        if (externalServer == null) {
            externalServer = new ApiServer(externalServerPort);
        }

        return externalServer;
    }

    private static void addShutdownHook(final ApiServer apiServer) {
        Runtime.getRuntime().addShutdownHook(new Thread() {
            public void run() {
                apiServer.close();
            }
        });
    }
}
