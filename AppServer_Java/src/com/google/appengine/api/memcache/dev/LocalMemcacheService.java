package com.google.appengine.api.memcache.dev;


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
     * AppScale - removed getWithExpiration private method
     */

    private void internalSet( String namespace, Key key, CacheEntry entry )
    {
        /*
         * AppScale - replaced entire method body with memcache insert
         */
        logger.info("Memcache set, key= [" + keyToString(key) + "]");
        int exp = (int)((entry.getExpires() - System.currentTimeMillis()) / 1000 + 1);
        if(exp < 0)
        {
            exp = 0;
        }
        try
        {
            Object response = memcacheClient.set(keyToString(key), exp, entry);
            logger.info("Memcache set response for key [" + keyToString(key) + "] was [" + response + "]");
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

            CacheEntry entry;

            // handle cas
            if ((req.hasForCas()) && (req.getForCas()))
            {
                GetsResponse<Object> res;
                try
                {
                    res = memcacheClient.gets(internalKey);
                    item.setCasId(res.getCas());
                    entry = (CacheEntry)res.getValue();
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
                        boolean res = false;
                        try
                        {
                            //get cas id for key
                            GetsResponse<Object> getsResp = memcacheClient.gets(internalKey);
                            //do cas operation for key:ce
                            res = memcacheClient.cas(internalKey, (int)expiry, ce, getsResp.getCas());
                        }
                        catch(TimeoutException e)
                        {
                            logger.warning("TimeoutException doing gets/cas for key [" + internalKey + "]");
                        }
                        catch(InterruptedException e)
                        {
                            logger.warning("InterruptedException doing gets/cas for key [" + internalKey + "]");
                        }
                        catch(MemcachedException e)
                        {
                            logger.warning("MemcachedException doing gets/cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
                        } 
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
         * doesn't have use exception handling on this method, going to throw a
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

            // Spymemcache doesn't support deletes with hold time
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
        Object res = null;
        try
        {
            res = memcacheClient.get(internalKey);
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
        if (res == null)
        {
            logger.fine("Memcache key [" + internalKey + "] not found, returning null");
            return null;
        }

        boolean deleted = false;
        try
        {
            deleted = memcacheClient.delete(internalKey);;
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
        return (CacheEntry)res;
    }

    public MemcacheServicePb.MemcacheIncrementResponse increment( LocalRpcService.Status status, MemcacheServicePb.MemcacheIncrementRequest req )
    {
        MemcacheServicePb.MemcacheIncrementResponse.Builder result = MemcacheServicePb.MemcacheIncrementResponse.newBuilder();
        String namespace = req.getNameSpace();
        Key key = new Key(req.getKey().toByteArray());
        long delta = req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT ? -req.getDelta() : req.getDelta();
        String internalKey = getInternalKey(namespace, key);
        /*
         * AppScale - Added declaration of BigInteger value;
         */
        BigInteger value;
        /*
         * AppScale - changed some of this method body to use our memcache
         * client
         */
        // Do a gets because we can't increment CacheEntry objects, so we do cas instead.
        GetsResponse<Object> getsResp = null;
        try
        {
            getsResp = memcacheClient.gets(internalKey);
        }
	catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing gets/cas for key [" + internalKey + "]");
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing gets/cas for key [" + internalKey + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing gets/cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
        }
        CacheEntry ce = null;
        long casId = 0l;
        if(getsResp != null)
        {
            ce = (CacheEntry)getsResp.getValue();
            casId = getsResp.getCas();
        }
        if (ce == null)
        {
            if (req.hasInitialValue())
            {
                /*
                 * AppScale - removed type declaration for value
                 */
		// Doing an increment for something with an initial value, just do a regular set. 
		System.out.println("inside increment, ce null and req has init value");
                value = BigInteger.valueOf(req.getInitialValue()).and(UINT64_MAX_VALUE);
                value = value.add(new BigInteger(String.valueOf(delta)));
                System.out.println("value: " + value);
                int flags = req.hasInitialFlags() ? req.getInitialFlags() : MemcacheSerialization.Flag.LONG.ordinal();

                ce = new CacheEntry(namespace, key, value.toString().getBytes(), flags, 0L, clock.getCurrentTime());
                internalSet(namespace, stringToKey(internalKey), ce);
                result.setNewValue(value.longValue());
        	status.setSuccessful(true);
        	return result.build();
            }
            else
            {
                // Doing an increment for something not present should return null.
 		status.setSuccessful(false);
                return result.build();
            }
        }
        try
        {
            value = new BigInteger(new String(ce.getValue(), UTF8));
        }
        catch (NumberFormatException e)
        {
            status.setSuccessful(false);
            throw new ApiProxy.ApplicationException(MemcacheServicePb.MemcacheServiceError.ErrorCode.INVALID_VALUE.ordinal(), "Format error");
        }
        catch (UnsupportedEncodingException e)
        {
            throw new ApiProxy.UnknownException("UTF-8 encoding was not found.");
        }
        if ((value.compareTo(UINT64_MAX_VALUE) > 0) || (value.signum() < 0))
        {
            status.setSuccessful(false);
            throw new ApiProxy.ApplicationException(MemcacheServicePb.MemcacheServiceError.ErrorCode.INVALID_VALUE.ordinal(), "Value to be incremented must be in the range of an unsigned 64-bit number");
        }

        value = value.add(BigInteger.valueOf(delta));
        if (value.signum() < 0)
            value = UINT64_MIN_VALUE;
        else if (value.compareTo(UINT64_MAX_VALUE) > 0)
        {
            value = value.and(UINT64_MAX_VALUE);
        }
        try
        {
            ce.setValue(value.toString().getBytes(UTF8));
        }
        catch (UnsupportedEncodingException e)
        {
            throw new ApiProxy.UnknownException("UTF-8 encoding was not found.");
        }

        boolean res = false;
        // Value is set now, now do a cas. 
	try
        {
            res = memcacheClient.cas(internalKey, 0, ce, casId);
        }
        catch(TimeoutException e)
        {
            logger.warning("TimeoutException doing gets/cas for key [" + internalKey + "]");
        }
        catch(InterruptedException e)
        {
            logger.warning("InterruptedException doing gets/cas for key [" + internalKey + "]");
        }
        catch(MemcachedException e)
        {
            logger.warning("MemcachedException doing gets/cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
        }	
        if (res == false)
        {
            logger.log(Level.WARNING, "Increment call failed");
            status.setSuccessful(false);
        }
        else
        {
            result.setNewValue(value.longValue());
            status.setSuccessful(true);
        }
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
            if (req.getDirection() == MemcacheServicePb.MemcacheIncrementRequest.Direction.DECREMENT)
            {
                delta = -delta;
            }

            String internalKey = getInternalKey(namespace, key);

	    GetsResponse<Object> getsResp = null;
            try
            {
                getsResp = memcacheClient.gets(internalKey);
            }
            catch(TimeoutException e)
            {
                logger.warning("TimeoutException doing gets/cas for key [" + internalKey + "]");
            }
            catch(InterruptedException e)
            {
                logger.warning("InterruptedException doing gets/cas for key [" + internalKey + "]");
            }
            catch(MemcachedException e)
            {
                logger.warning("MemcachedException doing gets/cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
            }
            CacheEntry ce = null;
            long casId = 0l;
            if(getsResp != null)
            {
                ce = (CacheEntry)getsResp.getValue();
                casId = getsResp.getCas();
            }

            if (ce == null)
            {
                if (req.hasInitialValue())
                {
                    MemcacheSerialization.ValueAndFlags value;
                    try
                    {
                        value = MemcacheSerialization.serialize(Long.toString(req.getInitialValue() + delta));
                    }
                    catch (IOException e)
                    {
                        throw new ApiProxy.UnknownException("Serialzation error: " + e);
                    }
                    ce = new CacheEntry(namespace, key, value.value, value.flags.ordinal(), 0L, clock.getCurrentTime());
                    internalSet(namespace, stringToKey(internalKey), ce);
                    resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
                    resp.setNewValue(req.getInitialValue() + delta);
                    result.addItem(resp);
                    continue;
                }
                else
                {
                    resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                    result.addItem(resp);
                    continue;
                }
            }

            Long longval;
            try
            {
                longval = Long.valueOf(Long.parseLong(new String(ce.getValue(), "UTF-8")));
            }
            catch (NumberFormatException e)
            {
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                result.addItem(resp);
                continue;
            }
            catch (UnsupportedEncodingException e)
            {
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                result.addItem(resp);
                /*
                 * AppScale - moved continue into catch
                 */
                logger.info("AppScale - Caught UnsupportedEncodingException, continuing for loop");
                continue;
            }

            if (longval.longValue() < 0L)
            {
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
                result.addItem(resp);
                continue;
            }

            long newValue = longval.longValue();
            newValue += delta;
            if ((delta < 0L) && (newValue < 0L))
            {
                newValue = 0L;
            }
            try
            {
                ce.setValue(Long.toString(newValue).getBytes("UTF-8"));
            }
            catch (UnsupportedEncodingException e)
            {
                throw new ApiProxy.UnknownException("UTF-8 encoding was not found.");
            }

	    boolean res = false;
	    try
            {
                res = memcacheClient.cas(internalKey, 0, ce, casId);
            }
            catch(TimeoutException e)
            {
                logger.warning("TimeoutException doing gets/cas for key [" + internalKey + "]");
            }
            catch(InterruptedException e)
            {
                logger.warning("InterruptedException doing gets/cas for key [" + internalKey + "]");
            }
            catch(MemcachedException e)
            {
                logger.warning("MemcachedException doing gets/cas for key [" + internalKey + "], message [" + e.getMessage() + "]");
            }
            if (res == false)
            {
                logger.log(Level.WARNING, "Increment call failed");
		resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.NOT_CHANGED);
            }
            else
            {
                resp.setIncrementStatus(MemcacheServicePb.MemcacheIncrementResponse.IncrementStatusCode.OK);
		resp.setNewValue(newValue);
            }
            result.addItem(resp);

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
     * AppScale - added private method below
     */
    private CacheEntry internalGet( String internalKey )
    {
        logger.info("Memcache internalGet(), key = [" + internalKey + "]");
        Object res = null;
        try
        {
            res = memcacheClient.get(internalKey);
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
            logger.info("Memcache internalGet() returning cache entry [" + res + "]");
            return (CacheEntry)res;
        }
        else
        {
            logger.info("Memcache internalGet() returning null");
            return null;
        }
    }

    /*
     * AppScale - added this private method
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
     * AppScale - added private method
     */
    private Key stringToKey( String keyString )
    {
        return new Key(keyString.getBytes());
    }

    /*
     * AppScale - added this private method
     */
    private String getInternalKey( String namespace, Key key )
    {
        /*
         * AppScale - encoding the key because the sdk allows spaces and 
         * lots of other special characters and our memcache client does 
         * not. 
         */
        String encodedKey = DatatypeConverter.printBase64Binary(key.getBytes());
        String internalKey = "__" + appName + "__" + namespace + "__" + encodedKey;
        return internalKey;
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

}
