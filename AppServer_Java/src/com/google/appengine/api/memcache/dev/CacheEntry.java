package com.google.appengine.api.memcache.dev;

import java.io.Serializable;

public class CacheEntry implements Serializable {
    /**
         * 
         */
    private static final long serialVersionUID = -1644795290406463950L;
    private byte[] value;
    private int flags;

    public byte[] getValue() {
        return value;
    }

    public void setValue(byte[] value) {
        this.value = value;
    }

    public int getFlags() {
        return flags;
    }

    public void setFlags(int flags) {
        this.flags = flags;
    }

    public long getExpires() {
        return expires;
    }

    public void setExpires(long expires) {
        this.expires = expires;
    }

    public long getAccess() {
        return access;
    }

    public void setAccess(long access) {
        this.access = access;
    }

    private long expires;
    private long access;

    // cas id is not need since it is managed in memcached server
    // public Long casId;

    public CacheEntry(String namespace, byte[] value, int flags, long expiration, long accessTime)
            throws IllegalArgumentException {
        this.value = value;
        this.flags = flags;
        this.expires = expiration;
        this.access = accessTime;
    }

    // public int compareTo(CacheEntry entry) {
    // return this.access == entry.access ? 0 : this.access < entry.access ?
    // -1 : 1;
    // }
}