package com.google.appengine.api.memcache.dev;

public interface Chainable<E> {
    public E getNewer();

    public E getOlder();

    public void setNewer(E paramE);

    public void setOlder(E paramE);
}