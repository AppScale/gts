package com.google.appengine.api.memcache.dev;

import java.io.BufferedReader;
import java.io.DataInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import net.spy.memcached.MemcachedClient;

import com.google.appengine.api.memcache.MemcacheServicePb;
import com.google.appengine.api.memcache.MemcacheServicePb.MemcacheSetResponse;
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiProxy;

@ServiceProvider(LocalRpcService.class)
public final class LocalMemcacheService implements LocalRpcService {
	public static final String PACKAGE = "memcache";
	private String appName = "";
	// public static final String SIZE_PROPERTY = "memcache.maxsize";
	// private static final String DEFAULT_MAX_SIZE = "100M";
	// private static final String UTF8 = "UTF-8";
	// private LRU lru;
	// private final Map<String, Map<Key, CacheEntry>> mockCache;
	// private final Map<String, Map<Key, Long>> deleteHold;
	// private long maxSize;
	private LocalStats stats;
	// private Clock clock;

	private MemcachedClient c = null;

	public LocalMemcacheService() {
		// this.lru = new LRU();
		// this.mockCache = new HashMap();
		// this.deleteHold = new HashMap();
		this.stats = new LocalStats(0L, 0L, 0L, 0L, 0L);
	}

	//
	// private <K1, K2, V> Map<K2, V> getOrMakeSubMap(Map<K1, Map<K2, V>> map,
	// K1 key) {
	// Map subMap = (Map)map.get(key);
	// if (subMap == null) {
	// subMap = new HashMap();
	// map.put(key, subMap);
	// }
	// return subMap;
	// }

	// private CacheEntry getWithExpiration(String namespace, Key key)
	// {
	// synchronized (this.mockCache) {
	// CacheEntry entry = (CacheEntry)getOrMakeSubMap(this.mockCache,
	// namespace).get(key);
	// if (entry != null) {
	// if ((entry.expires == 0L) || (this.clock.getCurrentTime() <
	// entry.expires)) {
	// entry.access = this.clock.getCurrentTime();
	// this.lru.update(entry);
	// return entry;
	// }
	//
	// getOrMakeSubMap(this.mockCache, namespace).remove(key);
	// this.lru.remove(entry);
	// this.stats.recordDelete(entry);
	// }
	// }
	// return null;
	// }

	// private CacheEntry internalDelete(String namespace, Key key)
	// {
	// CacheEntry ce;
	// synchronized (this.mockCache) {
	// ce = (CacheEntry)getOrMakeSubMap(this.mockCache, namespace).remove(key);
	// if (ce != null) {
	// this.lru.remove(ce);
	// }
	// }
	// return ce;
	// }

	private void internalSet(String namespace, MyKey key, CacheEntry entry) {
		// synchronized (this.mockCache) {
		// Map namespaceMap = getOrMakeSubMap(this.mockCache, namespace);
		// CacheEntry old = (CacheEntry)namespaceMap.get(key);
		// if (old != null) {
		// this.stats.recordDelete(old);
		// }
		// namespaceMap.put(key, entry);
		// this.lru.update(entry);
		// this.stats.recordAdd(entry);
		// }
		System.out.println("internal setting!");
		// testSerializable(entry);

		System.out.println("setting key: "
				+ new String("__" + appName + "__" + namespace + "__"
						+ new String(key.getBytes())) + " expire: "
				+ ((Long) entry.expires).intValue() + " entry: "
				+ entry.toString());
		System.out.println("old expire: " + entry.expires);

		int exp = (int) (entry.expires - System.currentTimeMillis()) / 1000 + 1;

		System.out.println("ready to set!");
		
		
		
		try{
		c.add(new String("__" + appName + "__" + namespace + "__"
				+ new String(key.getBytes())), exp, entry);
		}
		catch (Throwable t){
			System.out.println("problem!");
			t.printStackTrace();
		}
		System.out.println("internel set return!");
		
		
	}

	public String getPackage() {
		return "memcache";
	}

	public void init(LocalServiceContext context, Map<String, String> properties) {
		String warPath = context.getLocalServerEnvironment().getAppDir()
				.getAbsolutePath();
		String[] segs = warPath.split("/");
		if (segs.length <= 0)
			System.out.println("error finding app name!");
		else {
			for (int i = 0; i < segs.length; i++) {
				if (segs[i].equals("apps")) {
					appName = segs[i + 1];
				}
			}
		}
		// init spymemcached
		final List<InetSocketAddress> ipList = new ArrayList<InetSocketAddress>();

		System.out.println("initializing localmemservice");

		try {
			// Open the file that is the first
			// command line parameter
			ResourceLoader res = ResourceLoader.getResouceLoader();
			FileInputStream fstream = new FileInputStream(res
					.getMemcachedServerIp());
			// Get the object of DataInputStream
			DataInputStream in = new DataInputStream(fstream);
			BufferedReader br = new BufferedReader(new InputStreamReader(in));
			String strLine;
			// Read File Line By Line
			while ((strLine = br.readLine()) != null) {
				// Print the content on the console
				String ip = strLine;
				System.out.println("adding: " + strLine);
				if (isIp(ip))
					ipList.add(new InetSocketAddress(ip, 11211));
			}
			// Close the input stream
			in.close();
		} catch (Exception e) {// Catch exception if any
			System.err.println("Error: " + e.getMessage());
		}
		try {
			c = new MemcachedClient(ipList);

		} catch (IOException e) {
			e.printStackTrace();
		}
		System.out.println("connection to memcache server is established!");

		//		
		// // clock = context.getClock();
		// String propValue = (String) properties.get("memcache.maxsize");
		// if (propValue == null)
		// propValue = "100M";
		// else {
		// propValue = propValue.toUpperCase();
		// }
		// int multiplier = 1;
		// if ((propValue.endsWith("M")) || (propValue.endsWith("K"))) {
		// if (propValue.endsWith("M"))
		// multiplier = 1048576;
		// else {
		// multiplier = 1024;
		// }
		// propValue = propValue.substring(0, propValue.length() - 1);
		// }
		// try {
		// this.maxSize = (Long.parseLong(propValue) * multiplier);
		// } catch (NumberFormatException ex) {
		// throw new MemcacheServiceException("Can't parse cache size limit '"
		// + ((String) properties.get("memcache.maxsize")) + "'", ex);
		// }
	}

	public void setLimits(int bytes) {
		// this.maxSize = bytes;
	}

	public void start() {
	}

	public void stop() {
	}

	private boolean isIp(String ip) {
		String[] parts = ip.split("\\.");
		if (parts.length != 4)
			return false;
		for (String s : parts) {
			int i = Integer.parseInt(s);
			if (i < 0 || i > 255) {
				return false;
			}
		}
		return true;
	}

	public MemcacheServicePb.MemcacheGetResponse get(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheGetRequest req) {
		System.out.println("----in memcache get----");
		System.out.println("----flat string of getRequest: " + req.toString());

		MemcacheServicePb.MemcacheGetResponse.Builder result = MemcacheServicePb.MemcacheGetResponse
				.newBuilder();

		for (int i = 0; i < req.getKeyCount(); ++i) {
			MyKey key = new MyKey(req.getKey(i).toByteArray());
			System.out.println("internal getting");
			System.out.println("getting key: "
					+ new String("__" + appName + "__" + req.getNameSpace()
							+ "__" + new String(key.getBytes())));
			CacheEntry entry2 = (CacheEntry) c.get(new String("__" + appName
					+ "__" + req.getNameSpace() + "__" + new String(key.getBytes())));
			if (entry2 != null)
				result.addItem(MemcacheServicePb.MemcacheGetResponse.Item
						.newBuilder().setKey(
								ByteString.copyFrom(key.getBytes())).setFlags(
								entry2.flags).setValue(
								ByteString.copyFrom(entry2.value)).build());
		}

		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheGrabTailResponse grabTail(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheGrabTailRequest req) {
		MemcacheServicePb.MemcacheGrabTailResponse.Builder result = MemcacheServicePb.MemcacheGrabTailResponse
				.newBuilder();
		System.out.println("grabTail is not implemented!");
		// int itemCount;
		// synchronized (this.mockCache) {
		// Map map = getOrMakeSubMap(this.mockCache, req.getNameSpace());
		// List<CacheEntry> entries = new ArrayList<CacheEntry>(map.values());
		// Collections.sort(entries);
		//
		// itemCount = 0;
		// for (CacheEntry entry : entries) {
		// internalDelete(req.getNameSpace(), entry.key);
		// this.stats.recordHit(entry);
		// result.addItem(MemcacheServicePb.MemcacheGrabTailResponse.Item
		// .newBuilder().setFlags(entry.flags).setValue(
		// ByteString.copyFrom(entry.value)).build());
		//
		// ++itemCount;
		//
		// if (itemCount == req.getItemCount()) {
		// break;
		// }
		// }
		// }

		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheSetResponse set(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheSetRequest req) {
		MemcacheServicePb.MemcacheSetResponse.Builder result = MemcacheServicePb.MemcacheSetResponse
				.newBuilder();
		String namespace = req.getNameSpace();
		System.out.println("----in memcache set----");
		System.out.println("----flat string of setRequest: " + req.toString());

		for (int i = 0; i < req.getItemCount(); ++i) {
			MemcacheServicePb.MemcacheSetRequest.Item item = req.getItem(i);
			MyKey key = new MyKey(item.getKey().toByteArray());
			MemcacheServicePb.MemcacheSetRequest.SetPolicy policy = item
					.getSetPolicy();
			if (policy != MemcacheServicePb.MemcacheSetRequest.SetPolicy.SET) {
				long expiry = (item.hasExpirationTime()) ? item
						.getExpirationTime() : 0L;
				byte[] value = item.getValue().toByteArray();
				int flags = item.getFlags();

				CacheEntry ce = new CacheEntry(namespace, key, value, flags,
						expiry * 1000L);
				int exp = (int) (ce.expires - System.currentTimeMillis()) / 1000 + 1;
				if (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.REPLACE)
					c.replace(new String(key.getBytes()), exp, ce);
				else if (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.ADD)
					c.add(new String(key.getBytes()), exp, ce);
			} else {
				// /* 338 */ CacheEntry entry = getWithExpiration(namespace,
				// key);
				// // CacheEntry entry2 = (CacheEntry)c.get(new
				// String(key.getBytes()));
				// /* 339 */ if (((entry == null) && (policy ==
				// MemcacheServicePb.MemcacheSetRequest.SetPolicy.REPLACE)) ||
				// ((entry != null) && (policy ==
				// MemcacheServicePb.MemcacheSetRequest.SetPolicy.ADD)))
				// /* */ {
				// /* 342 */ System.out.println("dont need to set in local");
				// result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
				// /* */ }
				// /* */ else
				// /* */ {
				long expiry = (item.hasExpirationTime()) ? item
						.getExpirationTime() : 0L;
				byte[] value = item.getValue().toByteArray();
				int flags = item.getFlags();

				CacheEntry ce = new CacheEntry(namespace, key, value, flags,
						expiry * 1000L);
				internalSet(namespace, key, ce);
				System.out.println("after intenal set!");
				result
						.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
			}

		}

		// for (int i = 0; i < req.getItemCount(); ++i) {
		// MemcacheServicePb.MemcacheSetRequest.Item item = req.getItem(i);
		// Key key = new Key(item.getKey().toByteArray());
		// MemcacheServicePb.MemcacheSetRequest.SetPolicy policy = item
		// .getSetPolicy();
		// if (policy != MemcacheServicePb.MemcacheSetRequest.SetPolicy.SET) {
		// Long timeout = (Long) getOrMakeSubMap(this.deleteHold,
		// namespace).get(key);
		// if ((timeout != null)
		// && (this.clock.getCurrentTime() < timeout.longValue())) {
		// result
		// .addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
		// }
		//
		// } else {
		// CacheEntry entry = getWithExpiration(namespace, key);
		// if (((entry == null) && (policy ==
		// MemcacheServicePb.MemcacheSetRequest.SetPolicy.REPLACE))
		// || ((entry != null) && (policy ==
		// MemcacheServicePb.MemcacheSetRequest.SetPolicy.ADD))) {
		// result
		// .addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
		// } else {
		// long expiry = (item.hasExpirationTime()) ? item
		// .getExpirationTime() : 0L;
		// byte[] value = item.getValue().toByteArray();
		// int flags = item.getFlags();
		//
		// CacheEntry ce = new CacheEntry(namespace, key, value,
		// flags, expiry * 1000L);
		// internalSet(namespace, key, ce);
		// result
		// .addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
		// }
		// }
		// }
		MemcacheSetResponse rr = result.build();
		status.setSuccessful(true);
		System.out.println("----flat string of set result: " + rr.toString());
		return rr;
	}

	public MemcacheServicePb.MemcacheDeleteResponse delete(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheDeleteRequest req) {
		MemcacheServicePb.MemcacheDeleteResponse.Builder result = MemcacheServicePb.MemcacheDeleteResponse
				.newBuilder();
		// String namespace = req.getNameSpace();

		for (int i = 0; i < req.getItemCount(); ++i) {
			MemcacheServicePb.MemcacheDeleteRequest.Item item = req.getItem(i);
			MyKey key = new MyKey(item.getKey().toByteArray());
			// CacheEntry ce = internalDelete(namespace, key);
			boolean deleteResult = false;
			try {
				deleteResult = (c.delete(new String("__" + appName + "__"
						+ req.getNameSpace() + "__" + key.getBytes()))).get();
			} catch (InterruptedException e) {
				e.printStackTrace();
			} catch (ExecutionException e) {
				e.printStackTrace();
			}

			if (deleteResult)
				result
						.addDeleteStatus(MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.DELETED);

			else
				result
						.addDeleteStatus(MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.NOT_FOUND);

			// result
			// .addDeleteStatus((ce == null) ?
			// MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.NOT_FOUND
			// :
			// MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.DELETED);

			// if (ce != null) {
			// this.stats.recordDelete(ce);
			// }

			// if (item.hasDeleteTime()) {
			// int millisNoReAdd = item.getDeleteTime() * 1000;
			// getOrMakeSubMap(this.deleteHold, namespace).put(
			// key,
			// Long.valueOf(this.clock.getCurrentTime()
			// + millisNoReAdd));
			// }
		}
		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheIncrementResponse increment(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheIncrementRequest req) {
		MemcacheServicePb.MemcacheIncrementResponse.Builder result = MemcacheServicePb.MemcacheIncrementResponse
				.newBuilder();
		// String namespace = req.getNameSpace();

		MyKey key = new MyKey(req.getKey().toByteArray());
		long delta = req.getDelta();
		boolean dir = true;
		if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
			dir = false;
		if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT) {
			delta = -delta;
		}

		if (delta > Integer.MAX_VALUE) {
			status.setSuccessful(false);
			throw new ApiProxy.ApplicationException(1,
					"delta is too big, we only support interger for now");
		}
		long tempResult = 0;
		if (dir) {
			tempResult = c.incr(new String("__" + appName + "__"
					+ req.getNameSpace() + "__" + key.getBytes()), (int) delta);
		} else
			tempResult = c.decr(new String("__" + appName + "__"
					+ req.getNameSpace() + "__" + key.getBytes()), (int) delta);
		//
		// synchronized (this.mockCache) {
		// CacheEntry ce = getWithExpiration(namespace, key);
		//
		// if (ce == null) {
		// if (req.hasInitialValue()) {
		// MemcacheSerialization.ValueAndFlags value;
		// try {
		// value = MemcacheSerialization.serialize(Long
		// .valueOf(req.getInitialValue()));
		// } catch (IOException e) {
		// throw new ApiProxy.UnknownException(
		// "Serialzation error: " + e);
		// }
		// int flags = value.flags.ordinal();
		// if (req.hasInitialFlags()) {
		// flags = req.getInitialFlags();
		// }
		// ce = new CacheEntry(namespace, key, value.value, flags, 0L);
		// internalSet(namespace, key, ce);
		// } else {
		// this.stats.recordMiss();
		// return result.build();
		// }
		// }
		// this.stats.recordHit(ce);
		// Long longval;
		// try {
		// longval = Long.valueOf(Long.parseLong(new String(ce.value,
		// "UTF-8")));
		// } catch (NumberFormatException e) {
		// status.setSuccessful(false);
		// throw new ApiProxy.ApplicationException(1, "Format error");
		// } catch (UnsupportedEncodingException e) {
		// throw new ApiProxy.UnknownException(
		// "UTF-8 encoding was not found.");
		// }
		// if (longval.longValue() < 0L) {
		// status.setSuccessful(false);
		// throw new ApiProxy.ApplicationException(1,
		// "Initial value must be non-negative");
		// }
		//
		// long newvalue = longval.longValue();
		//
		// newvalue += delta;
		// if ((delta < 0L) && (newvalue < 0L)) {
		// newvalue = 0L;
		// }
		// this.stats.recordDelete(ce);
		// try {
		// ce.value = Long.toString(newvalue).getBytes("UTF-8");
		// } catch (UnsupportedEncodingException e) {
		// throw new ApiProxy.UnknownException(
		// "UTF-8 encoding was not found.");
		// }
		//
		// ce.bytes = (key.getBytes().length + ce.value.length);
		// Map namespaceMap = getOrMakeSubMap(this.mockCache, namespace);
		// namespaceMap.remove(key);
		// namespaceMap.put(key, ce);
		// this.stats.recordAdd(ce);
		// result.setNewValue(newvalue);
		// }
		result.setNewValue(tempResult);
		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheBatchIncrementResponse batchIncrement(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheBatchIncrementRequest batchReq) {
		MemcacheServicePb.MemcacheBatchIncrementResponse.Builder result = MemcacheServicePb.MemcacheBatchIncrementResponse
				.newBuilder();
	//	String namespace = batchReq.getNameSpace();

		// synchronized (this.mockCache) {
		// label29: for (MemcacheServicePb.MemcacheIncrementRequest req :
		// batchReq.getItemList()) {
		// MemcacheServicePb.MemcacheIncrementResponse.Builder resp =
		// MemcacheServicePb.MemcacheIncrementResponse.newBuilder();
		//
		// Key key = new Key(req.getKey().toByteArray());
		// long delta = req.getDelta();
		// if (req.getDirection() ==
		// MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT) {
		// delta = -delta;
		// }
		//
		// CacheEntry ce = getWithExpiration(namespace, key);
		//
		// if (ce == null) {
		// if (req.hasInitialValue()) {
		// MemcacheSerialization.ValueAndFlags value;
		// try {
		// value =
		// MemcacheSerialization.serialize(Long.toString(req.getInitialValue()));
		// } catch (IOException e) {
		// throw new ApiProxy.UnknownException("Serialzation error: " + e);
		// }
		// ce = new CacheEntry(namespace, key, value.value,
		// value.flags.ordinal(), 0L);
		// } else {
		// this.stats.recordMiss();
		// resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
		// result.addItem(resp);
		// }
		// }
		//
		// this.stats.recordHit(ce);
		// Long longval;
		// try {
		// longval = Long.valueOf(Long.parseLong(new String(ce.value,
		// "UTF-8")));
		// } catch (NumberFormatException e) {
		// resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
		// result.addItem(resp);
		// break label29:
		// } catch (UnsupportedEncodingException e) {
		// resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
		// result.addItem(resp); }
		// continue;
		//
		// if (longval.longValue() < 0L) {
		// resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
		// result.addItem(resp);
		// }
		//
		// long newvalue = longval.longValue();
		// newvalue += delta;
		// if ((delta < 0L) && (newvalue < 0L)) {
		// newvalue = 0L;
		// }
		// this.stats.recordDelete(ce);
		// try {
		// ce.value = Long.toString(newvalue).getBytes("UTF-8");
		// }
		// catch (UnsupportedEncodingException e) {
		// throw new ApiProxy.UnknownException("UTF-8 encoding was not found.");
		// }
		//
		// ce.bytes = (key.getBytes().length + ce.value.length);
		// Map namespaceMap = getOrMakeSubMap(this.mockCache, namespace);
		// namespaceMap.remove(key);
		// namespaceMap.put(key, ce);
		// this.stats.recordAdd(ce);
		//
		// resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
		// resp.setNewValue(newvalue);
		// result.addItem(resp);
		// }
		// }
		System.out.println("not implemented batch increment!");
		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheFlushResponse flushAll(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheFlushRequest req) {
		MemcacheServicePb.MemcacheFlushResponse.Builder result = MemcacheServicePb.MemcacheFlushResponse
				.newBuilder();
		// synchronized (this.mockCache) {
		// this.mockCache.clear();
		// this.deleteHold.clear();
		// this.lru.clear();
		// this.stats = new LocalStats(0L, 0L, 0L, 0L, 0L);
		// }
		c.flush();

		status.setSuccessful(true);
		return result.build();
	}

	public MemcacheServicePb.MemcacheStatsResponse stats(
			LocalRpcService.Status status,
			MemcacheServicePb.MemcacheStatsRequest req) {
		MemcacheServicePb.MemcacheStatsResponse result = MemcacheServicePb.MemcacheStatsResponse
				.newBuilder().setStats(this.stats.getAsMergedNamespaceStats())
				.build();

		status.setSuccessful(true);
		return result;
	}

	// public long getMaxSizeInBytes() {
	// return this.maxSize;
	// }

	private class LocalStats {
		// private long hits;
		// private long misses;
		// private long hitBytes;
		// private long itemCount;
		// private long totalBytes;

		private LocalStats(long paramLong1, long paramLong2, long paramLong3,
				long paramLong4, long paramLong5) {
			// this.hits = paramLong1;
			// this.misses = paramLong2;
			// this.hitBytes = paramLong3;
			// this.itemCount = paramLong4;
			// this.totalBytes = paramLong5;
		}

		public MemcacheServicePb.MergedNamespaceStats getAsMergedNamespaceStats() {
			// return
			// MemcacheServicePb.MergedNamespaceStats.newBuilder().setHits(
			// this.hits).setMisses(this.misses)
			// .setByteHits(this.hitBytes).setBytes(this.totalBytes)
			// .setItems(this.itemCount).setOldestItemAge(
			// getMaxSecondsWithoutAccess()).build();
			Iterator<SocketAddress> keyIter = c.getStats().keySet().iterator();
			int hits = 0;
			int miss = 0;
			int byte_written = 0;
			int total_items = 0;
			int bytes = 0;

			while (keyIter.hasNext()) {
				SocketAddress so = keyIter.next();
				Map<String, String> map = c.getStats().get(so);
				// System.out.println("in address: "+so.toString());
				// System.out.println("hits: " +map.get("get_hits"));
				hits += Integer.parseInt(map.get("get_hits"));
				// System.out.println("misses: " +map.get("get_misses"));
				miss += Integer.parseInt(map.get("get_misses"));
				// System.out.println("bytes_written: "
				// +map.get("bytes_written"));
				byte_written += Integer.parseInt(map.get("bytes_written"));
				// System.out.println("total_item: " +map.get("total_items"));
				// total_items += Integer.parseInt(map.get("total_items"));
				// System.out.println("bytes: " +map.get("bytes"));
				bytes += Integer.parseInt(map.get("bytes"));

				// for now total_item and max_time_without_access is set to 0

				// System.out.println();
				// Iterator<String> keysIter = map.keySet().iterator();
				// while(keysIter.hasNext()){
				// String key = (String)keysIter.next();
				// System.out.println("key: "+ key+"value: "+map.get(key));
				// }
			}
			total_items = 0;
			/* 106 */return MemcacheServicePb.MergedNamespaceStats.newBuilder()
					.setHits(hits).setMisses(miss).setByteHits(byte_written)
					.setBytes(bytes).setItems(total_items).setOldestItemAge(
							getMaxSecondsWithoutAccess()).build();
		}

		public int getMaxSecondsWithoutAccess() {
			// if (LocalMemcacheService.this.lru.isEmpty()) {
			// return 0;
			// }
			// LocalMemcacheService.CacheEntry entry =
			// (LocalMemcacheService.CacheEntry) LocalMemcacheService.this.lru
			// .getOldest();
			// return (int) ((LocalMemcacheService.this.clock.getCurrentTime() -
			// entry.access) / 1000L);
			return 0;
		}

		// public void recordHit(LocalMemcacheService.CacheEntry ce) {
		// this.hits += 1L;
		// this.hitBytes += ce.bytes;
		// }
		//
		// public void recordMiss() {
		// this.misses += 1L;
		// }
		//
		// public void recordAdd(LocalMemcacheService.CacheEntry ce) {
		// this.itemCount += 1L;
		// this.totalBytes += ce.bytes;
		// while (this.totalBytes > LocalMemcacheService.this.maxSize) {
		// LocalMemcacheService.CacheEntry oldest =
		// (LocalMemcacheService.CacheEntry) LocalMemcacheService.this.lru
		// .getOldest();
		// LocalMemcacheService.this.internalDelete(oldest.namespace,
		// oldest.key);
		// this.itemCount -= 1L;
		// this.totalBytes -= oldest.bytes;
		// }
		// }
		//
		// public void recordDelete(LocalMemcacheService.CacheEntry ce) {
		// this.itemCount -= 1L;
		// this.totalBytes -= ce.bytes;
		// }
	}

	

	

}
