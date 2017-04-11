package com.google.appengine.api.modules;

/**
 * User: uglitskih
 * Date: 07.11.16
 * Time: 21:34
 */
public class ModulesException extends RuntimeException {
    public ModulesException(final String message) {
        super(message);
    }

    public ModulesException(final String message, final Throwable cause) {
        super(message, cause);
    }
}
