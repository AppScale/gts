package com.google.appengine.api.memcache.dev;

import java.io.BufferedReader;
import java.io.DataInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import net.spy.memcached.CASResponse;
import net.spy.memcached.CASValue;
import net.spy.memcached.MemcachedClient;

import com.google.appengine.api.memcache.MemcacheSerialization;
import com.google.appengine.api.memcache.MemcacheServiceException;
import com.google.appengine.api.memcache.MemcacheServicePb;
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiProxy;

@ServiceProvider(LocalRpcService.class)
public final class LocalMemcacheService implements LocalRpcService {

    private static final Logger logger = Logger.getLogger(LocalMemcacheService.class.getName());
    public static final String PACKAGE = "memcache";
    public static final String SIZE_PROPERTY = "memcache.maxsize";
    private static final String DEFAULT_MAX_SIZE = "100M";
    private static final String UTF8 = "UTF-8";
    private final Map<String, Long> deleteHold;
    private Clock clock;

    private String appName = "";

    private long maxSize;
    // private LocalStats stats;

    private MemcachedClient memcacheClient = null;

    public LocalMemcacheService() {
        this.deleteHold = new HashMap<String, Long>();
    }

    private void internalSet(String key, CacheEntry entry) {
        int exp = (int) ((entry.getExpires() - System.currentTimeMillis()) / 1000 + 1);
        //logger.log(Level.INFO, "internal set for: " + key + " with expiration time: " + exp);
        memcacheClient.set(key, exp, entry);
    }

    public String getPackage() {
        return "memcache";
    }

    public void init(LocalServiceContext context, Map<String, String> properties) {
        clock = context.getClock();
        String warPath = context.getLocalServerEnvironment().getAppDir().getAbsolutePath();
        String[] segs = warPath.split("/");
        if (segs.length <= 0)
            logger.log(Level.WARNING, "can't find app's name");
        else {
            for (int i = 0; i < segs.length; i++) {
                if (segs[i].equals("apps")) {
                    appName = segs[i + 1];
                    //logger.log(Level.INFO, "app's name is: " + appName);
                }
            }
        }

        final List<InetSocketAddress> ipList = new ArrayList<InetSocketAddress>();

        try {
            ResourceLoader res = ResourceLoader.getResouceLoader();
            FileInputStream fstream = new FileInputStream(res.getMemcachedServerIp());
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
        } catch (Exception e) {
            logger.log(Level.SEVERE, "Error: " + e.getMessage());
        }
        try {
            memcacheClient = new MemcachedClient(ipList);
            memcacheClient.flush();
        } catch (IOException e) {
            e.printStackTrace();
        }

        logger.info("Connection to memcache server is established!");

        String propValue = properties.get("memcache.maxsize");
        if (propValue == null)
            propValue = DEFAULT_MAX_SIZE;
        else {
            propValue = propValue.toUpperCase();
        }
        int multiplier = 1;
        if ((propValue.endsWith("M")) || (propValue.endsWith("K"))) {
            if (propValue.endsWith("M"))
                multiplier = 1048576;
            else {
                multiplier = 1024;
            }
            propValue = propValue.substring(0, propValue.length() - 1);
        }
        try {
            this.maxSize = (Long.parseLong(propValue) * multiplier);
        } catch (NumberFormatException ex) {
            throw new MemcacheServiceException("Can't parse cache size limit '" + properties.get("memcache.maxsize")
                    + "'", ex);
        }
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

    public void setLimits(int bytes) {
        this.maxSize = bytes;
    }

    public void start() {
    }

    public void stop() {
    }

    public MemcacheServicePb.MemcacheGetResponse get(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheGetRequest req) {
        MemcacheServicePb.MemcacheGetResponse.Builder result = MemcacheServicePb.MemcacheGetResponse.newBuilder();

        for (int i = 0; i < req.getKeyCount(); i++) {
            String namespace = req.getNameSpace();
            Key key = new Key(req.getKey(i).toByteArray());
            String internalKey = getInternalKey(namespace, key);
            //logger.log(Level.INFO, "internal key: " + internalKey);
            MemcacheServicePb.MemcacheGetResponse.Item.Builder item = MemcacheServicePb.MemcacheGetResponse.Item
                    .newBuilder();

            CacheEntry entry;

            // handle cas
            if ((req.hasForCas()) && (req.getForCas())) {
                CASValue<Object> res = memcacheClient.gets(internalKey);
                item.setCasId(res.getCas());
                entry = (CacheEntry) res.getValue();
            } else {
                entry = internalGet(internalKey);
                if (entry != null) {
                    item.setKey(ByteString.copyFrom(key.getBytes())).setFlags(entry.getFlags()).setValue(
                            ByteString.copyFrom(entry.getValue()));

                    result.addItem(item.build());
                }
            }

        }
        status.setSuccessful(true);
        return result.build();
    }

    // not implemented !
    public MemcacheServicePb.MemcacheGrabTailResponse grabTail(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheGrabTailRequest req) {
        MemcacheServicePb.MemcacheGrabTailResponse.Builder result = MemcacheServicePb.MemcacheGrabTailResponse
                .newBuilder();

        logger.log(Level.SEVERE, "grabtail is not implemented!");
        // int itemCount;
        // synchronized (this.mockCache) {
        // Map<Key, CacheEntry> map = getOrMakeSubMap(this.mockCache,
        // req.getNameSpace());
        // List<CacheEntry> entries = new ArrayList<CaceEntry>(map.values());
        // Collections.sort(entries);
        //
        // itemCount = 0;
        // for (CacheEntry entry : entries) {
        // internalDelete(req.getNameSpace(), entry.key);
        // this.stats.recordHit(entry);
        // result.addItem(MemcacheServicePb.MemcacheGrabTailResponse.Item.newBuilder().setFlags(entry.flags)
        // .setValue(ByteString.copyFrom(entry.value)).build());
        //
        // itemCount++;
        //
        // if (itemCount == req.getItemCount()) {
        // break;
        // }
        // }
        // }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheSetResponse set(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheSetRequest req) {
        MemcacheServicePb.MemcacheSetResponse.Builder result = MemcacheServicePb.MemcacheSetResponse.newBuilder();
        String namespace = req.getNameSpace();

        for (int i = 0; i < req.getItemCount(); i++) {
            MemcacheServicePb.MemcacheSetRequest.Item item = req.getItem(i);
            Key key = new Key(item.getKey().toByteArray());
            String internalKey = getInternalKey(namespace, key);
            MemcacheServicePb.MemcacheSetRequest.SetPolicy policy = item.getSetPolicy();
            if (policy != MemcacheServicePb.MemcacheSetRequest.SetPolicy.SET) {
                Long timeout = deleteHold.get(internalKey);
                if ((timeout != null) && (this.clock.getCurrentTime() < timeout.longValue())) {
                    result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                    continue;
                }
            }
            //logger.log(Level.INFO, "making a set call");

            CacheEntry entry = internalGet(getInternalKey(namespace, key));
            // if pass this test, REPLACE_ONLY_IF_PRESENT equals to SET_ALWAYS
            if (((entry == null) && (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.REPLACE))
            // if pass this test, ADD_ONLY_IF_NOT_PRESENT equals to SET_ALWAYS
                    || ((entry != null) && (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.ADD))) {
                //logger.log(Level.INFO, "not stored1");
                result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
            } else {
                long expiry = item.hasExpirationTime() ? item.getExpirationTime() : 0L;
                //logger.log(Level.INFO, "exp time: " + expiry);
                //logger.log(Level.INFO, "cur time: " + System.currentTimeMillis());

                byte[] value = item.getValue().toByteArray();
                int flags = item.getFlags();
                CacheEntry ce = new CacheEntry(namespace, value, flags, expiry * 1000L, clock.getCurrentTime());

                // dealing with CAS operation
                if (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.CAS) {
                    if (!item.hasCasId()) {
                        result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                    } else {
                        // get cas id for key
                        CASValue<Object> obj = memcacheClient.gets(internalKey);
                        // do cas operation for key:ce
                        CASResponse res = memcacheClient.cas(internalKey, obj.getCas(), ce);
                        if (res.equals(CASResponse.EXISTS)) {
                            result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.EXISTS);
                        } else if (res.equals(CASResponse.NOT_FOUND)) {
                            result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                        } else if (res.equals(CASResponse.OK)) {
                            result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
                        } else {
                            logger.log(Level.SEVERE, "unknown response for cas operation: " + res.toString());
                        }
                    }
                } else {
                    // set always(MemcacheService.SetPolicy.SET_ALWAYS)
                    //logger.log(Level.INFO, "calling set internal");
                    internalSet(internalKey, ce);
                    result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
                }
            }
        }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheDeleteResponse delete(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheDeleteRequest req) {
        MemcacheServicePb.MemcacheDeleteResponse.Builder result = MemcacheServicePb.MemcacheDeleteResponse.newBuilder();
        String namespace = req.getNameSpace();

        for (int i = 0; i < req.getItemCount(); i++) {
            MemcacheServicePb.MemcacheDeleteRequest.Item item = req.getItem(i);
            Key key = new Key(item.getKey().toByteArray());
            CacheEntry ce = internalGet(getInternalKey(namespace, key));

            result.addDeleteStatus(ce == null ? MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.NOT_FOUND
                    : MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.DELETED);

            // spymemcache dosen't support delete with hold time
            // so have to implement thi feather here
            if (item.hasDeleteTime()) {
                int millisNoReAdd = item.getDeleteTime() * 1000;
                deleteHold.put(getInternalKey(namespace, key), Long
                        .valueOf(this.clock.getCurrentTime() + millisNoReAdd));
            }
        }
        status.setSuccessful(true);
        return result.build();
    }

    // we only support synchronized get
    private CacheEntry internalGet(String key) {
        Object res = memcacheClient.get(key);
        if (res != null) {
            //logger.log(Level.INFO, "calling internal get with res: " + ((CacheEntry) res).getValue());
            return (CacheEntry) res;
        } else
            return null;
    }

    public MemcacheServicePb.MemcacheIncrementResponse increment(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheIncrementRequest req) {
        MemcacheServicePb.MemcacheIncrementResponse.Builder result = MemcacheServicePb.MemcacheIncrementResponse
                .newBuilder();
        String namespace = req.getNameSpace();

        Key key = new Key(req.getKey().toByteArray());
        String internalKey = getInternalKey(namespace, key);
        long delta = req.getDelta();
        long res = 0;

        // if there is no such an entry, set it
        CacheEntry ce = internalGet(internalKey);
        if (ce == null) {
            if (req.hasInitialValue()) {
                MemcacheSerialization.ValueAndFlags value;
                try {
                    value = MemcacheSerialization.serialize(Long.valueOf(req.getInitialValue()));
                } catch (IOException e) {
                    throw new ApiProxy.UnknownException("Serialzation error: " + e);
                }
                int flags = value.flags.ordinal();
                if (req.hasInitialFlags()) {
                    flags = req.getInitialFlags();
                }
                ce = new CacheEntry(namespace, value.value, flags, 0L, clock.getCurrentTime());
                internalSet(internalKey, ce);
            } else {
                return result.build();
            }
        }
        try {
            Long.valueOf(Long.parseLong(new String(ce.getValue(), "UTF-8")));
        } catch (NumberFormatException e) {
            status.setSuccessful(false);
            throw new ApiProxy.ApplicationException(1, "Format error");
        } catch (UnsupportedEncodingException e) {
            throw new ApiProxy.UnknownException("UTF-8 encoding was not found.");
        }
        // test does it do a set if cache miss?
        // req.hasinitial value?
        if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT) {
            res = memcacheClient.decr(internalKey, (int) delta);
        } else
            res = memcacheClient.incr(internalKey, (int) delta);
        if (res == -1) {
            logger.log(Level.WARNING, "increment call failed");
            status.setSuccessful(false);
        } else
            status.setSuccessful(true);
        result.setNewValue(res);
        return result.build();
    }

    public MemcacheServicePb.MemcacheBatchIncrementResponse batchIncrement(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheBatchIncrementRequest batchReq) {
        MemcacheServicePb.MemcacheBatchIncrementResponse.Builder result = MemcacheServicePb.MemcacheBatchIncrementResponse
                .newBuilder();
        String namespace = batchReq.getNameSpace();

        for (MemcacheServicePb.MemcacheIncrementRequest req : batchReq.getItemList()) {
            MemcacheServicePb.MemcacheIncrementResponse.Builder resp = MemcacheServicePb.MemcacheIncrementResponse
                    .newBuilder();

            Key key = new Key(req.getKey().toByteArray());

            String internalKey = getInternalKey(namespace, key);

            CacheEntry ce = internalGet(internalKey);
            if (ce == null) {
                if (req.hasInitialValue()) {
                    MemcacheSerialization.ValueAndFlags value;
                    try {
                        value = MemcacheSerialization.serialize(Long.toString(req.getInitialValue()));
                    } catch (IOException e) {
                        throw new ApiProxy.UnknownException("Serialzation error: " + e);
                    }
                    ce = new CacheEntry(namespace, value.value, value.flags.ordinal(), 0L, clock.getCurrentTime());
                    internalSet(internalKey, ce);
                } else {
                    resp
                            .setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                    result.addItem(resp);
                    continue;

                }

                try {
                    Long.valueOf(Long.parseLong(new String(ce.getValue(), UTF8)));
                } catch (NumberFormatException e) {
                    resp
                            .setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                    result.addItem(resp);
                    continue;
                } catch (UnsupportedEncodingException e) {
                    resp
                            .setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                    result.addItem(resp);
                    continue;
                }

                long delta = req.getDelta();
                long res;
                if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT) {
                    res = memcacheClient.decr(internalKey, (int) delta);
                } else
                    res = memcacheClient.incr(internalKey, (int) delta);
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
                resp.setNewValue(res);
                result.addItem(resp);
            }
        }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheFlushResponse flushAll(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheFlushRequest req) {
        MemcacheServicePb.MemcacheFlushResponse.Builder result = MemcacheServicePb.MemcacheFlushResponse.newBuilder();
        memcacheClient.flush();
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheStatsResponse stats(LocalRpcService.Status status,
            MemcacheServicePb.MemcacheStatsRequest req) {
        MemcacheServicePb.MemcacheStatsResponse result = MemcacheServicePb.MemcacheStatsResponse.newBuilder().setStats(
                getAsMergedNamespaceStats()).build();

        status.setSuccessful(true);
        return result;
    }

    public long getMaxSizeInBytes() {
        return this.maxSize;
    }

    private String getInternalKey(String namespace, Key key) {
        return "__" + appName + "__" + namespace + "__" + new String(key.getBytes());
    }

    // private class LocalStats {
    // private long hits;
    // private long misses;
    // private long hitBytes;
    // private long itemCount;
    // private long totalBytes;
    //
    // private LocalStats(long hits, long misses, long hitBytes, long itemCount,
    // long totalBytes) {
    // this.hits = hits;
    // this.misses = misses;
    // this.hitBytes = hitBytes;
    // this.itemCount = itemCount;
    // this.totalBytes = totalBytes;
    //
    // Map<SocketAddress, Map<String, String>> statusMap =
    // memcacheClient.getStats();
    // Iterator<SocketAddress> iter = statusMap.keySet().iterator();
    // while (iter.hasNext()) {
    // SocketAddress host = iter.next();
    // logger.info("status for host: " + host.toString());
    // Map<String, String> status = statusMap.get(host);
    // Iterator<String> propIter = status.keySet().iterator();
    // while (propIter.hasNext()) {
    // String prop = propIter.next();
    // logger.info(prop + "->" + status.get(prop));
    // }
    // }
    // }

    public MemcacheServicePb.MergedNamespaceStats getAsMergedNamespaceStats() {
        Map<SocketAddress, Map<String, String>> statusMap = memcacheClient.getStats();
        //logger.info("trying to get status");
        Iterator<SocketAddress> iter = statusMap.keySet().iterator();
        int hits = 0;
        int misses = 0;
        int totalBytes = 0;
        int hitBytes = 0;
        int itemCount = 0;
        while (iter.hasNext()) {
            SocketAddress host = iter.next();
            Map<String, String> status = statusMap.get(host);
            //logger.info("getting status for host: " + host);
            hits += Integer.parseInt(status.get("get_hits"));
            misses += Integer.parseInt(status.get("get_misses"));
            totalBytes += Integer.parseInt(status.get("bytes"));
            // this.hitBytes += Integer.parseInt(status.get("get_hits"));
            // this.itemCount += Integer.parseInt(status.get("get_hits"));
            // hitBytes = 0;
            // itemCount = 0;

        }

        return MemcacheServicePb.MergedNamespaceStats.newBuilder().setHits(hits).setMisses(misses)
                .setByteHits(hitBytes).setBytes(totalBytes).setItems(itemCount).setOldestItemAge(
                        getMaxSecondsWithoutAccess()).build();
    }

    public int getMaxSecondsWithoutAccess() {
        // return 0 temporarily
        return 0;
    }
}
