package com.google.appengine.api.memcache.dev;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;

public class STest {

	public static boolean test(Object o) throws IOException {
		ByteArrayOutputStream out = new ByteArrayOutputStream();
		ObjectOutputStream oos = new ObjectOutputStream(out);
		oos.writeObject(o);
		oos.close();
		if (out.toByteArray().length > 0)
			return true;
		else
			return false;

	}

	public static void main(String[] args) {
		byte[] key = new byte[] { 'h', 'e', 'l', 'l', 'o' };
		MyKey k = new MyKey(key);
		CacheEntry c = new CacheEntry("hello", k, new byte[0], 100, 10000);
		try {
			System.out.println("entry: "+STest.test(c));
			System.out.println("key: "+STest.test(new String("__" +  "__" + "a" + "__"
					+ new String(k.getBytes()))));
			
		} catch (IOException e) {
			e.printStackTrace();
		}
		System.out.println(new String(key));

	}

}
