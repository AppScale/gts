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
            throw new IllegalStateException(String.format("Invalid value \"%s\" for property \"%s\"", new Object[] { 
              autoIdAllocationPolicyString, "datastore.auto_id_allocation_policy" }), e);
          }

        }

        LocalCompositeIndexManager.getInstance().setAppDir(context.getLocalServerEnvironment().getAppDir());

        LocalCompositeIndexManager.getInstance().setClock(this.clock);

        LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(false);
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

        setupIndexes(properties.get("user.dir"), properties.get("APP_NAME"));
        
        logger.info(String.format("Local Datastore initialized: \n\tType: %s\n\tStorage: %s", 
          new Object[] { isHighRep() ? "High Replication" : "Master/Slave", 
          this.noStorage ? "In-memory" : this.backingStore }));
    }

    private void setupIndexes(String appDir, String appName)
    {
        IndexesXmlReader xmlReader = new IndexesXmlReader(appDir);
        indexes = xmlReader.readIndexesXml();
        DatastoreV3Pb.CompositeIndices requestedCompositeIndices = new DatastoreV3Pb.CompositeIndices();
        for (IndexesXml.Index index : indexes)
        {
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
        
      ApiBasePb.StringProto appId = new ApiBasePb.StringProto();
      appId.setValue(appName); 
      DatastoreV3Pb.CompositeIndices existing = getIndices( null, appId);  
      
      createAndDeleteIndexes(existing, requestedCompositeIndices);
    }

    private void createAndDeleteIndexes( DatastoreV3Pb.CompositeIndices existing, DatastoreV3Pb.CompositeIndices requested)
    {
        HashMap existingMap = new HashMap<String, OnestoreEntity.CompositeIndex>();
        HashMap requestedMap = new HashMap<String, OnestoreEntity.CompositeIndex>();
        // Convert CompositeIndices into hash maps to get the diff of existing and requested indices. 
        for (int ctr = 0; ctr < existing.indexSize(); ctr++)
        {
            OnestoreEntity.CompositeIndex compIndex = existing.getIndex(ctr);
            existingMap.put(compIndex.getDefinition().toFlatString(), compIndex);
        }
        for (int ctr = 0; ctr < requested.indexSize(); ctr++)
        {
            OnestoreEntity.CompositeIndex compIndex = requested.getIndex(ctr);
            requestedMap.put(compIndex.getDefinition().toFlatString(), compIndex);
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
            }
        }

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
            }
        }
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

    private OnestoreEntity.CompositeIndex findIndexToUse( DatastoreV3Pb.Query query)
    {
        if (!query.hasKind())
        {
            return null;
        }
        List<OnestoreEntity.Index> indexList = LocalCompositeIndexManager.getInstance().queryIndexList(query);
        if (indexList.isEmpty())
        {
            return null;
        }
        List<OnestoreEntity.CompositeIndex> compIndexes = compositeIndexCache.get(query.getKind());
        return fetchMatchingIndex(compIndexes, indexList.get(0));
    }

    public DatastoreV3Pb.QueryResult runQuery( LocalRpcService.Status status, DatastoreV3Pb.Query query )
    {
        final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new LocalCompositeIndexManager.ValidatedQuery(query);

        query = validatedQuery.getV3Query();
        OnestoreEntity.CompositeIndex compositeIndex = findIndexToUse(query);
        if (compositeIndex != null)
        {
            query.addCompositeIndex(compositeIndex);
        }
        String app = query.getApp();
        Profile profile = getOrCreateProfile(app);

        synchronized (profile)
        {
            if ((query.hasTransaction()) || (query.hasAncestor()))
            {
                if (query.hasTransaction())
                {
                    if (!app.equals(query.getTransaction().getApp()))
                    {
                        throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.INTERNAL_ERROR, "Can't query app " + app + "in a transaction on app " + query.getTransaction().getApp());
                    }

                    LiveTxn liveTxn = profile.getTxn(query.getTransaction().getHandle());

                }

            }

            /*
             * AppScale line replacement to #end
             */
            DatastoreV3Pb.QueryResult queryResult = new DatastoreV3Pb.QueryResult();
            proxy.doPost(app, "RunQuery", query, queryResult);
            //List<EntityProto> queryEntities = new ArrayList<EntityProto>(queryResult.results());
            /* #end */

            //if (queryEntities == null)
            //{
            //    queryEntities = Collections.emptyList();
           // }

            //final boolean hasNamespace = query.hasNameSpace();
            //final String namespace = query.getNameSpace();

            /*
             * AppScale - removed duplicate count instantiations
             */
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

            //DatastoreV3Pb.QueryResult result = liveQuery.nextResult(query.hasOffset() ? Integer.valueOf(query.getOffset()) : null, count, query.isCompile());
            if (query.isCompile())
            {
                queryResult.setCompiledQuery(liveQuery.compileQuery());
            }
            if (queryResult.isMoreResults())
            {
                long cursor = this.queryId.getAndIncrement();
                profile.addQuery(cursor, liveQuery);
                queryResult.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
            }

            //for (OnestoreEntity.Index index : LocalCompositeIndexManager.getInstance().queryIndexList(query))
            //{
            //    result.addIndex(wrapIndexInCompositeIndex(app, index));
            //} 
            /*
             * AppScale - adding skipped results to the result, otherwise query counts are wrong	
             */	
            //result.setSkippedResults(queryResult.getSkippedResults());
            return queryResult;
        }
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
        if (!compiledCursor.isInitialized() || liveQuery.getCount() >= liveQuery.getOffset())
        {
          queryResult.setMoreResults(false);
          if (query.isCompile())
          {
            queryResult.setCompiledQuery(liveQuery.compileQuery());
          }
          if (compiledCursor.isInitialized())
          {
            queryResult.setCompiledCursor(compiledCursor); 
          } 
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

        if (queryResult.isMoreResults())
        {
            queryResult.setCursor(request.getCursor());
        }
        else
        {
            profile.removeQuery(request.getCursor().getCursor());
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

    static class LiveTxn extends LocalDatastoreService.HasCreationTime
    {
        private final List<TaskQueuePb.TaskQueueAddRequest>                                                    actions      = new ArrayList();
        private boolean                                                                                        failed       = false;

        LiveTxn( Clock clock)
        {
            /*
             * changed super() call below to include clocl.getCurrentTime()
             */
            super(clock.getCurrentTime());
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

        synchronized void close()
        {
        }

        private void checkFailed()
        {
            if (this.failed) throw Utils.newError(DatastoreV3Pb.Error.ErrorCode.BAD_REQUEST, "transaction closed");
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

            // This is the number of entities this queries has seen so far.
            this.offset = offset;

            this.lastCursor.copyFrom(cursor);
            if (query.hasCount()) {
              this.totalCount = Integer.valueOf(this.query.getCount());
            }
            else if (query.hasLimit()) {
              this.totalCount = Integer.valueOf(this.query.getLimit());
            }
            else{
              this.totalCount = DEFAULT_BATCH_SIZE;
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

        public int getOffset(){
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
        private transient Map<Long, LocalDatastoreService.LiveTxn>   txns;

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

        public synchronized LocalDatastoreService.LiveTxn getTxn( long handle )
        {
            return (LocalDatastoreService.LiveTxn)LocalDatastoreService.safeGetFromExpiringMap(getTxns(), handle, "transaction has expired or is invalid");
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
    }
}
