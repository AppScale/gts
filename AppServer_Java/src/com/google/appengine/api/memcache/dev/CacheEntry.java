package com.google.appengine.api.memcache.dev;

import java.io.Serializable;

import com.google.appengine.api.memcache.dev.LRU.AbstractChainable;

public class CacheEntry extends AbstractChainable<CacheEntry> implements
Serializable

{
	private static final long serialVersionUID = 333762892964231596L;
	public String namespace;
	public MyKey key;
	public byte[] value;
	int flags;
	public long expires;
	public long access;
	public long bytes;

	public CacheEntry(String paramString, MyKey paramKey2,
			byte[] paramArrayOfByte, int paramInt, long paramLong)
			throws IllegalArgumentException {
		this.namespace = paramString;
		this.key = paramKey2;
		this.value = paramArrayOfByte;
		this.flags = paramInt;
		this.expires = paramLong;
		this.access = System.currentTimeMillis();
		this.bytes = (paramKey2.getBytes().length + paramArrayOfByte.length);
	}
}