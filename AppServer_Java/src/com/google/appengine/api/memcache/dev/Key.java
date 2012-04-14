package com.google.appengine.api.memcache.dev;

import java.util.Arrays;

public class Key {
    private byte[] keyval;

    public Key(byte[] bytes) {
        this.keyval = bytes;
    }

    public byte[] getBytes() {
        return this.keyval;
    }

    public boolean equals(Object other) {
        if ((other instanceof Key))
            return Arrays.equals(this.keyval, ((Key) other).keyval);
        if ((other instanceof byte[])) {
            return Arrays.equals(this.keyval, (byte[]) (byte[]) other);
        }
        return false;
    }

    public int hashCode() {
        return Arrays.hashCode(this.keyval);
    }
}