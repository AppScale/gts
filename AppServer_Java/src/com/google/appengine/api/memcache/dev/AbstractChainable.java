package com.google.appengine.api.memcache.dev;

public abstract class AbstractChainable<E> implements Chainable<E> {
    private E newer = null;
    private E older = null;

    public E getNewer() {
        return this.newer;
    }

    public E getOlder() {
        return this.older;
    }

    public void setNewer(E newer) {
        this.newer = newer;
    }

    public void setOlder(E older) {
        this.older = older;
    }
}