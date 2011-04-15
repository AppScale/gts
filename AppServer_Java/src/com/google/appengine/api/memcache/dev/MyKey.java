package com.google.appengine.api.memcache.dev;

import java.io.Serializable;
import java.util.Arrays;

public class MyKey implements Serializable {
	private static final long serialVersionUID = 8617042543853952415L;
	private byte[] Key2val;

	public MyKey(byte[] paramArrayOfByte) {
		this.Key2val = paramArrayOfByte;
	}

	public byte[] getBytes() {
		return this.Key2val;
	}

	public boolean equals(Object other) {
		if (other instanceof MyKey)
			return Arrays.equals(this.Key2val, ((MyKey) other).Key2val);
		if (other instanceof byte[]) {
			return Arrays.equals(this.Key2val, (byte[]) (byte[]) other);
		}
		return false;
	}

	public int hashCode() {
		return Arrays.hashCode(this.Key2val);
	}
}
