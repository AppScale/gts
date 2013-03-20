package com.google.appengine.api.memcache.dev;


import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.BufferedReader;
import java.io.DataInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.math.BigInteger;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Collections;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.concurrent.TimeoutException;
import java.lang.InterruptedException;
import javax.xml.bind.DatatypeConverter;

import net.rubyeye.xmemcached.*;
import net.rubyeye.xmemcached.utils.*;
import net.rubyeye.xmemcached.exception.MemcachedException;

import com.google.appengine.api.memcache.MemcacheSerialization;
import com.google.appengine.api.memcache.MemcacheServiceException;
import com.google.appengine.api.memcache.MemcacheServicePb;
import com.google.appengine.repackaged.com.google.protobuf.ByteString;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiProxy;


@ServiceProvider(LocalRpcService.class)
public final class LocalMemcacheService extends AbstractLocalRpcService
{
    private static final Logger               logger               = Logger.getLogger(LocalMemcacheService.class.getName());
    public static final String                PACKAGE              = "memcache";
    public static final String                SIZE_PROPERTY        = "memcache.maxsize";
    private static final String               DEFAULT_MAX_SIZE     = "100M";
    private static final String               UTF8                 = "UTF-8";
    private static final BigInteger           UINT64_MIN_VALUE     = BigInteger.valueOf(0L);
    private static final BigInteger           UINT64_MAX_VALUE     = new BigInteger("FFFFFFFFFFFFFFFF", 16);
    private final int                         MEMCACHE_PORT        = 11211;
    private final int                         TWO_TO_TENTH_SQUARED = 1048576;
    private final int                         TWO_TO_THE_TENTH     = 1024;
    private final int                         MAX_REQUEST_SIZE     = 33554432;
    /*
     * AppScale - removed mockCache and lru
     */
    private final Map<String, Map<Key, Long>> deleteHold;
    private long                              maxSize;
    private Clock                             clock;

    /*
     * AppScale - Added MemcachedClient and appName
     */
    private MemcachedClient                   memcacheClient       = null;
    private String                            appName              = "";

    public LocalMemcacheService()
    {
        /*
         * AppScale - removed mockCache, lru, stats, globalNextCasId
         */
        this.deleteHold = new HashMap<String, Map<Key, Long>>();
        /*
         * AppScale - removed null argument in constructor for LocalStats
         */
    }

    private <K1, K2, V> Map<K2, V> getOrMakeSubMap(Map<K1, Map<K2, V>> map, K1 key) {
        Map subMap = (Map)map.get(key);
        if (subMap == null) 
        {
            subMap = new HashMap();
            map.put(key, subMap);
        }
        return subMap;
    }

    /*
     * AppScale - This method handles a set (but not cas). If the type is incrementable, 
     * it uses other private functions to handle deserialization, serialization, and type
     * conversion. 
     */

    private void internalSet( String namespace, Key key, CacheEntry entry )
    {
        logger.fine("Memcache set, key= [" + keyToString(key) + "]");
        int exp = (int)((entry.getExpires() - System.currentTimeMillis()) / 1000 + 1);
        
        Object valueObj = getIncrObjectFromCacheEntry(entry);
        if(exp < 0)
        {
            exp = 0;
        }
        try
        {
            Object response = memcacheClient.set(keyToString(key), exp, valueObj);
            logger.fine("Memcache set response for key [" + keyToString(key) + "] was [" + response + "]");
            if(isIncrementableType(entry.getFlags()))
            {
                Object typeResponse = memcacheClient.set(getTypeKey(key), exp, entry.getFlags());
            }
            else
            {   
                //do this delete just in case they change types with the same key and the old one was incrementable
                memcacheClient.delete(getTypeKey(key));
            }
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing set for key [" + key + "]"); 
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing set for key [" + key + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing set for key [" + key + "], message [" + e.getMessage() + "]");
        }
    }

    public String getPackage()
    {
        return "memcache";
    }

    public void init( LocalServiceContext context, Map<String, String> properties )
    {
        this.clock = context.getClock();

        /*
         * AppScale - start of added code below to set the appname
         */
        String warPath = context.getLocalServerEnvironment().getAppDir().getAbsolutePath();
        String[] segs = warPath.split("/");
        if (segs.length <= 0)
            logger.log(Level.WARNING, "Can't find app's name");
        else
        {
            for (int i = 0; i < segs.length; i++)
            {
                if (segs[i].equals("apps"))
                {
                    appName = segs[i + 1];
                    logger.info("App's name is: " + appName);
                }
            }
        }
        /*
         * AppScale - end added code for appname
         */

        /*
         * AppScale - start of added code below to establish connection to
         * memcached
         */
        List<String> ipList = new ArrayList<String>();
        String ipListString = new String("");
	
        try
        {
            ResourceLoader res = ResourceLoader.getResourceLoader();
            FileInputStream fstream = new FileInputStream(res.getMemcachedServerIp());
            // Get the object of DataInputStream
            DataInputStream in = new DataInputStream(fstream);
            BufferedReader br = new BufferedReader(new InputStreamReader(in));
            String strLine;
            // Read file line by line and populate ip list
            while ((strLine = br.readLine()) != null)
            {
                String ip = strLine;
                if (isIp(ip))
                { 
                    ipList.add(ip);
                }
            }
            // Close the input stream
            in.close();
            //ip list needs to be sorted to be consistent accross all memcache clients
            Collections.sort(ipList);
            for(String ipStr : ipList)
            {
                logger.info("Memcache client - adding ip: " + ipStr);
                ipListString = ipListString + ipStr + ":" + MEMCACHE_PORT + " ";
            }
        }
        catch (Exception e)
        {
            logger.log(Level.SEVERE, "Error reading in memcache ips: " + e.getMessage());
        }

        XMemcachedClientBuilder builder = new XMemcachedClientBuilder(AddrUtil.getAddresses(ipListString));
        try
        {
            memcacheClient = builder.build();
        }
        catch(IOException e)
        {
            logger.severe("Failed to create Java Memcached client!");
            throw new MemcacheServiceException("Failed to create Java Memcached client", e);
        }
        logger.info("Connection to memcache server is established!");
        /*
         * AppScale - end added code for memcache connection
         */

        String propValue = (String)properties.get("memcache.maxsize");
        if (propValue == null)
            propValue = DEFAULT_MAX_SIZE;
        else
        {
            propValue = propValue.toUpperCase();
        }
        int multiplier = 1;
        if ((propValue.endsWith("M")) || (propValue.endsWith("K")))
        {
            if (propValue.endsWith("M"))
                multiplier = TWO_TO_TENTH_SQUARED;
            else
            {
                multiplier = TWO_TO_THE_TENTH;
            }
            propValue = propValue.substring(0, propValue.length() - 1);
        }
        try
        {
            this.maxSize = (Long.parseLong(propValue) * multiplier);
        }
        catch (NumberFormatException ex)
        {
            throw new MemcacheServiceException("Can't parse cache size limit '" + (String)properties.get("memcache.maxsize") + "'", ex);
        }
    }

    public void setLimits( int bytes )
    {
        this.maxSize = bytes;
    }

    public void start()
    {}

    public void stop()
    {}

    public MemcacheServicePb.MemcacheGetResponse get( LocalRpcService.Status status, MemcacheServicePb.MemcacheGetRequest req )
    {
        /*
         * AppScale - replaced some of this method body to use just memcache and
         * remove unneeded gae code
         */
        logger.fine("Memcache - get() called with [" + req.getKeyCount() + "] keys");
        MemcacheServicePb.MemcacheGetResponse.Builder result = MemcacheServicePb.MemcacheGetResponse.newBuilder();

        for (int i = 0; i < req.getKeyCount(); i++)
        {
            String namespace = req.getNameSpace();
            Key key = new Key(req.getKey(i).toByteArray());
            String internalKey = getInternalKey(namespace, key);
            MemcacheServicePb.MemcacheGetResponse.Item.Builder item = MemcacheServicePb.MemcacheGetResponse.Item.newBuilder();

            CacheEntry entry = null;

            // handle cas
            if ((req.hasForCas()) && (req.getForCas()))
            {
                GetsResponse<Object> res;
                try
                {
                    res = memcacheClient.gets(internalKey);
                    item.setCasId(res.getCas());
                    //now get the type so we can return the correct object
                    Integer type = (Integer)(memcacheClient.get(getTypeKey(internalKey)));
                    Object getsVal = res.getValue();
                    if(getsVal != null)
                    {
                        if(type != null || getsVal instanceof String)
                        {
                            //if type isn't null, we know it was stored as a String so it could be incrementable
                            if(getsVal instanceof String) type = 1;
                            getsVal = convertToReturnType((String)getsVal, type);
                            entry = getCacheEntryFromObject(getsVal, internalKey);
                        } //if type was null, it was stored as a CacheEntry object
                        else entry = (CacheEntry)getsVal;
                        item.setKey(ByteString.copyFrom(key.getBytes())).setFlags(entry.getFlags()).setValue(ByteString.copyFrom(entry.getValue()));
                        result.addItem(item.build()); 
                    }   
                }
                catch(TimeoutException e)
                {
                    logger.warning("TimeoutException doing gets for key [" + internalKey + "]");
                }
                catch(InterruptedException e)
                {
                    logger.warning("InterruptedException doing gets for key [" + internalKey + "]");
                }
                catch(MemcachedException e)
                {
                    logger.warning("MemcachedException doing gets for key [" + internalKey + "], message [" + e.getMessage() + "]");
                }  
            }
            else
            {
                entry = internalGet(internalKey);
                if (entry != null)
                {
                    item.setKey(ByteString.copyFrom(key.getBytes())).setFlags(entry.getFlags()).setValue(ByteString.copyFrom(entry.getValue()));

                    result.addItem(item.build());
                }
            }

        }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheGrabTailResponse grabTail( LocalRpcService.Status status, MemcacheServicePb.MemcacheGrabTailRequest req )
    {
        /*
         * AppScale - replaced entire method body
         */
        MemcacheServicePb.MemcacheGrabTailResponse.Builder result = MemcacheServicePb.MemcacheGrabTailResponse.newBuilder();

        logger.log(Level.SEVERE, "grabTail is not implemented!");
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheSetResponse set( LocalRpcService.Status status, MemcacheServicePb.MemcacheSetRequest req )
    {
        MemcacheServicePb.MemcacheSetResponse.Builder result = MemcacheServicePb.MemcacheSetResponse.newBuilder();
        String namespace = req.getNameSpace();

        for (int i = 0; i < req.getItemCount(); i++)
        {
            MemcacheServicePb.MemcacheSetRequest.Item item = req.getItem(i);
            Key key = new Key(item.getKey().toByteArray());
            String internalKey = getInternalKey(namespace, key);
            MemcacheServicePb.MemcacheSetRequest.SetPolicy policy = item.getSetPolicy();
            if (policy != MemcacheServicePb.MemcacheSetRequest.SetPolicy.SET)
            {
                /*
                 * AppScale - using stringToKey method to get key
                */
                Long timeout = (Long)getOrMakeSubMap(this.deleteHold, namespace).get(stringToKey(internalKey));
                if ((timeout != null) && (this.clock.getCurrentTime() < timeout.longValue()))
                {
                    result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                    continue;
                }
            }

            CacheEntry entry = internalGet(getInternalKey(namespace, key));
            if (((entry == null) && (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.REPLACE)) || ((entry != null) && (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.ADD)))
            {
                result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
            }
            else
            {
                long expiry = item.hasExpirationTime() ? item.getExpirationTime() : 0L;

                byte[] value = item.getValue().toByteArray();
                int flags = item.getFlags();

                CacheEntry ce = new CacheEntry(namespace, key, value, flags, expiry * 1000L, clock.getCurrentTime());

                // dealing with CAS operation
                if (policy == MemcacheServicePb.MemcacheSetRequest.SetPolicy.CAS)
                {
                    if (!item.hasCasId())
                    {
                        result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                    }
                    else
                    {
                        boolean res = internalCheckAndSet(internalKey, ce, item);
                        if (res == false)
                        {
                            result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.NOT_STORED);
                        }
                        else if (res == true)
                        {
                            result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
                        }
                    }
                }
                else
                {
                    internalSet(namespace, stringToKey(internalKey), ce);
                    result.addSetStatus(MemcacheServicePb.MemcacheSetResponse.SetStatusCode.STORED);
                }
            }
        }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheDeleteResponse delete( LocalRpcService.Status status, MemcacheServicePb.MemcacheDeleteRequest req )
    {
        /*
         * AppScale - not sure how to take care of failed deletes since google
         * doesn't use exception handling on this method, going to throw a
         * MemcacheServiceException with message containing the key that failed
         * to delete if there's an issue
         */
        MemcacheServicePb.MemcacheDeleteResponse.Builder result = MemcacheServicePb.MemcacheDeleteResponse.newBuilder();
        String namespace = req.getNameSpace();

        for (int i = 0; i < req.getItemCount(); i++)
        {
            MemcacheServicePb.MemcacheDeleteRequest.Item item = req.getItem(i);
            Key key = new Key(item.getKey().toByteArray());
            String internalKey = getInternalKey(namespace, key);
            CacheEntry ce = internalDelete(internalKey);

            result.addDeleteStatus(ce == null ? MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.NOT_FOUND : MemcacheServicePb.MemcacheDeleteResponse.DeleteStatusCode.DELETED);

            if (item.hasDeleteTime())
            {
                int millisNoReAdd = item.getDeleteTime() * 1000;
                if (deleteHold.get(namespace) != null)
                {
                    deleteHold.get(namespace).put(stringToKey(getInternalKey(namespace, key)), Long.valueOf(this.clock.getCurrentTime() + millisNoReAdd));
                }
            }
        }

        status.setSuccessful(true);
        return result.build();
    }

    /*
     * AppScale - added internalDelete method below
     */
    private CacheEntry internalDelete( String internalKey )
    {
        logger.fine("Memcache internalDelete(...), key=[" + internalKey + "]");
        /*
         * AppScale - memcache doesn't return the object which is being deleted
         * on delete(key). First we do a get, if it's not there return null,
         * otherwise we do a delete and make sure the asynchronous delete
         * returns true. Otherwise we throw an exception.
         */
        CacheEntry res = null;
        res = internalGet(internalKey);
        
        if (res == null)
        {
            logger.fine("Memcache key [" + internalKey + "] not found, returning null");
            return null;
        }

        boolean deleted = false;
        try
        {
            deleted = memcacheClient.delete(internalKey);
            memcacheClient.delete(getTypeKey(internalKey));
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing delete for key [" + internalKey + "]");
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing delete for key [" + internalKey + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing delete for key [" + internalKey + "], message [" + e.getMessage() + "]");
        }
        logger.fine("Memcache returned [" + deleted + "] as delete result for key [" + internalKey + "]");
        
        if (deleted == false)
        {
            throw new MemcacheServiceException("Failed to delete cache entry with internalKey [" + internalKey + "]");
        }
        
        return res;
    }

    public MemcacheServicePb.MemcacheIncrementResponse increment( LocalRpcService.Status status, MemcacheServicePb.MemcacheIncrementRequest req )
    {
        MemcacheServicePb.MemcacheIncrementResponse.Builder result = MemcacheServicePb.MemcacheIncrementResponse.newBuilder();
        String namespace = req.getNameSpace();
        Key key = new Key(req.getKey().toByteArray());
        long delta = req.getDelta();
        
        /*
         * AppScale - Added declaration of BigInteger value;
         */
        BigInteger value;
        /*
         * AppScale - changed some of this method body to use our memcache
         * client
         */
        String internalKey = getInternalKey(namespace, key);
        if (req.hasInitialValue())
        {
            /*
             * AppScale - removed type declaration for value
             */
            value = BigInteger.valueOf(req.getInitialValue()).and(UINT64_MAX_VALUE);
            long initLongVal = value.longValue();
            if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
            {
                try
                {
                    long res = memcacheClient.decr(internalKey, delta, initLongVal - delta);
                    result.setNewValue(res);
                    status.setSuccessful(true);
                    return result.build();
                }
                catch(TimeoutException e)
                {
                    logger.warning("TimeoutException doing decr for key [" + internalKey + "]");
                }
                catch(InterruptedException e)
                {
                    logger.warning("InterruptedException doing decr for key [" + internalKey + "]");
                }
                catch(MemcachedException e)
                {
                    logger.warning("MemcachedException doing decr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                }
            }        
            else
            {   
                try
                {
                    long res = memcacheClient.incr(internalKey, delta, initLongVal + delta);
                    result.setNewValue(res);
                    status.setSuccessful(true);
                    return result.build();
                }
                catch(TimeoutException e)
                {
                    logger.warning("TimeoutException doing incr for key [" + internalKey + "]");
                }
                catch(InterruptedException e)
                {
                    logger.warning("InterruptedException doing incr for key [" + internalKey + "]");
                }
                catch(MemcachedException e)
                {
                    logger.warning("MemcachedException doing incr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                }
            }
        }
        long res = -1;
        if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
        {
            try
            {
                res = memcacheClient.decr(internalKey, delta);
            }
            catch(TimeoutException e)
            {   
                logger.warning("TimeoutException doing decr for key [" + internalKey + "]");
            }
            catch(InterruptedException e)
            {
                logger.warning("InterruptedException doing decr for key [" + internalKey + "]");
            }
            catch(MemcachedException e)
            {
                logger.warning("MemcachedException doing decr for key [" + internalKey + "], message [" + e.getMessage() + "]");
            }
        }
        else
        {
            try
            {
                res = memcacheClient.incr(internalKey, delta);
            }
            catch(TimeoutException e)
            {
                logger.warning("TimeoutException doing incr for key [" + internalKey + "]");
            }
            catch(InterruptedException e)
            {
                logger.warning("InterruptedException doing incr for key [" + internalKey + "]");
            }
            catch(MemcachedException e)
            {
                logger.warning("MemcachedException doing incr for key [" + internalKey + "], message [" + e.getMessage() + "]");
            }
        }
        if (res == -1)
        {
            logger.log(Level.WARNING, "Increment call failed");
            status.setSuccessful(false);
        }
        else
        {
            status.setSuccessful(true);
        }
        result.setNewValue(res);
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheBatchIncrementResponse batchIncrement( LocalRpcService.Status status, MemcacheServicePb.MemcacheBatchIncrementRequest batchReq )
    {
        /*
         * AppScale - changed a lot of this method body to use our memcached
         * client
         */
        logger.fine("Memcache - batchIncrement called");
        MemcacheServicePb.MemcacheBatchIncrementResponse.Builder result = MemcacheServicePb.MemcacheBatchIncrementResponse.newBuilder();
        String namespace = batchReq.getNameSpace();

        for (MemcacheServicePb.MemcacheIncrementRequest req : batchReq.getItemList())
        {
            MemcacheServicePb.MemcacheIncrementResponse.Builder resp = MemcacheServicePb.MemcacheIncrementResponse.newBuilder();

            Key key = new Key(req.getKey().toByteArray());
            long delta = req.getDelta();

            String internalKey = getInternalKey(namespace, key);
            BigInteger value;
            if (req.hasInitialValue())
            {
                /*
                 * AppScale - removed type declaration for value
                 */
                value = BigInteger.valueOf(req.getInitialValue()).and(UINT64_MAX_VALUE);
                long initLongVal = value.longValue();
                if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
                {
                    try
                    {
                        long res = memcacheClient.decr(internalKey, delta, initLongVal - delta);
                        resp.setNewValue(res);
                        resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
                        result.addItem(resp);
                    }
                    catch(TimeoutException e)
                    {
                        logger.warning("TimeoutException doing decr for key [" + internalKey + "]");
                    }
                    catch(InterruptedException e)
                    {
                        logger.warning("InterruptedException doing decr for key [" + internalKey + "]");
                    }
                    catch(MemcachedException e)
                    {
                        logger.warning("MemcachedException doing decr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                    }
                }
                else
                {
                    try
                    {
                        long res = memcacheClient.incr(internalKey, delta, initLongVal + delta);
                        resp.setNewValue(res);
                        resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
                        result.addItem(resp);
                    }
                    catch(TimeoutException e)
                    {
                        logger.warning("TimeoutException doing incr for key [" + internalKey + "]");
                    }
                    catch(InterruptedException e)
                    {
                        logger.warning("InterruptedException doing incr for key [" + internalKey + "]");
                    }
                    catch(MemcachedException e)
                    {
                        logger.warning("MemcachedException doing incr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                    }
                } 
            }
            else
            {
                long res = -1;
                if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
                {
                    try
                    {
                        res = memcacheClient.decr(internalKey, delta);
                    }
                    catch(TimeoutException e)
                    {
                        logger.warning("TimeoutException doing decr for key [" + internalKey + "]");
                    }
                    catch(InterruptedException e)
                    {
                        logger.warning("InterruptedException doing decr for key [" + internalKey + "]");
                    }
                    catch(MemcachedException e)
                    {
                        logger.warning("MemcachedException doing decr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                    }
                }
                else
                {
		    try
                    {
                        res = memcacheClient.incr(internalKey, delta);
                    }
                    catch(TimeoutException e)
                    {
                        logger.warning("TimeoutException doing incr for key [" + internalKey + "]");
                    }
                    catch(InterruptedException e)
                    {
                        logger.warning("InterruptedException doing incr for key [" + internalKey + "]");
                    }
                    catch(MemcachedException e)
                    {
                        logger.warning("MemcachedException doing incr for key [" + internalKey + "], message [" + e.getMessage() + "]");
                    }
                }
                if (res == -1)
                {
                    logger.log(Level.WARNING, "Increment call failed");
                    status.setSuccessful(false);
                }
                else
                {
                    status.setSuccessful(true);
                }
                resp.setNewValue(res);
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
                result.addItem(resp);
            }
        }

        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheFlushResponse flushAll( LocalRpcService.Status status, MemcacheServicePb.MemcacheFlushRequest req )
    {
        /*
         * AppScale - replaced entire method body to use memcached client
         */
        MemcacheServicePb.MemcacheFlushResponse.Builder result = MemcacheServicePb.MemcacheFlushResponse.newBuilder();
        try
        {
            memcacheClient.flushAll();
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing flushAll");
            status.setSuccessful(false);
            return result.build();
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing flushAll");
            status.setSuccessful(false);
            return result.build();
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing flushAll, message [" + e.getMessage() + "]");
            status.setSuccessful(false);
            return result.build();
        }
        status.setSuccessful(true);
        return result.build();
    }

    public MemcacheServicePb.MemcacheStatsResponse stats( LocalRpcService.Status status, MemcacheServicePb.MemcacheStatsRequest req )
    {
        MemcacheServicePb.MemcacheStatsResponse result = MemcacheServicePb.MemcacheStatsResponse.newBuilder().setStats(getAsMergedNamespaceStats()).build();
        status.setSuccessful(true);
        return result;
    }

    public long getMaxSizeInBytes()
    {
        return this.maxSize;
    }

    public Integer getMaxApiRequestSize()
    {
        return Integer.valueOf(MAX_REQUEST_SIZE);
    }

    /*
     * AppScale - Added this private method for stats
     */
    public MemcacheServicePb.MergedNamespaceStats getAsMergedNamespaceStats()
    {
        Map<InetSocketAddress, Map<String, String>> statusMap;
        try
        {
            statusMap = memcacheClient.getStats();
        }
        catch(MemcachedException e)
        {
            logger.severe("Failed to get stats for memcache");
            throw new MemcacheServiceException("Failed to get stats for memcache", e);
        }
        catch(InterruptedException e)
        {
            logger.severe("Failed to get stats for memcache");
            throw new MemcacheServiceException("Failed to get stats for memcache", e);
        }
        catch(TimeoutException e)
        {
            logger.severe("Failed to get stats for memcache");
            throw new MemcacheServiceException("Failed to get stats for memcache", e);
        } 
        Iterator<InetSocketAddress> iter = statusMap.keySet().iterator();
        int hits = 0;
        int misses = 0;
        int totalBytes = 0;
        int hitBytes = 0;
        int itemCount = 0;
        while (iter.hasNext())
        {
            InetSocketAddress host = iter.next();
            Map<String, String> status = statusMap.get(host);
            hits += Integer.parseInt(status.get("get_hits"));
            misses += Integer.parseInt(status.get("get_misses"));
            totalBytes += Integer.parseInt(status.get("bytes"));

        }

        return MemcacheServicePb.MergedNamespaceStats.newBuilder().setHits(hits).setMisses(misses).setByteHits(hitBytes).setBytes(totalBytes).setItems(itemCount).setOldestItemAge(getMaxSecondsWithoutAccess()).build();
    }

    public int getMaxSecondsWithoutAccess()
    {
        /*
         * AppScale - need to investigate what value to return here
         */
        return 0;
    }

    /*
     * AppScale - removed inner class Key (implemented own version in same
     * package)
     */

    /*
     * AppScale - removed inner class LocalStats
     */

    /*
     * AppScale - This method does a get using the xmemcached client, also does
     * a get to check if the type was converted from a Integer, Long, Byte or Short
     * to a String. If it was then the return object is changed to its original type. 
     */
    private CacheEntry internalGet( String internalKey )
    {
        logger.fine("Memcache internalGet(), key = [" + internalKey + "]");
        Object res = null;
        Integer type = null;
        try
        {
            res = memcacheClient.get(internalKey);
            type = (Integer)(memcacheClient.get(getTypeKey(internalKey)));
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing get for key [" + internalKey + "]");
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing get for key [" + internalKey + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing get for key [" + internalKey + "], message [" + e.getMessage() + "]");
        }
        if (res != null)
        {
            if(type != null || res instanceof String)
            {
                if(res instanceof String) type = 1;
                res = convertToReturnType((String)res, type);
                CacheEntry ce = getCacheEntryFromObject(res, internalKey);
                return ce;
            }//if type is null we know it's a CacheEntry object
            else return (CacheEntry)res;
        }
        else
        {
            logger.fine("Memcache internalGet() returning null");
            return null;
        }
    }

    /*
     * AppScale - Checks if a given String is an ip address
     */
    private boolean isIp( String ip )
    {
        String[] parts = ip.split("\\.");
        if (parts.length != 4) return false;
        for (String s : parts)
        {
            int i = Integer.parseInt(s);
            if (i < 0 || i > 255)
            {
                return false;
            }
        }
        return true;
    }

    /*
     * AppScale - Creates a key from a String
     */
    private Key stringToKey( String keyString )
    {
        return new Key(keyString.getBytes());
    }

    /*
     * AppScale - encoding the key because the sdk allows spaces and 
     * lots of other special characters and our memcache client does 
     * not.
     */
    private String getInternalKey( String namespace, Key key )
    {
        String encodedKey = DatatypeConverter.printBase64Binary(key.getBytes());
        String internalKey = "__" + appName + "__" + namespace + "__" + encodedKey;
        return internalKey;
    }

    /*
     * AppScale - This method retrieves the namespace from an internalKey. 
     * The format of an internalKey is __appname__namespace__encodedkey.
     */
    private String getNamespaceFromInternalKey(String internalKey)
    {
        String[] splits = internalKey.split("__");
        return splits[1];
    } 
 
    /*
     * AppScale - This method retrieves the key from an internalKey. When it is
     * made into an eternal key, it is encoded, so this method does parsing for the
     * encoded key, then decodes it. 
     */
    private Key getKeyFromInternalKey(String internalKey)
    {
        String[] splits = internalKey.split("__");
        String encodedKey = splits[3];
        byte[] keyBytes = DatatypeConverter.parseBase64Binary(encodedKey);
        Key key = new Key(keyBytes);
        return key;
    } 

    /*
     * AppScale - added this private method
     */
    private String keyToString( Key key )
    {
        return new String(key.getBytes());
    }

    /*
     * AppScale - removed inner CacheEntry class
     */


    /*
     * AppScale - This method is used to convert a Flag into an int.
     */
    private int getFlagVal(MemcacheSerialization.Flag flag)
    {
        if(flag == MemcacheSerialization.Flag.BYTES) return 0;
        else if(flag == MemcacheSerialization.Flag.UTF8) return 1;
        else if(flag == MemcacheSerialization.Flag.OBJECT) return 2;
        else if(flag == MemcacheSerialization.Flag.INTEGER) return 3;
        else if(flag == MemcacheSerialization.Flag.LONG) return 4;
        else if(flag == MemcacheSerialization.Flag.BOOLEAN) return 5;
        else if(flag == MemcacheSerialization.Flag.BYTE) return 6;
        else if(flag == MemcacheSerialization.Flag.SHORT) return 7;
        logger.warning("Failed to translate Flag enum to int, defaulting to object value");
        return 2;
    }
 
    /*
     * AppScale - Using the above Flag->int values, incrementable types are: 
     * SHORT, LONG, INTEGER, and BYTE. 
     */    
    private boolean isIncrementableType(int type)
    {
        if(type == 1 || type == 3 || type == 4 || type == 6 || type == 7) return true;
        else return false; 
    }

    /*
     * AppScale - This method is used to convert a incrementable type from a String
     * back to its original value. 
     */
    private Object convertToReturnType(String obj, int type)
    {   
        Object returnObj = null;
        if(type == 3) returnObj = Integer.parseInt(obj);
        else if(type == 4) returnObj = Long.parseLong(obj);
        else if(type == 6) returnObj = Byte.parseByte(obj);
        else if(type == 7) returnObj = Short.parseShort(obj);
        else if(type == 1) returnObj = obj;
        return returnObj;
    }

    /*
     * AppScale - These methods are used because we store Integers, Longs, Shorts, 
     * and Bytes as Strings so they are incrementable in xmemcached. Because of that, 
     * we must also store a separate key which is just the internalKey + __type. 
     */
    private String getTypeKey(String key)
    {
        return key + "__type";
    }

    private String getTypeKey(Key key)
    {
        return keyToString(key) + "__type";
    }

    /*
     * AppScale - This method takes an object and its memcache key and converts it into 
     * a CacheEntry object. This is used because originally objects were stored as CacheEntry's,
     * but in order for incr to work, we needed to store them as regular Objects. Before calling
     * this method, you should make sure that if your object was originally an incrementable type, 
     * that you did the correct conversion using "convertToReturnType()". 
     */
    private CacheEntry getCacheEntryFromObject(Object obj, String internalKey)
    {
        CacheEntry ce = null;
        MemcacheSerialization.ValueAndFlags vf = null;
        try
        {
            vf = MemcacheSerialization.serialize(obj);
        }
        catch(IOException e)
        {
            logger.severe("Failed to serialize object to create CacheEntry object, message: " + e.getMessage());
        }
        int flagVal = getFlagVal(vf.flags);
        String namespace = getNamespaceFromInternalKey(internalKey);
        Key key = getKeyFromInternalKey(internalKey);
        ce = new CacheEntry(namespace, key, vf.value, flagVal, 0, 0L);
        return ce;
    }

    /*
     * AppScale - This method takes in a CacheEntry object and returns a regular object if it's incrementable. 
     * The objects are stored in the CacheEntry as a byte array so this method handles the
     * deserialization. Also, if the object is an incrementable type, it will return it as
     * a String because xmemcached can only do increments on String objects. 
     */ 
    private Object getIncrObjectFromCacheEntry(CacheEntry entry)
    {
        byte[] value = entry.getValue();
        boolean incrementable = isIncrementableType(entry.getFlags());
        Object valueObj = entry;
        if(incrementable)
        {
            try
            {
                valueObj = MemcacheSerialization.deserialize(value, entry.getFlags());
                valueObj = valueObj.toString();
            }
            catch(IOException e)
            {
                logger.warning("Failed to deserialize CacheEntry byte array value, error:" + e.getMessage());
                e.printStackTrace();
                valueObj = entry;
            }
            catch(ClassNotFoundException e)
            {
                logger.warning("Failed to deserialize CacheEntry byte array value, error:" + e.getMessage());
                e.printStackTrace();
                valueObj = entry;
            }
        }
        return valueObj;            
    }

    /*
     * AppScale - This method will use the casId passed in from the application
     * and do a cas using xmemcached. If the entry is an incrementable type, xmemcached
     * requires it to be a String so it is converted to a String and the original type
     * is stored as a separate entry. 
     */
    private boolean internalCheckAndSet(String internalKey, CacheEntry ce, MemcacheServicePb.MemcacheSetRequest.Item item)
    {
        long expiry = item.hasExpirationTime() ? item.getExpirationTime() : 0L;
        boolean res = false;
        Object valueObj = getIncrObjectFromCacheEntry(ce);
        try
        {
            res = memcacheClient.cas(internalKey, (int)expiry, valueObj, item.getCasId());
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing cas for key [" + internalKey + "]");
        }
        catch(InterruptedException e)
        {
             logger.warning("InterruptedException doing cas for key [" + internalKey + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
        }
        if (res == true)
        {
             if(isIncrementableType(ce.getFlags()))
             {
                 try
                 {
                      memcacheClient.set(getTypeKey(internalKey), (int)expiry, ce.getFlags());
                 }
                 catch(TimeoutException e)
                 {
                      logger.warning("TimeoutException doing type set for key [" + internalKey + "]");
                 }
                 catch(InterruptedException e)
                 {
                       logger.warning("InterruptedException doing type set for key [" + internalKey + "]");
                 }
                 catch(MemcachedException e)
                 {
                       logger.warning("MemcachedException doing type set for key [" + internalKey + "], message [" + e.getMessage() + "]");
                 }
             }
             else
             {
                 //if the new value isn't incrementable, make sure to delete the old type value
                 try
                 {
                      memcacheClient.delete(getTypeKey(internalKey));
                 }
                 catch(TimeoutException e)
                 {
                      logger.warning("TimeoutException doing type delete for key [" + internalKey + "]");
                 }
                 catch(InterruptedException e)
                 {
                       logger.warning("InterruptedException doing type delete for key [" + internalKey + "]");
                 }
                 catch(MemcachedException e)
                 {
                       logger.warning("MemcachedException doing type delete for key [" + internalKey + "], message [" + e.getMessage() + "]");
                 }
             }
         }
         return res;
    }
}
