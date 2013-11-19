package com.google.appengine.api.datastore.dev;


import com.google.appengine.api.datastore.EntityProtoComparators;
import com.google.appengine.api.datastore.EntityProtoComparators.EntityProtoComparator;
import com.google.appengine.api.datastore.EntityTranslator;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddRequest;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.base.Predicate;
import com.google.appengine.repackaged.com.google.common.base.Predicates;
import com.google.appengine.repackaged.com.google.common.collect.HashMultimap;
import com.google.appengine.repackaged.com.google.common.collect.Iterables;
import com.google.appengine.repackaged.com.google.common.collect.Iterators;
import com.google.appengine.repackaged.com.google.common.collect.Lists;
import com.google.appengine.repackaged.com.google.common.collect.Maps;
import com.google.appengine.repackaged.com.google.common.collect.Multimap;
import com.google.appengine.repackaged.com.google.common.collect.Sets;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiBasePb.Integer64Proto;
import com.google.apphosting.api.ApiBasePb.StringProto;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.datastore.DatastoreV3Pb;
import com.google.apphosting.datastore.DatastoreV3Pb.AllocateIdsRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.AllocateIdsResponse;
import com.google.apphosting.datastore.DatastoreV3Pb.BeginTransactionRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.CommitResponse;
import com.google.apphosting.datastore.DatastoreV3Pb.CompositeIndices;
import com.google.apphosting.datastore.DatastoreV3Pb.Cost;
import com.google.apphosting.datastore.DatastoreV3Pb.Cursor;
import com.google.apphosting.datastore.DatastoreV3Pb.DeleteRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.DeleteResponse;
import com.google.apphosting.datastore.DatastoreV3Pb.Error.ErrorCode;
import com.google.apphosting.datastore.DatastoreV3Pb.GetRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.GetResponse;
import com.google.apphosting.datastore.DatastoreV3Pb.GetResponse.Entity;
import com.google.apphosting.datastore.DatastoreV3Pb.NextRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.PutRequest;
import com.google.apphosting.datastore.DatastoreV3Pb.PutResponse;
import com.google.apphosting.datastore.DatastoreV3Pb.Query;
import com.google.apphosting.datastore.DatastoreV3Pb.Query.Order;
import com.google.apphosting.datastore.DatastoreV3Pb.Query.Order.Direction;
import com.google.apphosting.datastore.DatastoreV3Pb.QueryResult;
import com.google.apphosting.datastore.DatastoreV3Pb.Transaction;
import com.google.apphosting.utils.config.GenerationDirectory;
import com.google.apphosting.utils.config.IndexesXmlReader;
import com.google.apphosting.utils.config.IndexesXml;
//import com.google.apphosting.utils.config.IndexesXml.Index;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.CompositeIndex;
import com.google.storage.onestore.v3.OnestoreEntity.CompositeIndex.State;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;
import com.google.storage.onestore.v3.OnestoreEntity.Index;
import com.google.storage.onestore.v3.OnestoreEntity.Path;
import com.google.storage.onestore.v3.OnestoreEntity.Path.Element;
import com.google.storage.onestore.v3.OnestoreEntity.Property;
import com.google.storage.onestore.v3.OnestoreEntity.Property.Meaning;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue.UserValue;
import com.google.storage.onestore.v3.OnestoreEntity.Reference;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.security.AccessController;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.PrivilegedAction;
import java.security.PrivilegedActionException;
import java.security.PrivilegedExceptionAction;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/*
 * AppScale addition to #end
 */
import com.google.appengine.tools.resources.ResourceLoader;
import org.apache.http.*;


/* #end */

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService extends AbstractLocalRpcService
{
    private static final Logger                 logger                             = Logger.getLogger(LocalDatastoreService.class.getName());
    private static final long                   CURRENT_STORAGE_VERSION            = 1L;
    private final String                        APPLICATION_ID_PROPERTY            = "APPLICATION_ID";
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
    private final AtomicLong                    entityId                           = new AtomicLong(1L);

    private static final long                   MAX_SEQUENTIAL_BIT                 = 52L;
    private static final long                   MAX_SEQUENTIAL_COUNTER             = 4503599627370495L;
    private static final long                   MAX_SEQUENTIAL_ID                  = 4503599627370495L;
    private static final long                   MAX_SCATTERED_COUNTER              = 2251799813685247L;
    private static final long                   SCATTER_SHIFT                      = 13L;
    public static final String                  AUTO_ID_ALLOCATION_POLICY_PROPERTY = "datastore.auto_id_allocation_policy";
    private final AtomicLong                    entityIdSequential                 = new AtomicLong(1L);
    private final AtomicLong                    entityIdScattered                  = new AtomicLong(1L);
    private LocalDatastoreService.AutoIdAllocationPolicy       autoIdAllocationPolicy             = LocalDatastoreService.AutoIdAllocationPolicy.SEQUENTIAL;

    private final AtomicLong                    queryId                            = new AtomicLong(0L);
    private String                              backingStore;
    private Map<String, Profile>                profiles                           = Collections.synchronizedMap(new HashMap());
    private Clock                               clock;
    private static final long                   MAX_BATCH_GET_KEYS                 = 1000000000L;
    private static final long                   MAX_ACTIONS_PER_TXN                = 5L;
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

    private final PersistDatastore              persistDatastoreTask               = new PersistDatastore();

    private final AtomicInteger                 transactionHandleProvider          = new AtomicInteger(0);
    private int                                 storeDelayMs;
    private volatile boolean                    dirty;
    private final ReadWriteLock                 globalLock                         = new ReentrantReadWriteLock();
    private boolean                             noStorage;
    private Thread                              shutdownHook;
    private PseudoKinds                         pseudoKinds;
    private HighRepJobPolicy                    highRepJobPolicy;
    private boolean                             isHighRep;
    private LocalDatastoreCostAnalysis          costAnalysis;
    private Map<String, LocalDatastoreService.SpecialProperty>  specialPropertyMap = Maps.newHashMap();
    private IndexesXml                          indexes                           = null;
    private HashMap<String, List<OnestoreEntity.CompositeIndex>>   compositeIndexCache    = new HashMap<String, List<OnestoreEntity.CompositeIndex>>();

    public void clearProfiles()
    {
        for (Profile profile : this.profiles.values())
        {
            LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
            if (fullTextIndex != null)
            {
                fullTextIndex.close();
            }
        }
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

        String autoIdAllocationPolicyString = (String)properties.get("datastore.auto_id_allocation_policy");
        if (autoIdAllocationPolicyString != null) {
          try {
            this.autoIdAllocationPolicy = AutoIdAllocationPolicy.valueOf(autoIdAllocationPolicyString.toUpperCase());
          }
          catch (IllegalArgumentException e) {
            throw new IllegalStateException(String.format("Invalid value \"%s\" for property \"%s\"", new Object[] { autoIdAllocationPolicyString, "datastore.auto_id_allocation_policy" }), e);
          }

        }

        LocalCompositeIndexManager.getInstance().setAppDir(context.getLocalServerEnvironment().getAppDir());

        LocalCompositeIndexManager.getInstance().setClock(this.clock);

        String noIndexAutoGenProp = (String)properties.get(NO_INDEX_AUTO_GEN_PROP);
        if (noIndexAutoGenProp != null)
        {
            LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(Boolean.valueOf(noIndexAutoGenProp).booleanValue());
        }

        initHighRepJobPolicy(properties);

        this.pseudoKinds = new PseudoKinds();
        this.pseudoKinds.register(new KindPseudoKind(this));
        this.pseudoKinds.register(new PropertyPseudoKind(this));
        this.pseudoKinds.register(new NamespacePseudoKind(this));
        if (isHighRep())
        {
            this.pseudoKinds.register(new EntityGroupPseudoKind());
        }

        this.costAnalysis = new LocalDatastoreCostAnalysis(LocalCompositeIndexManager.getInstance());

	//DATASTORE INDEX STUFF
        setupIndexes(properties.get("user.dir"));
        
        logger.info(String.format("Local Datastore initialized: \n\tType: %s\n\tStorage: %s", new Object[] { isHighRep() ? "High Replication" : "Master/Slave", this.noStorage ? "In-memory" : this.backingStore }));
    }

    private void setupIndexes(String appDir)
    {
        IndexesXmlReader xmlReader = new IndexesXmlReader(appDir);
        indexes = xmlReader.readIndexesXml();
        DatastoreV3Pb.CompositeIndices requestedCompositeIndices = new DatastoreV3Pb.CompositeIndices();
        for (IndexesXml.Index index : indexes)
        {
            System.out.println("Index: " + index.getKind() + ", " + index.doIndexAncestors() + ", properties: " + index.getProperties());
            OnestoreEntity.CompositeIndex newCompositeIndex = requestedCompositeIndices.addIndex();
            newCompositeIndex.setAppId(getAppId());
            OnestoreEntity.Index requestedIndex = newCompositeIndex.getMutableDefinition();
            requestedIndex.setAncestor(index.doIndexAncestors());
            requestedIndex.setEntityType(index.getKind());
            for (IndexesXml.PropertySort propSort : index.getProperties())
            {
                OnestoreEntity.Index.Property newProp = requestedIndex.addProperty();
                newProp.setName(propSort.getPropertyName());
                if (propSort.isAscending()) 
                {
                    //ENUM IS IN ONESTOREENTITY in Appengine-api.jar
                    newProp.setDirection(1);
                }
                else 
                { 
                    newProp.setDirection(2);
                }
            }
        }
      System.out.println("done with indexes");
      System.out.println("requestedCompositeIndices: " + requestedCompositeIndices);
      System.out.println("more stuff: " + requestedCompositeIndices.getIndex(0).getDefinition().getEntityType()); 
        
      ApiBasePb.StringProto appId = new ApiBasePb.StringProto();
      appId.setValue(getAppId()); 
      DatastoreV3Pb.CompositeIndices existing = getIndices( null, appId);  
      System.out.println("existing: " + existing);

      createAndDeleteIndexes(existing, requestedCompositeIndices);
     
    }

    private void createAndDeleteIndexes( DatastoreV3Pb.CompositeIndices existing, DatastoreV3Pb.CompositeIndices requested)
    {
        HashMap existingMap = new HashMap<String, OnestoreEntity.CompositeIndex>();
        HashMap requestedMap = new HashMap<String, OnestoreEntity.CompositeIndex>();
        // Convert CompositeIndices into hash maps to get the diff of existing and requested indices. 
        for (int ctr = 0; ctr < existing.indexSize(); ctr++)
        {
            System.out.println("getting index in loop 1");
            OnestoreEntity.CompositeIndex compIndex = existing.getIndex(ctr);
            existingMap.put(compIndex.getDefinition().toFlatString(), compIndex);
            System.out.println("Map1 putting: " + compIndex.getDefinition().toFlatString());
        }
        for (int ctr = 0; ctr < requested.indexSize(); ctr++)
        {
            System.out.println("getting index in loop 2");
            OnestoreEntity.CompositeIndex compIndex = requested.getIndex(ctr);
            requestedMap.put(compIndex.getDefinition().toFlatString(), compIndex);
            System.out.println("Map2 putting: " + compIndex.getDefinition().toFlatString());
        }

        int deletedCounter = 0;
        for (String key : (Set<String>)existingMap.keySet())
        {
            if (requestedMap.containsKey(key) == false)
            {
                //Need to map the composite index id into the requested deleted thing.
                OnestoreEntity.CompositeIndex tmpCompIndex = (OnestoreEntity.CompositeIndex)existingMap.get(key);
                deleteIndex(null, tmpCompIndex);
                deletedCounter++;
            }
            else
            {
                OnestoreEntity.CompositeIndex tmpCompIndex = (OnestoreEntity.CompositeIndex)existingMap.get(key);
                String kind = tmpCompIndex.getDefinition().getEntityType();
                List<OnestoreEntity.CompositeIndex> list = compositeIndexCache.get(kind);
                if (list == null)
                {
                    List<OnestoreEntity.CompositeIndex> newList = new ArrayList<OnestoreEntity.CompositeIndex>();
                    newList.add(tmpCompIndex);
                    compositeIndexCache.put(kind, newList);
                }
                else
                {
                    list.add(tmpCompIndex);
                }
                System.out.println("adding " + kind + " to index cache");
            }
        }
        System.out.println("Deleted Indexes: " + deletedCounter);

        int createdCounter = 0;
        for (String key : (Set<String>)requestedMap.keySet())
        {
            if (existingMap.containsKey(key) == false)
            {
                ApiBasePb.Integer64Proto id = createIndex( null, (OnestoreEntity.CompositeIndex)requestedMap.get(key));
                createdCounter++;
                //Add to the cache
                OnestoreEntity.CompositeIndex tmpCompIndex = (OnestoreEntity.CompositeIndex)requestedMap.get(key);
                tmpCompIndex.setId(id.getValue());
                String kind = tmpCompIndex.getDefinition().getEntityType();
                List<OnestoreEntity.CompositeIndex> list = compositeIndexCache.get(kind);
                if (list == null)
                {
                    List<OnestoreEntity.CompositeIndex> newList = new ArrayList<OnestoreEntity.CompositeIndex>();
                    newList.add(tmpCompIndex);
                    compositeIndexCache.put(kind, newList);
                }
                else
                {
                    list.add(tmpCompIndex);
                }
                System.out.println("Adding " + kind + " when index was created");
            }
        }
        System.out.println("Created Indexes: " + createdCounter);
    }

    boolean isHighRep()
    {
        return this.isHighRep;
    }

    private void initHighRepJobPolicy( Map<String, String> properties )
    {
        String highRepJobPolicyStr = (String)properties.get(HIGH_REP_JOB_POLICY_CLASS_PROPERTY);
        if (highRepJobPolicyStr == null)
        {
            DefaultHighRepJobPolicy defaultPolicy = new DefaultHighRepJobPolicy(properties);

            this.isHighRep = (defaultPolicy.unappliedJobCutoff > 0);
            this.highRepJobPolicy = defaultPolicy;
        }
        else
        {
            this.isHighRep = true;
            try
            {
                Class highRepJobPolicyCls = Class.forName(highRepJobPolicyStr);
                Constructor ctor = highRepJobPolicyCls.getDeclaredConstructor(new Class[0]);

                ctor.setAccessible(true);

                this.highRepJobPolicy = ((HighRepJobPolicy)ctor.newInstance(new Object[0]));
            }
            catch (ClassNotFoundException e)
            {
                throw new IllegalArgumentException(e);
            }
            catch (InvocationTargetException e)
            {
                throw new IllegalArgumentException(e);
            }
            catch (NoSuchMethodException e)
            {
                throw new IllegalArgumentException(e);
            }
            catch (InstantiationException e)
            {
                throw new IllegalArgumentException(e);
            }
            catch (IllegalAccessException e)
            {
                throw new IllegalArgumentException(e);
            }
        }
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

        if (!this.noStorage)
        {
            this.scheduler.scheduleWithFixedDelay(this.persistDatastoreTask, this.storeDelayMs, this.storeDelayMs, TimeUnit.MILLISECONDS);
        }

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
        if (!this.noStorage)
        {
            rollForwardAllUnappliedJobs();
            this.persistDatastoreTask.run();
        }

        clearProfiles();
        try
        {
            Runtime.getRuntime().removeShutdownHook(this.shutdownHook);
        }
        catch (IllegalStateException ex)
        {
        }
    }

    private void rollForwardAllUnappliedJobs()
    {
        for (Profile profile : this.profiles.values())
            if (profile.getGroups() != null) for (LocalDatastoreService.Profile.EntityGroup eg : profile.getGroups().values())
                eg.rollForwardUnappliedJobs();
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
        try
        {
            this.globalLock.readLock().lock();
            return putImpl(status, request);
        }
        finally
        {
            this.globalLock.readLock().unlock();
        }
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

    public DatastoreV3Pb.PutResponse putImpl( LocalRpcService.Status status, DatastoreV3Pb.PutRequest request )
    {
        Set<String> entityKinds = new HashSet<String>();
        for (OnestoreEntity.EntityProto entity : request.entitys())
        {
            String kind = entity.getKey().getPath().getElement(entity.getKey().getPath().elementSize()-1).getType();
            entityKinds.add(kind);
        }
        for (String kind : entityKinds)
        {
            List<OnestoreEntity.CompositeIndex> compIndexes = compositeIndexCache.get(kind);
            if (compIndexes != null)
            {
                for (OnestoreEntity.CompositeIndex index : compIndexes)
                {
                    System.out.println("created index on put request");
                    request.addCompositeIndex(index);    
                }
            }
        }
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
        try
        {
            this.globalLock.readLock().lock();
            return deleteImpl(status, request);
        }
        finally
        {
            this.globalLock.readLock().unlock();
        }
    }

    public ApiBasePb.VoidProto addActions( LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request )
    {
        try
        {
            this.globalLock.readLock().lock();
            addActionsImpl(status, request);
        }
        finally
        {
            this.globalLock.readLock().unlock();
        }
        return new ApiBasePb.VoidProto();
    }

    private OnestoreEntity.Path getGroup( OnestoreEntity.Reference key )
    {
        OnestoreEntity.Path path = key.getPath();
        OnestoreEntity.Path group = new OnestoreEntity.Path();
        group.addElement(path.getElement(0));
        return group;
    }

    public DatastoreV3Pb.DeleteResponse deleteImpl( LocalRpcService.Status status, DatastoreV3Pb.DeleteRequest request )
    {
        Set<String> entityKinds = new HashSet<String>();
        for (OnestoreEntity.Reference key : request.keys())
        {
            String kind = key.getPath().getElement(key.getPath().elementSize()-1).getType();
            entityKinds.add(kind);
        }
        for (String kind : entityKinds)
        {
            List<OnestoreEntity.CompositeIndex> compIndexes = compositeIndexCache.get(kind);
            if (compIndexes != null)
            {
                for (OnestoreEntity.CompositeIndex index : compIndexes)
                {
                    System.out.println("created index on put request");
                    request.setMarkChanges(true);    
                }
            }
        }         
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

        List addRequests = new ArrayList(request.addRequestSize());

        for (TaskQueuePb.TaskQueueAddRequest addRequest : request.addRequests())
        {
            addRequests.add(((TaskQueuePb.TaskQueueAddRequest)addRequest.clone()).clearTransaction());
        }

        Profile profile = (Profile)this.profiles.get(((TaskQueuePb.TaskQueueAddRequest)request.addRequests().get(0)).getTransaction().getApp());
        LiveTxn liveTxn = profile.getTxn(((TaskQueuePb.TaskQueueAddRequest)request.addRequests().get(0)).getTransaction().getHandle());
        liveTxn.addActions(addRequests);
    }

    public DatastoreV3Pb.QueryResult runQuery( LocalRpcService.Status status, DatastoreV3Pb.Query query )
    {
        final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new LocalCompositeIndexManager.ValidatedQuery(query);

        query = validatedQuery.getV3Query();

        String app = query.getApp();
        Profile profile = getOrCreateProfile(app);

        synchronized (profile)
        {
            if ((query.hasTransaction()) || (query.hasAncestor()))
            {
                OnestoreEntity.Path groupPath = getGroup(query.getAncestor());
                LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup(groupPath);
                if (query.hasTransaction())
                {
                    if (!app.equals(query.getTransaction().getApp()))
                    {
                        throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.INTERNAL_ERROR, "Can't query app " + app + "in a transaction on app " + query.getTransaction().getApp());
                    }

                    LiveTxn liveTxn = profile.getTxn(query.getTransaction().getHandle());

                    eg.addTransaction(liveTxn);
                }

                if ((query.hasAncestor()) && ((query.hasTransaction()) || (!query.hasFailoverMs())))
                {
                    eg.rollForwardUnappliedJobs();
                }

            }

            LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
            if ((query.hasSearchQuery()) && (fullTextIndex == null))
            {
                throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "full-text search unsupported");
            }

            /*
             * AppScale line replacement to #end
             */
            DatastoreV3Pb.QueryResult queryResult = new DatastoreV3Pb.QueryResult();
            proxy.doPost(app, "RunQuery", query, queryResult);
            List<EntityProto> queryEntities = new ArrayList<EntityProto>(queryResult.results());
            /* #end */

            if (queryEntities == null)
            {
                Map extents = profile.getExtents();
                Extent extent = (Extent)extents.get(query.getKind());

                if (!query.hasSearchQuery())
                {
                    if (extent != null)
                    {
                        queryEntities = new ArrayList(extent.getEntities().values());
                    }
                    else if (!query.hasKind())
                    {
                        queryEntities = profile.getAllEntities();
                        if (query.orderSize() == 0)
                        {
                            query.addOrder(new DatastoreV3Pb.Query.Order().setDirection(DatastoreV3Pb.Query.Order.Direction.ASCENDING).setProperty("__key__"));
                        }
                    }

                }
                else
                {
                    /*
                     * AppScale - Added type to keys below
                     */
                    List<OnestoreEntity.Reference> keys = fullTextIndex.search(query.getKind(), query.getSearchQuery());
                    List entities = new ArrayList(keys.size());
                    for (OnestoreEntity.Reference key : keys)
                    {
                        entities.add(extent.getEntities().get(key));
                    }
                    queryEntities = entities;
                }

            }

            profile.groom();

            if (queryEntities == null)
            {
                queryEntities = Collections.emptyList();
            }

            List predicates = new ArrayList();

            if (query.hasAncestor())
            {
                final List ancestorPath = query.getAncestor().getPath().elements();
                predicates.add(new Predicate()
                {
                    public boolean apply( Object entity )
                    {
                        /*
                         * AppScale - Added type to entity below
                         */
                        List path = ((OnestoreEntity.EntityProto)entity).getKey().getPath().elements();
                        return (path.size() >= ancestorPath.size()) && (path.subList(0, ancestorPath.size()).equals(ancestorPath));
                    }

                });
            }

            final boolean hasNamespace = query.hasNameSpace();
            final String namespace = query.getNameSpace();
            predicates.add(new Predicate()
            {
                /*
                 * Added type to entity below
                 */
                public boolean apply( Object entity )
                {
                    OnestoreEntity.Reference ref = ((OnestoreEntity.EntityProto)entity).getKey();

                    if (hasNamespace)
                    {
                        if ((!ref.hasNameSpace()) || (!namespace.equals(ref.getNameSpace())))
                        {
                            return false;
                        }
                    }
                    else if (ref.hasNameSpace())
                    {
                        return false;
                    }

                    return true;
                }
            });
            final EntityProtoComparators.EntityProtoComparator entityComparator = new EntityProtoComparators.EntityProtoComparator(validatedQuery.getQuery().orders(), validatedQuery.getQuery().filters());

            predicates.add(new Predicate()
            {
                public boolean apply( Object entity )
                {
                    /*
                     * AppScale - Added cast to entity below
                     */
                    return entityComparator.matches((EntityProto)entity);
                }
            });
            Predicate queryPredicate = Predicates.not(Predicates.and(predicates));

            Iterators.removeIf(queryEntities.iterator(), queryPredicate);

            if (query.propertyNameSize() > 0)
            {
                queryEntities = createIndexOnlyQueryResults(queryEntities, entityComparator);
            }

            Collections.sort(queryEntities, entityComparator);

            LiveQuery liveQuery = new LiveQuery(queryEntities, query, entityComparator, this.clock);

            AccessController.doPrivileged(new PrivilegedAction()
            {
                public Object run()
                {
                    LocalCompositeIndexManager.getInstance().processQuery(validatedQuery.getV3Query());
                    return null;
                }
            });
            /*
             * AppScale - removed duplicate count instantiations
             */
            int count;
            if (query.hasCount())
            {
                count = query.getCount();
            }
            else
            {
                if (query.hasLimit())
                    count = query.getLimit();
                else
                {
                    count = 20;
                }
            }
            DatastoreV3Pb.QueryResult result = liveQuery.nextResult(query.hasOffset() ? Integer.valueOf(query.getOffset()) : null, count, query.isCompile());
            if (query.isCompile())
            {
                result.setCompiledQuery(liveQuery.compileQuery());
            }
            if (result.isMoreResults())
            {
                long cursor = this.queryId.getAndIncrement();
                profile.addQuery(cursor, liveQuery);
                result.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
            }

            for (OnestoreEntity.Index index : LocalCompositeIndexManager.getInstance().queryIndexList(query))
            {
                result.addIndex(wrapIndexInCompositeIndex(app, index));
            } 
            /*
             * AppScale - adding skipped results to the result, otherwise query counts are wrong	
             */	
            result.setSkippedResults(queryResult.getSkippedResults());
            return result;
        }
    }

    private List<OnestoreEntity.EntityProto> createIndexOnlyQueryResults( List<OnestoreEntity.EntityProto> queryEntities, EntityProtoComparators.EntityProtoComparator entityComparator )
    {
        Set postfixProps = Sets.newHashSetWithExpectedSize(entityComparator.getAdjustedOrders().size());

        for (DatastorePb.Query.Order order : entityComparator.getAdjustedOrders())
        {
            postfixProps.add(order.getProperty());
        }

        List results = Lists.newArrayListWithExpectedSize(queryEntities.size());
        for (OnestoreEntity.EntityProto entity : queryEntities)
        {
            List indexEntities = createIndexEntities(entity, postfixProps, entityComparator);
            results.addAll(indexEntities);
        }

        return results;
    }

    private List<OnestoreEntity.EntityProto> createIndexEntities( OnestoreEntity.EntityProto entity, Set<String> postfixProps, EntityProtoComparators.EntityProtoComparator entityComparator )
    {
        Multimap toSplit = HashMultimap.create(postfixProps.size(), 1);
        Set seen = Sets.newHashSet();
        boolean splitRequired = false;
        for (OnestoreEntity.Property prop : entity.propertys())
        {
            if (postfixProps.contains(prop.getName()))
            {
                splitRequired |= !seen.add(prop.getName());

                if (entityComparator.matches(prop))
                {
                    toSplit.put(prop.getName(), prop.getValue());
                }
            }
        }

        if (!splitRequired)
        {
            return Collections.singletonList(entity);
        }

        OnestoreEntity.EntityProto clone = new OnestoreEntity.EntityProto();
        clone.getMutableKey().copyFrom(entity.getKey());
        clone.getMutableEntityGroup();
        List results = Lists.newArrayList(new OnestoreEntity.EntityProto[] { clone });

        for (Map.Entry entry : ((Set<Map.Entry>)toSplit.asMap().entrySet()))
            if (((Collection)entry.getValue()).size() == 1)
            {
                /*
                 * AppScale - Added cast to results below
                 */
                for (OnestoreEntity.EntityProto result : ((List<OnestoreEntity.EntityProto>)results))
                {
                    result.addProperty().setName((String)entry.getKey()).setMeaning(OnestoreEntity.Property.Meaning.INDEX_VALUE).getMutableValue().copyFrom(((PropertyValue)((ProtocolMessage)Iterables.getOnlyElement((Iterable)entry.getValue()))));
                }

            }
            else
            {
                List splitResults = Lists.newArrayListWithCapacity(results.size() * ((Collection)entry.getValue()).size());

                for (Iterator i$ = ((Collection)entry.getValue()).iterator(); i$.hasNext();)
                {
                    /*
                     * AppScale - Added type to value below
                     */
                    OnestoreEntity.PropertyValue value = (OnestoreEntity.PropertyValue)i$.next();
                    /*
                     * AppScale - Added type to results below
                     */
                    for (OnestoreEntity.EntityProto result : (List<OnestoreEntity.EntityProto>)results)
                    {
                        OnestoreEntity.EntityProto split = (OnestoreEntity.EntityProto)result.clone();
                        split.addProperty().setName((String)entry.getKey()).setMeaning(OnestoreEntity.Property.Meaning.INDEX_VALUE).getMutableValue().copyFrom(value);

                        splitResults.add(split);
                    }
                }
                OnestoreEntity.PropertyValue value;
                results = splitResults;
            }
        return results;
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

        int count = request.hasCount() ? request.getCount() : 20;
        DatastoreV3Pb.QueryResult result = liveQuery.nextResult(request.hasOffset() ? Integer.valueOf(request.getOffset()) : null, count, request.isCompile());

        if (result.isMoreResults())
            result.setCursor(request.getCursor());
        else
        {
            profile.removeQuery(request.getCursor().getCursor());
        }

        return result;
    }


    public ApiBasePb.VoidProto deleteCursor( LocalRpcService.Status status, DatastoreV3Pb.Cursor request )
    {
        Profile profile = (Profile)this.profiles.get(request.getApp());
        profile.removeQuery(request.getCursor());
        return new ApiBasePb.VoidProto();
    }

    public DatastoreV3Pb.Transaction beginTransaction( LocalRpcService.Status status, DatastoreV3Pb.BeginTransactionRequest req )
    {
        Profile profile = getOrCreateProfile(req.getApp());
        DatastoreV3Pb.Transaction txn = new DatastoreV3Pb.Transaction().setApp(req.getApp()).setHandle(this.transactionHandleProvider.getAndIncrement());

        /*
         * AppScale line replacement
         */
        proxy.doPost(req.getApp(), "BeginTransaction", req, txn);
        profile.addTxn(txn.getHandle(), new LiveTxn(this.clock, req.isAllowMultipleEg()));
        return txn;
    }

    public DatastoreV3Pb.CommitResponse commit( LocalRpcService.Status status, DatastoreV3Pb.Transaction req )
    {
        Profile profile = (Profile)this.profiles.get(req.getApp());
        DatastoreV3Pb.CommitResponse response = new DatastoreV3Pb.CommitResponse();
        /*
         * AppScale - Added proxy call
         */
        proxy.doPost(req.getApp(), "Commit", req, response);

        synchronized (profile)
        {
            LiveTxn liveTxn = profile.removeTxn(req.getHandle());
            /*
             * AppScale removed if block
             */
            for (TaskQueuePb.TaskQueueAddRequest action : liveTxn.getActions())
            {
                try
                {
                    ApiProxy.makeSyncCall("taskqueue", "Add", action.toByteArray());
                }
                catch (ApiProxy.ApplicationException e)
                {
                    logger.log(Level.WARNING, "Transactional task: " + action + " has been dropped.", e);
                }
            }
        }
        return response;
    }

    private DatastoreV3Pb.Cost commitImpl( LiveTxn liveTxn, final Profile profile )
    {
        for (EntityGroupTracker tracker : liveTxn.getAllTrackers())
        {
            tracker.checkEntityGroupVersion();
        }

        int deleted = 0;
        int written = 0;
        DatastoreV3Pb.Cost totalCost = new DatastoreV3Pb.Cost();
        for (EntityGroupTracker tracker : liveTxn.getAllTrackers())
        {
            LocalDatastoreService.Profile.EntityGroup eg = tracker.getEntityGroup();
            eg.incrementVersion();

            final Collection writtenEntities = tracker.getWrittenEntities();
            final Collection deletedKeys = tracker.getDeletedKeys();
            LocalDatastoreJob job = new LocalDatastoreJob(this.highRepJobPolicy, eg.pathAsKey())
            {
                private DatastoreV3Pb.Cost calculateJobCost( boolean apply )
                {
                    DatastoreV3Pb.Cost cost = LocalDatastoreService.this.calculatePutCost(apply, profile, writtenEntities);
                    /*
                     * AppScale - Before: LocalDatastoreService.addTo(cost,
                     * LocalDatastoreService
                     * .access$700(LocalDatastoreService.this, apply, profile,
                     * deletedKeys)); After (2lines):
                     */
                    DatastoreV3Pb.Cost cost2 = LocalDatastoreService.this.calculateDeleteCost(apply, profile, deletedKeys);
                    LocalDatastoreService.addTo(cost, cost2); // CJK
                    return cost;
                }

                DatastoreV3Pb.Cost calculateJobCost()
                {
                    return calculateJobCost(false);
                }

                DatastoreV3Pb.Cost applyInternal()
                {
                    return calculateJobCost(true);
                }
            };
            addTo(totalCost, eg.addJob(job));
            deleted += deletedKeys.size();
            written += writtenEntities.size();
        }
        logger.fine("committed: " + written + " puts, " + deleted + " deletes in " + liveTxn.getAllTrackers().size() + " entity groups");

        return totalCost;
    }

    /*
     * AppScale body replaced CJK: Keeping removeTxn in this method b/c
     * removeTxn in commit(..) above is kept
     */
    public ApiBasePb.VoidProto rollback( LocalRpcService.Status status, DatastoreV3Pb.Transaction req )
    {
        ((Profile)this.profiles.get(req.getApp())).removeTxn(req.getHandle());
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
        try
        {
            this.globalLock.readLock().lock();
            return allocateIdsImpl(req);
        }
        finally
        {
            this.globalLock.readLock().unlock();
        }
    }

    /*
     * AppScale - replaced body
     */
    private DatastoreV3Pb.AllocateIdsResponse allocateIdsImpl( DatastoreV3Pb.AllocateIdsRequest req )
    {
        if (req.hasSize() && req.getSize() > MAX_BATCH_GET_KEYS)
        {
            throw new ApiProxy.ApplicationException(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST.getValue(), "cannot get more than " + MAX_BATCH_GET_KEYS + " keys in a single call");
        }

        DatastoreV3Pb.AllocateIdsResponse response = new DatastoreV3Pb.AllocateIdsResponse();
        proxy.doPost(getAppId(), "AllocateIds", req, response);
        return response;
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

    Extent getOrCreateExtent( Profile profile, String kind )
    {
        Map extents = profile.getExtents();
        synchronized (extents)
        {
            Extent e = (Extent)extents.get(kind);
            if (e == null)
            {
                e = new Extent();
                extents.put(kind, e);
            }
            return e;
        }
    }

    private void load()
    {
        if (this.noStorage)
        {
            return;
        }
        File backingStoreFile = new File(this.backingStore);
        String path = backingStoreFile.getAbsolutePath();
        if (!backingStoreFile.exists())
        {
            logger.log(Level.INFO, "The backing store, " + path + ", does not exist. " + "It will be created.");

            return;
        }
        try
        {
            long start = this.clock.getCurrentTime();
            ObjectInputStream objectIn = new ObjectInputStream(new BufferedInputStream(new FileInputStream(this.backingStore)));

            long version = -objectIn.readLong();
            if (version < 0L)
            {
                this.entityIdSequential.set(-version);
            }     
            else 
            {
                this.entityIdSequential.set(objectIn.readLong());
                this.entityIdScattered.set(objectIn.readLong());
            }            

            Map profilesOnDisk = (Map)objectIn.readObject();
            this.profiles = profilesOnDisk;

            objectIn.close();
            long end = this.clock.getCurrentTime();

            logger.log(Level.INFO, "Time to load datastore: " + (end - start) + " ms");
        }
        catch (FileNotFoundException e)
        {
            logger.log(Level.SEVERE, "Failed to find the backing store, " + path);
        }
        catch (IOException e)
        {
            logger.log(Level.INFO, "Failed to load from the backing store, " + path, e);
        }
        catch (ClassNotFoundException e)
        {
            logger.log(Level.INFO, "Failed to load from the backing store, " + path, e);
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

    private DatastoreV3Pb.Cost calculatePutCost( boolean apply, Profile profile, Collection<OnestoreEntity.EntityProto> entities )
    {
        DatastoreV3Pb.Cost totalCost = new DatastoreV3Pb.Cost();
        for (OnestoreEntity.EntityProto entityProto : entities)
        {
            String kind = Utils.getKind(entityProto.getKey());
            Extent extent = getOrCreateExtent(profile, kind);
            OnestoreEntity.EntityProto oldEntity;
            if (apply)
            {
                /*
                 * AppScale - removed type declaration from oldEntity below
                 */
                oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().put(entityProto.getKey(), entityProto);

                LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
                if (fullTextIndex != null) fullTextIndex.write(entityProto);
            }
            else
            {
                oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().get(entityProto.getKey());
            }
            addTo(totalCost, this.costAnalysis.getWriteOps(oldEntity, entityProto));
        }
        if (apply)
        {
            this.dirty = true;
        }
        return totalCost;
    }

    private DatastoreV3Pb.Cost calculateDeleteCost( boolean apply, Profile profile, Collection<OnestoreEntity.Reference> keys )
    {
        DatastoreV3Pb.Cost totalCost = new DatastoreV3Pb.Cost();
        for (OnestoreEntity.Reference key : keys)
        {
            String kind = Utils.getKind(key);
            Map extents = profile.getExtents();
            Extent extent = (Extent)extents.get(kind);
            if (extent != null)
            {
                OnestoreEntity.EntityProto oldEntity;
                if (apply)
                {
                    oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().remove(key);
                    LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
                    if (fullTextIndex != null) fullTextIndex.delete(key);
                }
                else
                {
                    /*
                     * AppScale - removed type declaration from oldEntity below
                     */
                    oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().get(key);
                }
                if (oldEntity != null)
                {
                    addTo(totalCost, this.costAnalysis.getWriteCost(oldEntity));
                }
            }
        }
        if (apply)
        {
            this.dirty = true;
        }
        return totalCost;
    }

    private class PersistDatastore implements Runnable
    {
        private PersistDatastore()
        {}

        public void run()
        {
            try
            {
                LocalDatastoreService.this.globalLock.writeLock().lock();
                privilegedPersist();
            }
            catch (IOException e)
            {
                LocalDatastoreService.logger.log(Level.SEVERE, "Unable to save the datastore", e);
            }
            finally
            {
                LocalDatastoreService.this.globalLock.writeLock().unlock();
            }
        }

        private void privilegedPersist() throws IOException
        {
            try
            {
                AccessController.doPrivileged(new PrivilegedExceptionAction()
                {
                    public Object run() throws IOException
                    {
                        LocalDatastoreService.PersistDatastore.this.persist();
                        return null;
                    }
                });
            }
            catch (PrivilegedActionException e)
            {
                Throwable t = e.getCause();
                if ((t instanceof IOException))
                {
                    throw ((IOException)t);
                }
                throw new RuntimeException(t);
            }
        }

        private void persist() throws IOException
        {
            if ((LocalDatastoreService.this.noStorage) || (!LocalDatastoreService.this.dirty))
            {
                return;
            }

            long start = LocalDatastoreService.this.clock.getCurrentTime();
            ObjectOutputStream objectOut = new ObjectOutputStream(new BufferedOutputStream(new FileOutputStream(LocalDatastoreService.this.backingStore)));

            objectOut.writeLong(LocalDatastoreService.this.entityId.get());
            objectOut.writeObject(LocalDatastoreService.this.profiles);

            objectOut.close();
            LocalDatastoreService.this.dirty = false;
            long end = LocalDatastoreService.this.clock.getCurrentTime();

            LocalDatastoreService.logger.log(Level.INFO, "Time to persist datastore: " + (end - start) + " ms");
        }
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
            for (LocalDatastoreService.Profile profile : LocalDatastoreService.this.profiles.values())
                /*
                 * AppScale - changed from access$2100 to profile.getTxns()
                 */
                synchronized (profile.getTxns())
                {
                    LocalDatastoreService.pruneHasCreationTimeMap(LocalDatastoreService.this.clock.getCurrentTime(), LocalDatastoreService.this.maxTransactionLifetimeMs, profile.getTxns());
                }
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

    static class EntityGroupTracker
    {
        private LocalDatastoreService.Profile.EntityGroup                       entityGroup;
        private Long                                                            entityGroupVersion;
        private final Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> written = new HashMap();
        private final Set<OnestoreEntity.Reference>                             deleted = new HashSet();

        EntityGroupTracker( LocalDatastoreService.Profile.EntityGroup entityGroup )
        {
            this.entityGroup = entityGroup;
            this.entityGroupVersion = Long.valueOf(entityGroup.getVersion());
        }

        synchronized LocalDatastoreService.Profile.EntityGroup getEntityGroup()
        {
            return this.entityGroup;
        }

        synchronized void checkEntityGroupVersion()
        {
            if (!this.entityGroupVersion.equals(Long.valueOf(this.entityGroup.getVersion()))) throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.CONCURRENT_TRANSACTION, "too much contention on these datastore entities. please try again.");
        }

        synchronized Long getEntityGroupVersion()
        {
            return this.entityGroupVersion;
        }

        synchronized void addWrittenEntity( OnestoreEntity.EntityProto entity )
        {
            OnestoreEntity.Reference key = entity.getKey();
            this.written.put(key, entity);

            this.deleted.remove(key);
        }

        synchronized void addDeletedEntity( OnestoreEntity.Reference key )
        {
            this.deleted.add(key);

            this.written.remove(key);
        }

        synchronized Collection<OnestoreEntity.EntityProto> getWrittenEntities()
        {
            return new ArrayList(this.written.values());
        }

        synchronized Collection<OnestoreEntity.Reference> getDeletedKeys()
        {
            return new ArrayList(this.deleted);
        }

        synchronized boolean isDirty()
        {
            return this.written.size() + this.deleted.size() > 0;
        }
    }

    static class LiveTxn extends LocalDatastoreService.HasCreationTime
    {
        private final Map<LocalDatastoreService.Profile.EntityGroup, LocalDatastoreService.EntityGroupTracker> entityGroups = new HashMap();

        private final List<TaskQueuePb.TaskQueueAddRequest>                                                    actions      = new ArrayList();
        private final boolean                                                                                  allowMultipleEg;
        private boolean                                                                                        failed       = false;

        LiveTxn( Clock clock, boolean allowMultipleEg )
        {
            /*
             * changed super() call below to include clocl.getCurrentTime()
             */
            super(clock.getCurrentTime());
            this.allowMultipleEg = allowMultipleEg;
        }

        synchronized LocalDatastoreService.EntityGroupTracker trackEntityGroup( LocalDatastoreService.Profile.EntityGroup newEntityGroup )
        {
            if (newEntityGroup == null)
            {
                throw new NullPointerException("EntityGroup cannot be null");
            }
            checkFailed();
            LocalDatastoreService.EntityGroupTracker tracker = (LocalDatastoreService.EntityGroupTracker)this.entityGroups.get(newEntityGroup);
            if (tracker == null)
            {
                if (this.allowMultipleEg)
                {
                    if (this.entityGroups.size() >= 5)
                    {
                        throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "operating on too many entity groups in a single transaction.");
                    }
                }
                else if (this.entityGroups.size() >= 1)
                {
                    LocalDatastoreService.Profile.EntityGroup entityGroup = (LocalDatastoreService.Profile.EntityGroup)this.entityGroups.keySet().iterator().next();
                    throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "cross-group transaction need to be explicitly specified, see TransactionOptions.Builder.withXGfound both " + entityGroup + " and " + newEntityGroup);
                }

                for (LocalDatastoreService.EntityGroupTracker other : getAllTrackers())
                {
                    try
                    {
                        other.checkEntityGroupVersion();
                    }
                    catch (ApiProxy.ApplicationException e)
                    {
                        this.failed = true;
                        throw e;
                    }
                }

                tracker = new LocalDatastoreService.EntityGroupTracker(newEntityGroup);
                this.entityGroups.put(newEntityGroup, tracker);
            }
            return tracker;
        }

        synchronized Collection<LocalDatastoreService.EntityGroupTracker> getAllTrackers()
        {
            return this.entityGroups.values();
        }

        synchronized void addActions( Collection<TaskQueuePb.TaskQueueAddRequest> newActions )
        {
            checkFailed();
            if (this.actions.size() + newActions.size() > 5L)
            {
                throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "Too many messages, maximum allowed: 5");
            }

            this.actions.addAll(newActions);
        }

        synchronized Collection<TaskQueuePb.TaskQueueAddRequest> getActions()
        {
            return new ArrayList(this.actions);
        }

        synchronized boolean isDirty()
        {
            checkFailed();
            for (LocalDatastoreService.EntityGroupTracker tracker : getAllTrackers())
            {
                if (tracker.isDirty())
                {
                    return true;
                }
            }
            return false;
        }

        synchronized void close()
        {
            for (LocalDatastoreService.EntityGroupTracker tracker : getAllTrackers())
                tracker.getEntityGroup().removeTransaction(this);
        }

        private void checkFailed()
        {
            if (this.failed) throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "transaction closed");
        }
    }
        
    class LiveQuery extends LocalDatastoreService.HasCreationTime
    {
        private final Set<String> orderProperties;
        private final Set<String> projectedProperties;
        private final Set<String> groupByProperties;
        private final DatastoreV3Pb.Query query;
        private List<OnestoreEntity.EntityProto> entities;
        private OnestoreEntity.EntityProto lastResult = null;
        private int remainingOffset = 0;

        public LiveQuery( List<EntityProto> entities, DatastoreV3Pb.Query query, EntityProtoComparator entityComparator, Clock clock )
        { 
            super(clock.getCurrentTime());
            if (entities == null) {
                throw new NullPointerException("entities cannot be null");
            }

            this.query = query;
            this.remainingOffset = query.getOffset();

            this.orderProperties = new HashSet();
            for (DatastorePb.Query.Order order : entityComparator.getAdjustedOrders()) {
                if (!"__key__".equals(order.getProperty())) {
                    this.orderProperties.add(order.getProperty());
                }
            }
            this.groupByProperties = Sets.newHashSet(query.groupByPropertyNames());
            this.projectedProperties = Sets.newHashSet(query.propertyNames());

            if (this.groupByProperties.isEmpty()) {
                this.entities = Lists.newArrayList(entities);
            } else {
                Set distinctEntities = Sets.newHashSet();
                List results = Lists.newArrayList();
                for (OnestoreEntity.EntityProto entity : entities) {
                    OnestoreEntity.EntityProto groupByResult = new OnestoreEntity.EntityProto();
                    for (OnestoreEntity.Property prop : entity.propertys()) {
                        if (this.groupByProperties.contains(prop.getName())) {
                            groupByResult.addProperty().setName(prop.getName()).setValue(prop.getValue());
                        }
                    }
                    if (distinctEntities.add(groupByResult)) {
                       results.add(entity);
                    }
                }
                this.entities = results;
            }

            DecompiledCursor startCursor = new DecompiledCursor(query.getCompiledCursor());
            this.lastResult = startCursor.getCursorEntity();
            int endCursorPos = new DecompiledCursor(query.getEndCompiledCursor()).getPosition(entityComparator, this.entities.size());

            int startCursorPos = Math.min(endCursorPos, startCursor.getPosition(entityComparator, 0));

            if (endCursorPos < this.entities.size()) {
                this.entities.subList(endCursorPos, this.entities.size()).clear();
            }
            this.entities.subList(0, startCursorPos).clear();

            if (query.hasLimit()) {
                int toIndex = query.getLimit() + query.getOffset();
                if (toIndex < this.entities.size())
                    this.entities.subList(toIndex, this.entities.size()).clear();
            }
        }

    private int offsetResults(int offset)
    {
      int realOffset = Math.min(Math.min(offset, this.entities.size()), 300);
      if (realOffset > 0) {
        this.lastResult = ((OnestoreEntity.EntityProto)this.entities.get(realOffset - 1));
        this.entities.subList(0, realOffset).clear();
        this.remainingOffset -= realOffset;
      }
      return realOffset;
    }

    public DatastoreV3Pb.QueryResult nextResult(Integer offset, Integer count, boolean compile) {
      DatastoreV3Pb.QueryResult result = new DatastoreV3Pb.QueryResult();
      if (count == null) {
        if (this.query.hasCount())
          count = Integer.valueOf(this.query.getCount());
        else {
          count = Integer.valueOf(20);
        }
      }
      if (this.query.isPersistOffset()) {
        if ((offset != null) && (offset.intValue() != this.remainingOffset)) {
          throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "offset mismatch");
        }
        offset = Integer.valueOf(this.remainingOffset);
      } else if (offset == null) {
        offset = Integer.valueOf(0);
      }
      if (offset.intValue() == result.getSkippedResults())
      {
        result.mutableResults().addAll(removeEntities(Math.min(300, count.intValue())));
      }
      result.setMoreResults(this.entities.size() > 0);
      result.setKeysOnly(this.query.isKeysOnly());
      if (compile) {
        result.getMutableCompiledCursor().addPosition(compilePosition());
      }
      return result;
    }

    private List<OnestoreEntity.EntityProto> removeEntities(int count)
    {
      List subList = this.entities.subList(0, Math.min(count, this.entities.size()));

      if (subList.size() > 0)
      {
        this.lastResult = ((OnestoreEntity.EntityProto)subList.get(subList.size() - 1));
      }

      List results = new ArrayList(subList.size());
      for (OnestoreEntity.EntityProto entity : (List<OnestoreEntity.EntityProto>)subList)
      {
        OnestoreEntity.EntityProto result;
        Set seenProps;
        if (!this.projectedProperties.isEmpty()) {
          result = new OnestoreEntity.EntityProto();
          result.getMutableKey().copyFrom(entity.getKey());
          result.getMutableEntityGroup();
          seenProps = Sets.newHashSetWithExpectedSize(this.query.propertyNameSize());
          for (OnestoreEntity.Property prop : entity.propertys()) {
            if (this.projectedProperties.contains(prop.getName()))
            {
              if (!seenProps.add(prop.getName())) {
                throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.INTERNAL_ERROR, "LocalDatstoreServer produced invalude results.");
              }

              result.addProperty().setName(prop.getName()).setMeaning(OnestoreEntity.Property.Meaning.INDEX_VALUE).setMultiple(false).getMutableValue().copyFrom(prop.getValue());
            }

          }

        }
        else if (this.query.isKeysOnly()) {
          result = new OnestoreEntity.EntityProto();
          result.getMutableKey().copyFrom(entity.getKey());
          result.getMutableEntityGroup();
        } else {
          result = (OnestoreEntity.EntityProto)entity.clone();
        }
        LocalDatastoreService.this.processEntityForSpecialProperties(result, false);
        results.add(result);
      }
      subList.clear();
      return results;
    }

    private OnestoreEntity.EntityProto decompilePosition(DatastoreV3Pb.CompiledCursor.Position position) {
      OnestoreEntity.EntityProto result = new OnestoreEntity.EntityProto();
      if (position.hasKey()) {
        if ((this.query.hasKind()) && (!this.query.getKind().equals(((OnestoreEntity.Path.Element)Iterables.getLast(position.getKey().getPath().elements())).getType())))
        {
          throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
        }
        result.setKey(position.getKey());
      }

      Set cursorProperties = this.groupByProperties.isEmpty() ? this.orderProperties : this.groupByProperties;

      Set remainingProperties = new HashSet(cursorProperties);
      for (DatastoreV3Pb.CompiledCursor.PositionIndexValue prop : position.indexValues()) {
        if (!cursorProperties.contains(prop.getProperty()))
        {
          throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
        }
        remainingProperties.remove(prop.getProperty());
        result.addProperty().setName(prop.getProperty()).setValue(prop.getValue());
      }

      if (!remainingProperties.isEmpty()) {
        throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
      }
      return result;
    }

    private DatastoreV3Pb.CompiledCursor.Position compilePosition()
    {
      DatastoreV3Pb.CompiledCursor.Position position = new DatastoreV3Pb.CompiledCursor.Position();

      if (this.lastResult != null)
      {
        Set cursorProperties;
        if (this.groupByProperties.isEmpty()) {
          cursorProperties = Sets.newHashSet(this.orderProperties);

          cursorProperties.add("__key__");
          position.setKey(this.lastResult.getKey());
        } else {
          cursorProperties = this.groupByProperties;
        }

        for (OnestoreEntity.Property prop : this.lastResult.propertys()) {
          if (cursorProperties.contains(prop.getName())) {
            position.addIndexValue().setProperty(prop.getName()).setValue(prop.getValue());
          }
        }

        position.setStartInclusive(false);
      }

      return position;
    }

    public DatastoreV3Pb.CompiledQuery compileQuery() {
      DatastoreV3Pb.CompiledQuery result = new DatastoreV3Pb.CompiledQuery();
      DatastoreV3Pb.CompiledQuery.PrimaryScan scan = result.getMutablePrimaryScan();

      scan.setIndexNameAsBytes(this.query.toByteArray());

      return result;
    }

        class DecompiledCursor
        {
            final OnestoreEntity.EntityProto cursorEntity;
            final boolean                    inclusive;

            public DecompiledCursor( DatastoreV3Pb.CompiledCursor compiledCursor )
            {
                if ((compiledCursor == null) || (compiledCursor.positionSize() == 0))
                {
                    this.cursorEntity = null;
                    this.inclusive = false;
                    return;
                }

                DatastoreV3Pb.CompiledCursor.Position position = compiledCursor.getPosition(0);
                if ((!position.hasStartKey()) && (!position.hasKey()) && (position.indexValueSize() <= 0))
                {
                    this.cursorEntity = null;
                    this.inclusive = false;
                    return;
                }

                this.cursorEntity = LocalDatastoreService.LiveQuery.this.decompilePosition(position);
                this.inclusive = position.isStartInclusive();
            }

            public int getPosition( EntityProtoComparators.EntityProtoComparator entityComparator, int defaultValue )
            {
                if (this.cursorEntity == null)
                {
                    return defaultValue;
                }

                int loc = Collections.binarySearch(LocalDatastoreService.LiveQuery.this.entities, this.cursorEntity, entityComparator);
                if (loc < 0)
                {
                    return -(loc + 1);
                }
                return this.inclusive ? loc : loc + 1;
            }

            public OnestoreEntity.EntityProto getCursorEntity()
            {
                return this.cursorEntity;
            }
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

    static class Extent implements Serializable
    {
        private Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> entities = new LinkedHashMap();

        public Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> getEntities()
        {
            return this.entities;
        }
    }

    static class Profile implements Serializable
    {
        private final Map<String, LocalDatastoreService.Extent>      extents = Collections.synchronizedMap(new HashMap());
        private transient Map<OnestoreEntity.Path, EntityGroup>      groups;
        private transient Set<OnestoreEntity.Path>                   groupsWithUnappliedJobs;
        private transient Map<Long, LocalDatastoreService.LiveQuery> queries;
        private transient Map<Long, LocalDatastoreService.LiveTxn>   txns;
        private final LocalFullTextIndex                             fullTextIndex;

        public synchronized List<OnestoreEntity.EntityProto> getAllEntities()
        {
            List entities = new ArrayList();
            for (LocalDatastoreService.Extent extent : this.extents.values())
            {
                entities.addAll(extent.getEntities().values());
            }
            return entities;
        }

        public Profile()
        {
            this.fullTextIndex = createFullTextIndex();
        }

        private LocalFullTextIndex createFullTextIndex()
        {
            Class indexClass = getFullTextIndexClass();

            if (indexClass == null)
            {
                return null;
            }
            try
            {
                return (LocalFullTextIndex)indexClass.newInstance();
            }
            catch (InstantiationException e)
            {
                throw new RuntimeException(e);
            }
            catch (IllegalAccessException e)
            {
                throw new RuntimeException(e);
            }
        }

        private Class<LocalFullTextIndex> getFullTextIndexClass()
        {
            try
            {
                /*
                 * AppScale - added cast below
                 */
                return (Class<LocalFullTextIndex>)Class.forName("com.google.appengine.api.datastore.dev.LuceneFullTextIndex");
            }
            catch (ClassNotFoundException e)
            {
                return null;
            }
            catch (NoClassDefFoundError e)
            {
            }
            return null;
        }

        public Map<String, LocalDatastoreService.Extent> getExtents()
        {
            return this.extents;
        }

        public synchronized EntityGroup getGroup( OnestoreEntity.Path path )
        {
            Map map = getGroups();
            EntityGroup group = (EntityGroup)map.get(path);
            if (group == null)
            {
                group = new EntityGroup(path);
                map.put(path, group);
            }
            return group;
        }

        private synchronized void groom()
        {
            for (OnestoreEntity.Path path : new HashSet<OnestoreEntity.Path>(getGroupsWithUnappliedJobs()))
            {
                EntityGroup eg = getGroup(path);
                eg.maybeRollForwardUnappliedJobs();
            }
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

        public synchronized LocalDatastoreService.LiveTxn getTxn( long handle )
        {
            return (LocalDatastoreService.LiveTxn)LocalDatastoreService.safeGetFromExpiringMap(getTxns(), handle, "transaction has expired or is invalid");
        }

        public LocalFullTextIndex getFullTextIndex()
        {
            return this.fullTextIndex;
        }

        public synchronized void addTxn( long handle, LocalDatastoreService.LiveTxn txn )
        {
            getTxns().put(Long.valueOf(handle), txn);
        }

        private synchronized LocalDatastoreService.LiveTxn removeTxn( long handle )
        {
            LocalDatastoreService.LiveTxn txn = getTxn(handle);
            txn.close();
            this.txns.remove(Long.valueOf(handle));
            return txn;
        }

        private synchronized Map<Long, LocalDatastoreService.LiveTxn> getTxns()
        {
            if (this.txns == null)
            {
                this.txns = new HashMap();
            }
            return this.txns;
        }

        private synchronized Map<OnestoreEntity.Path, EntityGroup> getGroups()
        {
            if (this.groups == null)
            {
                this.groups = new LinkedHashMap();
            }
            return this.groups;
        }

        private synchronized Set<OnestoreEntity.Path> getGroupsWithUnappliedJobs()
        {
            if (this.groupsWithUnappliedJobs == null)
            {
                this.groupsWithUnappliedJobs = new LinkedHashSet();
            }
            return this.groupsWithUnappliedJobs;
        }

        class EntityGroup
        {
            private final OnestoreEntity.Path                                                       path;
            private final AtomicLong                                                                version       = new AtomicLong();
            private final WeakHashMap<LocalDatastoreService.LiveTxn, LocalDatastoreService.Profile> snapshots     = new WeakHashMap();

            private final LinkedList<LocalDatastoreJob>                                             unappliedJobs = new LinkedList();

            private EntityGroup( OnestoreEntity.Path path )
            {
                this.path = path;
            }

            public long getVersion()
            {
                return this.version.get();
            }

            public void incrementVersion()
            {
                long oldVersion = this.version.getAndIncrement();
                LocalDatastoreService.Profile snapshot = null;
                for (LocalDatastoreService.LiveTxn txn : this.snapshots.keySet())
                    if (txn.trackEntityGroup(this).getEntityGroupVersion().longValue() == oldVersion)
                    {
                        if (snapshot == null)
                        {
                            snapshot = takeSnapshot();
                        }
                        this.snapshots.put(txn, snapshot);
                    }
            }

            public OnestoreEntity.EntityProto get( LocalDatastoreService.LiveTxn liveTxn, OnestoreEntity.Reference key, boolean eventualConsistency )
            {
                if (!eventualConsistency)
                {
                    rollForwardUnappliedJobs();
                }
                LocalDatastoreService.Profile profile = getSnapshot(liveTxn);
                Map extents = profile.getExtents();
                LocalDatastoreService.Extent extent = (LocalDatastoreService.Extent)extents.get(Utils.getKind(key));
                if (extent != null)
                {
                    Map entities = extent.getEntities();
                    return (OnestoreEntity.EntityProto)entities.get(key);
                }
                return null;
            }

            public LocalDatastoreService.EntityGroupTracker addTransaction( LocalDatastoreService.LiveTxn txn )
            {
                LocalDatastoreService.EntityGroupTracker tracker = txn.trackEntityGroup(this);
                if (!this.snapshots.containsKey(txn))
                {
                    this.snapshots.put(txn, null);
                }
                return tracker;
            }

            public void removeTransaction( LocalDatastoreService.LiveTxn txn )
            {
                this.snapshots.remove(txn);
            }

            private LocalDatastoreService.Profile getSnapshot( LocalDatastoreService.LiveTxn txn )
            {
                if (txn == null)
                {
                    return LocalDatastoreService.Profile.this;
                }
                LocalDatastoreService.Profile snapshot = (LocalDatastoreService.Profile)this.snapshots.get(txn);
                if (snapshot == null)
                {
                    return LocalDatastoreService.Profile.this;
                }
                return snapshot;
            }

            private LocalDatastoreService.Profile takeSnapshot()
            {
                try
                {
                    ByteArrayOutputStream bos = new ByteArrayOutputStream();
                    ObjectOutputStream oos = new ObjectOutputStream(bos);
                    oos.writeObject(LocalDatastoreService.Profile.this);
                    oos.close();
                    ByteArrayInputStream bis = new ByteArrayInputStream(bos.toByteArray());
                    ObjectInputStream ois = new ObjectInputStream(bis);
                    return (LocalDatastoreService.Profile)ois.readObject();
                }
                catch (IOException ex)
                {
                    throw new RuntimeException("Unable to take transaction snapshot.", ex);
                }
                catch (ClassNotFoundException ex)
                {
                    throw new RuntimeException("Unable to take transaction snapshot.", ex);
                }
            }

            public String toString()
            {
                return this.path.toString();
            }

            public DatastoreV3Pb.Cost addJob( LocalDatastoreJob job )
            {
                this.unappliedJobs.addLast(job);
                LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().add(this.path);
                return maybeRollForwardUnappliedJobs();
            }

            public void rollForwardUnappliedJobs()
            {
                if (!this.unappliedJobs.isEmpty())
                {
                    for (LocalDatastoreJob applyJob : this.unappliedJobs)
                    {
                        applyJob.apply();
                    }
                    this.unappliedJobs.clear();
                    LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().remove(this.path);
                    LocalDatastoreService.logger.fine("Rolled forward unapplied jobs for " + this.path);
                }
            }

            public DatastoreV3Pb.Cost maybeRollForwardUnappliedJobs()
            {
                int jobsAtStart = this.unappliedJobs.size();
                LocalDatastoreService.logger.fine(String.format("Maybe rolling forward %d unapplied jobs for %s.", new Object[] { Integer.valueOf(jobsAtStart), this.path }));

                int applied = 0;
                DatastoreV3Pb.Cost totalCost = new DatastoreV3Pb.Cost();
                for (Iterator iter = this.unappliedJobs.iterator(); iter.hasNext();)
                {
                    LocalDatastoreJob.TryApplyResult result = ((LocalDatastoreJob)iter.next()).tryApply();
                    LocalDatastoreService.addTo(totalCost, result.cost);
                    if (!result.applied) break;
                    iter.remove();
                    applied++;
                }

                if (this.unappliedJobs.isEmpty())
                {
                    LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().remove(this.path);
                }
                LocalDatastoreService.logger.fine(String.format("Rolled forward %d of %d jobs for %s", new Object[] { Integer.valueOf(applied), Integer.valueOf(jobsAtStart), this.path }));

                return totalCost;
            }

            public Key pathAsKey()
            {
                OnestoreEntity.Reference entityGroupRef = new OnestoreEntity.Reference();
                entityGroupRef.setPath(this.path);
                return LocalCompositeIndexManager.KeyTranslator.createFromPb(entityGroupRef);
            }
        }
    }
    
    private String getAppId()
    {
        String appId = System.getProperty(APPLICATION_ID_PROPERTY);
        return appId;
    }
    
    public static enum AutoIdAllocationPolicy
    {
        SEQUENTIAL, 
        SCATTERED;
    }
}
