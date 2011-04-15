package com.google.appengine.api.memcache.dev;

public interface Chainable<E> {
	public abstract Chainable<E> getNewer();

	public abstract Chainable<E> getOlder();

	public abstract void setNewer(Chainable<E> paramE);

	public abstract void setOlder(Chainable<E> paramE);
}
