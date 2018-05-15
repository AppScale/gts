package com.google.appengine.tools.development;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.protobuf.Message;
import com.google.appengine.repackaged.com.google.protobuf.MessageLite;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

public class ApiUtils {
    public static <T> T convertBytesToPb(byte[] bytes, Class<T> messageClass) throws IllegalAccessException, InstantiationException, InvocationTargetException, NoSuchMethodException {
        if (ProtocolMessage.class.isAssignableFrom(messageClass)) {
            ProtocolMessage<?> proto = (ProtocolMessage)messageClass.getConstructor().newInstance();
            boolean parsed = proto.mergeFrom(bytes);
            if (parsed && proto.isInitialized()) {
                return messageClass.cast(proto);
            } else {
                String messageType = String.valueOf(classDescription(messageClass));
                String error = "Could not parse request bytes into ".concat(messageType);
                throw new RuntimeException(error);
            }
        } else if (Message.class.isAssignableFrom(messageClass)) {
            Method method = messageClass.getMethod("parseFrom", byte[].class);
            return messageClass.cast(method.invoke((Object)null, bytes));
        } else {
            throw new UnsupportedOperationException(String.format("Cannot assign %s to either %s or %s", classDescription(messageClass), ProtocolMessage.class, Message.class));
        }
    }

    public static byte[] convertPbToBytes(Object object) {
        if (object instanceof MessageLite) {
            return ((MessageLite)object).toByteArray();
        } else {
            throw new UnsupportedOperationException(String.format("%s is neither %s nor %s", classDescription(object.getClass()), ProtocolMessage.class, Message.class));
        }
    }

    private static String classDescription(Class<?> klass) {
        return String.format("(%s extends %s loaded from %s)", klass, klass.getSuperclass(), klass.getProtectionDomain().getCodeSource().getLocation());
    }
}
