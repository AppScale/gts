package com.google.appengine.api.modules;

public final class ModulesServiceFactory {
    private ModulesServiceFactory() {
    }

    public static ModulesService getModulesService() {
        return new ModulesServiceImpl();
    }
}
