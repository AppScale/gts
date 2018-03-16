package com.google.appengine.tools.development;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLStreamHandler;
import java.net.URLStreamHandlerFactory;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Logger;

public final class StreamHandlerFactory
        implements URLStreamHandlerFactory {
    private static final Method GET_URL_STREAM_HANDLER;
    private static boolean factoryIsInstalled;

    static {
        Method m = null;
        try {
            m = URL.class.getDeclaredMethod("getURLStreamHandler", String.class);
            m.setAccessible(true);
        } catch (final NoSuchMethodException e) {
            Logger.getLogger(StreamHandlerFactory.class.getName()).info("Unable to register default URLStreamHandlers. "
                    + "You will be unable to access http and https URLs outside the App Engine environment.");
        }
        GET_URL_STREAM_HANDLER = m;
    }

    private final Map<String, URLStreamHandler> handlers = new HashMap<String, URLStreamHandler>();

    private StreamHandlerFactory() {
        for (final String protocol : Arrays.asList("http", "https")) {
            final URLStreamHandler fallbackHandler = StreamHandlerFactory.getFallbackStreamHandler(protocol);
            this.handlers.put(protocol, new LocalURLFetchServiceStreamHandler(fallbackHandler));
        }
    }

    /*
     * WARNING - Removed try catching itself - possible behaviour change.
     */
    public static void install() {
        System.out.println("App Engine URL Handler disabled!");
    }

    private static URLStreamHandler getFallbackStreamHandler(final String protocol) {
        if (GET_URL_STREAM_HANDLER == null) {
            return null;
        }
        final URLStreamHandler existingHandler = (URLStreamHandler) StreamHandlerFactory.invoke(null, GET_URL_STREAM_HANDLER, protocol);
        if (existingHandler.getClass().getName().equals(LocalURLFetchServiceStreamHandler.class.getName())) {
            final Method getFallbackHandler = StreamHandlerFactory.getDeclaredMethod(existingHandler.getClass(), "getFallbackHandler");
            return (URLStreamHandler) StreamHandlerFactory.invoke(existingHandler, getFallbackHandler);
        }
        return existingHandler;
    }

    static /* varargs */ Object invoke(final Object target, final Method m, final Object... args) {
        try {
            return m.invoke(target, args);
        } catch (final IllegalAccessException e) {
            throw new RuntimeException(e);
        } catch (final InvocationTargetException e) {
            if (e.getTargetException() instanceof RuntimeException) {
                throw (RuntimeException) e.getTargetException();
            }
            throw new RuntimeException(e.getTargetException());
        }
    }

    static /* varargs */ Method getDeclaredMethod(final Class<?> cls, final String methodName, final Class<?>... args) {
        try {
            final Method m = cls.getDeclaredMethod(methodName, args);
            m.setAccessible(true);
            return m;
        } catch (final NoSuchMethodException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public URLStreamHandler createURLStreamHandler(final String protocol) {
        return this.handlers.get(protocol);
    }
}
