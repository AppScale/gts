package com.google.appengine.api.datastore.dev;


import com.google.appengine.api.datastore.EntityTranslator;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.collect.Maps;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiBasePb.Integer64Proto;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.datastore.DatastoreV3Pb;
import com.google.apphosting.datastore.DatastoreV3Pb.GetResponse;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.Property;
import java.io.Serializable;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/*
 * AppScale addition to #end
 */
import com.google.appengine.tools.resources.ResourceLoader;
/* #end */

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService extends AbstractLocalRpcService
{
    private static final Logger                 logger                             = Logger.getLogger(LocalDatastoreService.class.getName());
    static final int                            DEFAULT_BATCH_SIZE                 = 20;
    public static final int                     MAXIMUM_RESULTS_SIZE               = 300;
    public static final String                  PACKAGE                            = "datastore_v3";
    public static final String                  MAX_QUERY_LIFETIME_PROPERTY        = "datastore.max_query_lifetime";
    private static final int                    DEFAULT_MAX_QUERY_LIFETIME         = 30000;
    public static final String                  MAX_TRANSACTION_LIFETIME_PROPERTY  = "datastore.max_txn_lifetime";
    private static final int                    DEFAULT_MAX_TRANSACTION_LIFETIME   = 300000;
    public static final String                  STORE_DELAY_PROPERTY               = "datastore.store_delay";
    static final int                            DEFAULT_STORE_DELAY_MS             = 30000;
    static final int                            MAX_STRING_LENGTH                  = 500;
    static final int                            MAX_LINK_LENGTH                    = 2038;
    public static final int                     MAX_EG_PER_TXN                     = 5;
    public static final String                  BACKING_STORE_PROPERTY             = "datastore.backing_store";
    public static final String                  NO_INDEX_AUTO_GEN_PROP             = "datastore.no_index_auto_gen";
    public static final String                  NO_STORAGE_PROPERTY                = "datastore.no_storage";
    public static final String                  HIGH_REP_JOB_POLICY_CLASS_PROPERTY = "datastore.high_replication_job_policy_class";
    private static final Pattern                RESERVED_NAME                      = Pattern.compile("^__.*__$");

    private static final Set<String>            RESERVED_NAME_WHITELIST            = new HashSet(Arrays.asList(new String[] { "__BlobUploadSession__", "__BlobInfo__", "__ProspectiveSearchSubscriptions__", "__BlobFileIndex__", "__GsFileInfo__", "__BlobServingUrl__", "__BlobChunk__" }));
    static final String                         ENTITY_GROUP_MESSAGE               = "cross-group transaction need to be explicitly specified, see TransactionOptions.Builder.withXG";
    static final String                         TOO_MANY_ENTITY_GROUP_MESSAGE      = "operating on too many entity groups in a single transaction.";
    static final String                         MULTI_EG_TXN_NOT_ALLOWED           = "transactions on multiple entity groups only allowed in High Replication applications";
    static final String                         CONTENTION_MESSAGE                 = "too much contention on these datastore entities. please try again.";
    static final String                         TRANSACTION_CLOSED                 = "transaction closed";
    static final String                         TRANSACTION_NOT_FOUND              = "transaction has expired or is invalid";
    static final String                         NAME_TOO_LONG                      = "name in key path element must be under 500 characters";
    static final String                         QUERY_NOT_FOUND                    = "query has expired or is invalid. Please restart it with the last cursor to read more results.";

    public static final String                  AUTO_ID_ALLOCATION_POLICY_PROPERTY = "datastore.auto_id_allocation_policy";

    private final AtomicLong                    queryId                            = new AtomicLong(0L);
    private String                              backingStore;
    private Map<String, Profile>                profiles                           = Collections.synchronizedMap(new HashMap());
    private Clock                               clock;
    private static final long                   MAX_BATCH_GET_KEYS                 = 1000000000L;
    private int                                 maxQueryLifetimeMs;
    private int                                 maxTransactionLifetimeMs;
    private final ScheduledThreadPoolExecutor   scheduler                          = new ScheduledThreadPoolExecutor(2, new ThreadFactory()
                                                                                   {
                                                                                       public Thread newThread( Runnable r )
                                                                                       {
                                                                                           Thread thread = new Thread(r);

                                                                                           thread.setDaemon(true);
                                                                                           return thread;
                                                                                       }
                                                                                   });

    /*
     * AppScale - removed null param from below constructors
     */
    private final RemoveStaleQueries            removeStaleQueriesTask             = new RemoveStaleQueries();

    private final RemoveStaleTransactions       removeStaleTransactionsTask        = new RemoveStaleTransactions();

    private final AtomicInteger                 transactionHandleProvider          = new AtomicInteger(0);
    private int                                 storeDelayMs;
    private boolean                             noStorage;
    private Thread                              shutdownHook;
    private LocalDatastoreCostAnalysis          costAnalysis;
    private Map<String, LocalDatastoreService.SpecialProperty>  specialPropertyMap = Maps.newHashMap();
    private String appID;

    public void clearProfiles()
    {
        this.profiles.clear();
    }

    public void clearQueryHistory()
    {
        LocalCompositeIndexManager.getInstance().clearQueryHistory();
    }

    // AppScale
    private HTTPClientDatastoreProxy proxy;

    // Setter added for unit tests
    public void setProxy( HTTPClientDatastoreProxy proxy )
    {
        this.proxy = proxy;
    }

    public LocalDatastoreService()
    {
        setMaxQueryLifetime(DEFAULT_MAX_QUERY_LIFETIME);
        setMaxTransactionLifetime(DEFAULT_MAX_TRANSACTION_LIFETIME);
        setStoreDelay(DEFAULT_STORE_DELAY_MS);
        enableScatterProperty(true);
    }

    /*
     * AppScale Replacing public void init(LocalServiceContext context,
     * Map<String, String> properties)
     */
    public void init( LocalServiceContext context, Map<String, String> properties )
    {
        this.clock = context.getClock();

        /*
         * AppScale replacement to #end
         */
        ResourceLoader res = ResourceLoader.getResourceLoader();
        String host = res.getPbServerIp();
        int port = res.getPbServerPort();
        boolean isSSL = res.getDatastoreSecurityMode();
        this.proxy = new HTTPClientDatastoreProxy(host, port, isSSL);
        /* #end */

        String storeDelayTime = (String)properties.get(STORE_DELAY_PROPERTY);
        this.storeDelayMs = parseInt(storeDelayTime, this.storeDelayMs, STORE_DELAY_PROPERTY);

        String maxQueryLifetime = (String)properties.get(MAX_QUERY_LIFETIME_PROPERTY);
        this.maxQueryLifetimeMs = parseInt(maxQueryLifetime, this.maxQueryLifetimeMs, MAX_QUERY_LIFETIME_PROPERTY);

        String maxTxnLifetime = (String)properties.get(MAX_TRANSACTION_LIFETIME_PROPERTY);
        this.maxTransactionLifetimeMs = parseInt(maxTxnLifetime, this.maxTransactionLifetimeMs, MAX_TRANSACTION_LIFETIME_PROPERTY);

        this.appID = properties.get("APP_NAME");

        LocalCompositeIndexManager.getInstance().setAppDir(context.getLocalServerEnvironment().getAppDir());

        LocalCompositeIndexManager.getInstance().setClock(this.clock);

        LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(false);

        this.costAnalysis = new LocalDatastoreCostAnalysis(LocalCompositeIndexManager.getInstance());

        logger.info("Datastore initialized");
    }

    private static int parseInt( String valStr, int defaultVal, String propName )
    {
        if (valStr != null)
        {
            try
            {
                return Integer.parseInt(valStr);
            }
            catch (NumberFormatException e)
            {
                logger.log(Level.WARNING, "Expected a numeric value for property " + propName + "but received, " + valStr + ". Resetting property to the default.");
            }
        }

        return defaultVal;
    }

    public void start()
    {
        AccessController.doPrivileged(new PrivilegedAction()
        {
            public Object run()
            {
                LocalDatastoreService.this.startInternal();
                return null;
            }
        });
    }

    private void startInternal()
    {
        /*
         * AppScale - removed this call to load load();
         */
        this.scheduler.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
        this.scheduler.scheduleWithFixedDelay(this.removeStaleQueriesTask, this.maxQueryLifetimeMs * 5, this.maxQueryLifetimeMs * 5, TimeUnit.MILLISECONDS);

        this.scheduler.scheduleWithFixedDelay(this.removeStaleTransactionsTask, this.maxTransactionLifetimeMs * 5, this.maxTransactionLifetimeMs * 5, TimeUnit.MILLISECONDS);

        this.shutdownHook = new Thread()
        {
            public void run()
            {
                LocalDatastoreService.this.stop();
            }
        };
        Runtime.getRuntime().addShutdownHook(this.shutdownHook);
    }

    public void stop()
    {
        this.scheduler.shutdown();

        clearProfiles();
        try
        {
            Runtime.getRuntime().removeShutdownHook(this.shutdownHook);
        }
        catch (IllegalStateException ex)
        {
        }
    }

    public void setMaxQueryLifetime( int milliseconds )
    {
        this.maxQueryLifetimeMs = milliseconds;
    }

    public void setMaxTransactionLifetime( int milliseconds )
    {
        this.maxTransactionLifetimeMs = milliseconds;
    }

    public void setBackingStore( String backingStore )
    {
        this.backingStore = backingStore;
    }

    public void setStoreDelay( int delayMs )
    {
        this.storeDelayMs = delayMs;
    }

    public void setNoStorage( boolean noStorage )
    {
        this.noStorage = noStorage;
    }
    
    public void enableScatterProperty(boolean enable)
    {
      if (enable)
        this.specialPropertyMap.put("__scatter__", SpecialProperty.SCATTER);
      else
        this.specialPropertyMap.remove("__scatter__");
    }

    public String getPackage()
    {
        return "datastore_v3";
    }

    /*
     * AppScale replacement of method body
     */
    public DatastoreV3Pb.GetResponse get( LocalRpcService.Status status, DatastoreV3Pb.GetRequest request )
    {
        DatastoreV3Pb.GetResponse response = new DatastoreV3Pb.GetResponse();
        proxy.doPost(request.getKey(0).getApp(), "Get", request, response);
        if (response.entitySize() == 0) response.addEntity(new GetResponse.Entity());

        return response;
    }

    public DatastoreV3Pb.PutResponse put( LocalRpcService.Status status, DatastoreV3Pb.PutRequest request )
    {
        return putImpl(status, request);
    }

    private void processEntityForSpecialProperties( OnestoreEntity.EntityProto entity, boolean store )
    {
        /*
         * AppScale - Added type Property to Iterator below in for loop
         */
        for (Iterator<Property> iter = entity.propertyIterator(); iter.hasNext();)
        {
            if (this.specialPropertyMap.containsKey(((OnestoreEntity.Property)iter.next()).getName()))
            {
                iter.remove();
            }
        }

        for (SpecialProperty specialProp : this.specialPropertyMap.values())
            if (store ? specialProp.isStored() : specialProp.isVisible())
            {
                OnestoreEntity.PropertyValue value = specialProp.getValue(entity);
                if (value != null) entity.addProperty(specialProp.getProperty(value));
            }
    }

    private DatastoreV3Pb.PutResponse putImpl( LocalRpcService.Status status, DatastoreV3Pb.PutRequest request )
    {
        DatastoreV3Pb.PutResponse response = new DatastoreV3Pb.PutResponse();
        if (request.entitySize() == 0)
        {
            return response;
        }
        String app = ((OnestoreEntity.EntityProto)request.entitys().get(0)).getKey().getApp(); 
        proxy.doPost(app, "Put", request, response);
        if (!request.hasTransaction())
        {
            logger.fine("Put: " + request.entitySize() + " entities");
        }
        return response;
    }

    private void validateAndProcessEntityProto( OnestoreEntity.EntityProto entity )
    {
        validatePathForPut(entity.getKey());
        for (OnestoreEntity.Property prop : entity.propertys())
        {
            validateAndProcessProperty(prop);
            validateLengthLimit(prop);
        }
        for (OnestoreEntity.Property prop : entity.rawPropertys())
            validateAndProcessProperty(prop);
    }

    private void validatePathForPut( OnestoreEntity.Reference key )
    {
        OnestoreEntity.Path path = key.getPath();
        for (OnestoreEntity.Path.Element ele : path.elements())
        {
            String type = ele.getType();
            if ((RESERVED_NAME.matcher(type).matches()) && (!RESERVED_NAME_WHITELIST.contains(type)))
            {
                throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, String.format("illegal key.path.element.type: %s", new Object[] { ele.getType() }));
            }

            if ((ele.hasName()) && (ele.getName().length() > 500)) throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "name in key path element must be under 500 characters");
        }
    }

    private void validateAndProcessProperty( OnestoreEntity.Property prop )
    {
        if (RESERVED_NAME.matcher(prop.getName()).matches())
        {
            throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, String.format("illegal property.name: %s", new Object[] { prop.getName() }));
        }

        OnestoreEntity.PropertyValue val = prop.getMutableValue();
        if (val.hasUserValue())
        {
            OnestoreEntity.PropertyValue.UserValue userVal = val.getMutableUserValue();
            userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail().hashCode()));
        }
    }

    private void validateLengthLimit( OnestoreEntity.Property property )
    {
        String name = property.getName();
        OnestoreEntity.PropertyValue value = property.getValue();

        if (value.hasStringValue()) if ((property.hasMeaning()) && (property.getMeaningEnum() == OnestoreEntity.Property.Meaning.ATOM_LINK))
        {
            if (value.getStringValue().length() > 2038)
            {
                throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "Link property " + name + " is too long. Use TEXT for links over " + 2038 + " characters.");
            }

        }
        else if (value.getStringValue().length() > 500) throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "string property " + name + " is too long.  It cannot exceed " + 500 + " characters.");
    }

    public DatastoreV3Pb.DeleteResponse delete( LocalRpcService.Status status, DatastoreV3Pb.DeleteRequest request )
    {
        return deleteImpl(status, request);
    }

    public ApiBasePb.VoidProto addActions( LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request )
    {
        addActionsImpl(status, request);
        return new ApiBasePb.VoidProto();
    }

    private DatastoreV3Pb.DeleteResponse deleteImpl( LocalRpcService.Status status, DatastoreV3Pb.DeleteRequest request )
    {
        DatastoreV3Pb.DeleteResponse response = new DatastoreV3Pb.DeleteResponse();
        if (request.keySize() == 0)
        {
            return response;
        }
        /*
         * AppScale replaced remainder of method
         */
        proxy.doPost(request.getKey(0).getApp(), "Delete", request, response);
        if (!request.hasTransaction())
        {
            logger.fine("deleted " + request.keySize() + " keys.");
        }
        return response;
    }

    private void addActionsImpl( LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request )
    {
        if (request.addRequestSize() == 0)
        {
            return;
        }

        String app = request.addRequests().get(0).getTransaction().getApp();
        TaskQueuePb.TaskQueueBulkAddRequest bulkAddRequest = request.clone();
        TaskQueuePb.TaskQueueBulkAddResponse bulkAddResponse = new TaskQueuePb.TaskQueueBulkAddResponse();

        // Set project ID for tasks.
        for (TaskQueuePb.TaskQueueAddRequest addRequest : bulkAddRequest.addRequests())
        {
            addRequest.setAppId(app);
        }

        proxy.doPost(app, "AddActions", bulkAddRequest, bulkAddResponse);
    }

    private OnestoreEntity.CompositeIndex fetchMatchingIndex(List<OnestoreEntity.CompositeIndex> compIndexes, OnestoreEntity.Index indexToMatch)
    {
        if (compIndexes == null)
        {
            throw new ApiProxy.ApplicationException(DatastoreV3Pb.Error.ErrorCode.NEED_INDEX.getValue(), "Missing composite index for given query");
        }
        for (OnestoreEntity.CompositeIndex compIndex : compIndexes)
        {
            OnestoreEntity.Index indexDef  = compIndex.getDefinition();
            if (indexDef.equals(indexToMatch))
            {
                return compIndex;
            }
        }
        throw new ApiProxy.ApplicationException(DatastoreV3Pb.Error.ErrorCode.NEED_INDEX.getValue(), "Missing composite index for given query");
    }

    public DatastoreV3Pb.QueryResult runQuery( LocalRpcService.Status status, DatastoreV3Pb.Query query )
    {
        final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new LocalCompositeIndexManager.ValidatedQuery(query);

        query = validatedQuery.getV3Query();
        String app = query.getApp();

        DatastoreV3Pb.QueryResult queryResult = new DatastoreV3Pb.QueryResult();
        proxy.doPost(app, "RunQuery", query, queryResult);
        int count;
        if (query.hasCount())
        {
            count = query.getCount();
        }
        else if (query.hasLimit())
        {
            count = query.getLimit();
        }
        else
        {
            count = DEFAULT_BATCH_SIZE;
        }

        LiveQuery liveQuery = new LiveQuery(query, queryResult.resultSize(), queryResult.getCompiledCursor(), this.clock);
        if (query.isCompile())
        {
            queryResult.setCompiledQuery(liveQuery.compileQuery());
        }
        if (queryResult.isMoreResults())
        {
            Profile profile = getOrCreateProfile(app);
            synchronized (profile)
            {
                long cursor = this.queryId.getAndIncrement();
                profile.addQuery(cursor, liveQuery);
                queryResult.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
            }
        }

        for (OnestoreEntity.Index index : LocalCompositeIndexManager.getInstance().queryIndexList(query))
        {
            queryResult.addIndex(wrapIndexInCompositeIndex(app, index));
        }
        /*
         * AppScale - adding skipped results to the result, otherwise query counts are wrong
         */
        return queryResult;
    }

    private static <T> T safeGetFromExpiringMap( Map<Long, T> map, long key, String errorMsg )
    {
        /*
         * AppScale - Changed "value" from type Object to T
         */
        T value = map.get(Long.valueOf(key));
        if (value == null)
        {
            throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, errorMsg);
        }
        return value;
    }

    public DatastoreV3Pb.QueryResult next( LocalRpcService.Status status, DatastoreV3Pb.NextRequest request )
    {
        Profile profile = (Profile)this.profiles.get(request.getCursor().getApp());
        LiveQuery liveQuery = profile.getQuery(request.getCursor().getCursor());

        int count = request.hasCount() ? request.getCount() : DEFAULT_BATCH_SIZE;
        DatastoreV3Pb.Query query = liveQuery.getQuery();
        query.setCount(count);
        query.clearOffset();

        DatastoreV3Pb.QueryResult queryResult = new DatastoreV3Pb.QueryResult();
        DatastoreV3Pb.CompiledCursor compiledCursor = liveQuery.getCompiledCursor();
        // If we don't have a cursor to continue, or we have hit the count we're trying to achieve
        // end this query.
        if (liveQuery.getOffset() >= liveQuery.getCount())
        {
          queryResult.setMoreResults(false);
          if (query.isCompile())
          {
            queryResult.setCompiledQuery(liveQuery.compileQuery());
          }
          queryResult.setCompiledCursor(compiledCursor); 
          profile.removeQuery(request.getCursor().getCursor());
          return queryResult;
        }
        else
        {
          // We copy over the previous cursor from which we continue.
          query.setCompiledCursor(compiledCursor);
          String app = query.getApp();
          proxy.doPost(app, "RunQuery", query, queryResult);
          liveQuery.setOffset(liveQuery.getOffset() + queryResult.resultSize());
          if (query.isCompile())
          {
            queryResult.setCompiledQuery(liveQuery.compileQuery());
          }
        }

        if (!queryResult.isMoreResults())
        {
          profile.removeQuery(request.getCursor().getCursor());
        }
        else{
          liveQuery.setCompiledCursor(queryResult.getCompiledCursor());
          queryResult.setCursor(request.getCursor());
        }
        return queryResult;
    }


    public ApiBasePb.VoidProto deleteCursor( LocalRpcService.Status status, DatastoreV3Pb.Cursor request )
    {
        Profile profile = (Profile)this.profiles.get(request.getApp());
        profile.removeQuery(request.getCursor());
        return new ApiBasePb.VoidProto();
    }

    public DatastoreV3Pb.Transaction beginTransaction( LocalRpcService.Status status, DatastoreV3Pb.BeginTransactionRequest req )
    {
        DatastoreV3Pb.Transaction txn = new DatastoreV3Pb.Transaction().setApp(req.getApp()).setHandle(this.transactionHandleProvider.getAndIncrement());

        /*
         * AppScale line replacement
         */
        proxy.doPost(req.getApp(), "BeginTransaction", req, txn);
        return txn;
    }

    public DatastoreV3Pb.CommitResponse commit( LocalRpcService.Status status, DatastoreV3Pb.Transaction req )
    {
        DatastoreV3Pb.CommitResponse response = new DatastoreV3Pb.CommitResponse();
        /*
         * AppScale - Added proxy call
         */
        proxy.doPost(req.getApp(), "Commit", req, response);
        return response;
    }

    public ApiBasePb.VoidProto rollback( LocalRpcService.Status status, DatastoreV3Pb.Transaction req )
    {
        VoidProto response = new VoidProto();
        proxy.doPost(req.getApp(), "Rollback", req, response);
        return response;
    }

    /*
     * AppScale replaced body
     */
    public ApiBasePb.Integer64Proto createIndex( LocalRpcService.Status status, OnestoreEntity.CompositeIndex req )
    {
        Integer64Proto response = new Integer64Proto();
        if (req.getId() != 0)
        {
            throw new IllegalArgumentException("New index id must be 0.");
        }
        proxy.doPost(req.getAppId(), "CreateIndex", req, response);
        return response;
    }

    /*
     * AppScale replaced body
     */
    public ApiBasePb.VoidProto updateIndex( LocalRpcService.Status status, OnestoreEntity.CompositeIndex req )
    {
        VoidProto response = new ApiBasePb.VoidProto();
        proxy.doPost(req.getAppId(), "UpdateIndex", req, response);
        return response;
    }

    private OnestoreEntity.CompositeIndex wrapIndexInCompositeIndex( String app, OnestoreEntity.Index index )
    {
        OnestoreEntity.CompositeIndex ci = new OnestoreEntity.CompositeIndex().setAppId(app).setState(OnestoreEntity.CompositeIndex.State.READ_WRITE);

        if (index != null)
        {
            ci.setDefinition(index);
        }
        return ci;
    }

    /*
     * AppScale replaced body
     */
    public DatastoreV3Pb.CompositeIndices getIndices( LocalRpcService.Status status, ApiBasePb.StringProto req )
    {
        DatastoreV3Pb.CompositeIndices answer = new DatastoreV3Pb.CompositeIndices();
        proxy.doPost(req.getValue(), "GetIndices", req, answer);
        return answer;
    }

    /*
     * AppScale - replaced body
     */
    public ApiBasePb.VoidProto deleteIndex( LocalRpcService.Status status, OnestoreEntity.CompositeIndex req )
    {
        VoidProto response = new VoidProto();
        proxy.doPost(req.getAppId(), "DeleteIndex", req, response);
        return response;
    }

    public DatastoreV3Pb.AllocateIdsResponse allocateIds( LocalRpcService.Status status, DatastoreV3Pb.AllocateIdsRequest req )
    {
        return allocateIdsImpl(req);
    }

    /*
     * AppScale - replaced body
     */
    private DatastoreV3Pb.AllocateIdsResponse allocateIdsImpl( DatastoreV3Pb.AllocateIdsRequest req )
    {
        if (req.hasSize() && req.getSize() > MAX_BATCH_GET_KEYS)
        {
            throw new ApiProxy.ApplicationException(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST.getValue(), 
              "cannot get more than " + MAX_BATCH_GET_KEYS + " keys in a single call");
        }

        DatastoreV3Pb.AllocateIdsResponse response = new DatastoreV3Pb.AllocateIdsResponse();
        proxy.doPost(this.appID, "AllocateIds", req, response);
        return response;
    }
    
    public static enum AutoIdAllocationPolicy
    {
        SEQUENTIAL, 
        SCATTERED;
    }

    private static long toScatteredId(long counter)
    {
        if (counter >= 2251799813685247L)
        {
            throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.INTERNAL_ERROR, "Maximum scattered ID counter value exceeded");
        }
        return 4503599627370496L + Long.reverse(counter << 13);
    }

    Profile getOrCreateProfile( String app )
    {
        synchronized (this.profiles)
        {
            Preconditions.checkArgument((app != null) && (app.length() > 0), "appId not set");
            Profile profile = (Profile)this.profiles.get(app);
            if (profile == null)
            {
                profile = new Profile();
                this.profiles.put(app, profile);
            }
            return profile;
        }
    }

    static void pruneHasCreationTimeMap( long now, int maxLifetimeMs, Map<Long, ? extends HasCreationTime> hasCreationTimeMap )
    {
        long deadline = now - maxLifetimeMs;
        Iterator queryIt = hasCreationTimeMap.entrySet().iterator();
        while (queryIt.hasNext())
        {
            Map.Entry entry = (Map.Entry)queryIt.next();
            HasCreationTime query = (HasCreationTime)entry.getValue();
            if (query.getCreationTime() < deadline) queryIt.remove();
        }
    }

    Map<String, SpecialProperty> getSpecialPropertyMap()
    {
        return Collections.unmodifiableMap(this.specialPropertyMap);
    }

    void removeStaleQueriesNow()
    {
        this.removeStaleQueriesTask.run();
    }

    void removeStaleTxnsNow()
    {
        this.removeStaleTransactionsTask.run();
    }

    public Double getDefaultDeadline( boolean isOfflineRequest )
    {
        return Double.valueOf(30.0D);
    }

    public Double getMaximumDeadline( boolean isOfflineRequest )
    {
        return Double.valueOf(30.0D);
    }

    public CreationCostAnalysis getCreationCostAnalysis( com.google.appengine.api.datastore.Entity e )
    {
        return this.costAnalysis.getCreationCostAnalysis(EntityTranslator.convertToPb(e));
    }

    private static void addTo( DatastoreV3Pb.Cost target, DatastoreV3Pb.Cost addMe )
    {
        target.setEntityWrites(target.getEntityWrites() + addMe.getEntityWrites());
        target.setIndexWrites(target.getIndexWrites() + addMe.getIndexWrites());
    }


    static enum SpecialProperty
    {
        SCATTER(false, true);

        private final String  name;
        private final boolean isVisible;
        private final boolean isStored;

        private SpecialProperty( boolean isVisible, boolean isStored )
        {
            this.name = ("__" + name().toLowerCase() + "__");
            this.isVisible = isVisible;
            this.isStored = isStored;
        }

        public final String getName()
        {
            return this.name;
        }

        public final boolean isVisible()
        {
            return this.isVisible;
        }

        final boolean isStored()
        {
            return this.isStored;
        }

        OnestoreEntity.PropertyValue getValue( OnestoreEntity.EntityProto entity )
        {
            /*
             * AppScale - changed to avoid UnsupportedOperationException()
             * thrown for all DB txn's.
             */
            return null;
            // CJK throw new UnsupportedOperationException();
        }

        OnestoreEntity.Property getProperty( OnestoreEntity.PropertyValue value )
        {
            OnestoreEntity.Property processedProp = new OnestoreEntity.Property();
            processedProp.setName(getName());
            processedProp.setValue(value);
            processedProp.setMultiple(false);
            return processedProp;
        }
    }

    private class RemoveStaleTransactions implements Runnable
    {
        private RemoveStaleTransactions()
        {}

        public void run()
        {
            // This has no effect since this stub does not keep track of transaction state.
        }
    }

    private class RemoveStaleQueries implements Runnable
    {
        private RemoveStaleQueries()
        {}

        public void run()
        {
            /*
             * AppScale - changed to get rid of "access$1800" which is caued by
             * accessing inner class variables
             */
            for (LocalDatastoreService.Profile profile : LocalDatastoreService.this.profiles.values())
                synchronized (profile.getQueries())
                {
                    LocalDatastoreService.pruneHasCreationTimeMap(LocalDatastoreService.this.clock.getCurrentTime(), LocalDatastoreService.this.maxQueryLifetimeMs, profile.getQueries());
                }
        }
    }
        
    class LiveQuery extends LocalDatastoreService.HasCreationTime
    {
        private final DatastoreV3Pb.Query query = new DatastoreV3Pb.Query();
        private DatastoreV3Pb.CompiledCursor lastCursor = new DatastoreV3Pb.CompiledCursor();
        private int offset = 0;
        private int totalCount = 0;

        public LiveQuery(DatastoreV3Pb.Query query, int offset, DatastoreV3Pb.CompiledCursor cursor, Clock clock )
        { 
            super(clock.getCurrentTime());
            this.query.copyFrom(query);

            // This is the number of entities this query has seen so far.
            this.offset = offset;

            this.lastCursor.copyFrom(cursor);
            if (query.hasLimit()) {
              this.totalCount = Integer.valueOf(this.query.getLimit());
            }
            else {
              this.totalCount = Integer.MAX_VALUE;
            }
        }

        public int getCount()
        {
          return this.totalCount;
        }

        public void setOffset(int offset)
        {
          this.offset = offset;
        }

        public int getOffset()
        {
          return this.offset;
        }

        public DatastoreV3Pb.Query getQuery()
        {
          return this.query;
        }

        public DatastoreV3Pb.CompiledCursor getCompiledCursor()
        {
          return this.lastCursor;
        }
       
        public void setCompiledCursor(DatastoreV3Pb.CompiledCursor cursor)
        {
          this.lastCursor.copyFrom(cursor); 
        }

        public DatastoreV3Pb.CompiledQuery compileQuery() 
        {
          DatastoreV3Pb.CompiledQuery result = new DatastoreV3Pb.CompiledQuery();
          DatastoreV3Pb.CompiledQuery.PrimaryScan scan = result.getMutablePrimaryScan();
 
          scan.setIndexNameAsBytes(this.query.toByteArray());
     
          return result;
        }
    }
 
    static class HasCreationTime
    {
        private final long creationTime;
 
        HasCreationTime( long creationTime )
        {
            this.creationTime = creationTime;
        }

        long getCreationTime()
        {
            return this.creationTime;
        }
    }


    static class Profile implements Serializable
    {
        private transient Map<Long, LocalDatastoreService.LiveQuery> queries;

        public Profile()
        {
            
        }

        public synchronized LocalDatastoreService.LiveQuery getQuery( long cursor )
        {
            return (LocalDatastoreService.LiveQuery)LocalDatastoreService.safeGetFromExpiringMap(getQueries(), cursor, "query has expired or is invalid. Please restart it with the last cursor to read more results.");
        }

        public synchronized void addQuery( long cursor, LocalDatastoreService.LiveQuery query )
        {
            getQueries().put(Long.valueOf(cursor), query);
        }

        private synchronized LocalDatastoreService.LiveQuery removeQuery( long cursor )
        {
            LocalDatastoreService.LiveQuery query = getQuery(cursor);
            this.queries.remove(Long.valueOf(cursor));
            return query;
        }

        private synchronized Map<Long, LocalDatastoreService.LiveQuery> getQueries()
        {
            if (this.queries == null)
            {
                this.queries = new HashMap();
            }
            return this.queries;
        }
    }
}
