package com.google.appengine.api.datastore.dev;

import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityProtoComparators;
import com.google.appengine.api.datastore.EntityProtoComparators.EntityProtoComparator;
import com.google.appengine.api.datastore.EntityTranslator;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddRequest;
import com.google.appengine.api.taskqueue.Transaction;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.base.Predicate;
import com.google.appengine.repackaged.com.google.common.base.Predicates;
import com.google.appengine.repackaged.com.google.common.collect.HashMultimap;
import com.google.appengine.repackaged.com.google.common.collect.Iterables;
import com.google.appengine.repackaged.com.google.common.collect.Iterators;
import com.google.appengine.repackaged.com.google.common.collect.Lists;
import com.google.appengine.repackaged.com.google.common.collect.Multimap;
import com.google.appengine.repackaged.com.google.common.collect.Sets;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LatencyPercentiles;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServerEnvironment;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiBasePb.Integer64Proto;
import com.google.apphosting.api.ApiBasePb.StringProto;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.utils.config.GenerationDirectory;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.CompositeIndex;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;
import com.google.storage.onestore.v3.OnestoreEntity.Index;
import com.google.storage.onestore.v3.OnestoreEntity.Path;
import com.google.storage.onestore.v3.OnestoreEntity.Property;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue;
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

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService extends AbstractLocalRpcService
{
  private static final Logger logger = Logger.getLogger(LocalDatastoreService.class.getName());
  static final int DEFAULT_BATCH_SIZE = 20;
  static final int MAXIMUM_RESULTS_SIZE = 300;
  public static final String PACKAGE = "datastore_v3";
  public static final String MAX_QUERY_LIFETIME_PROPERTY = "datastore.max_query_lifetime";
  private static final int DEFAULT_MAX_QUERY_LIFETIME = 30000;
  public static final String MAX_TRANSACTION_LIFETIME_PROPERTY = "datastore.max_txn_lifetime";
  private static final int DEFAULT_MAX_TRANSACTION_LIFETIME = 300000;
  public static final String STORE_DELAY_PROPERTY = "datastore.store_delay";
  static final int DEFAULT_STORE_DELAY_MS = 30000;
  public static final int MAX_EG_PER_TXN = 5;
  public static final String BACKING_STORE_PROPERTY = "datastore.backing_store";
  public static final String NO_INDEX_AUTO_GEN_PROP = "datastore.no_index_auto_gen";
  public static final String NO_STORAGE_PROPERTY = "datastore.no_storage";
  public static final String HIGH_REP_JOB_POLICY_CLASS_PROPERTY = "datastore.high_replication_job_policy_class";
  private static final Pattern RESERVED_NAME = Pattern.compile("^__.*__$");

  private static final Set<String> RESERVED_NAME_WHITELIST = new HashSet(Arrays.asList(new String[] { "__BlobUploadSession__", "__BlobInfo__", "__ProspectiveSearchSubscriptions__", "__BlobFileIndex__", "__GsFileInfo__" }));
  static final String ENTITY_GROUP_MESSAGE = "can't operate on multiple entity groups in a single transaction.";
  static final String TOO_MANY_ENTITY_GROUP_MESSAGE = "operating on too many entity groups in a single transaction.";
  static final String MULTI_EG_TXN_NOT_ALLOWED = "transactions on multiple entity groups only allowed in High Replication applications";
  static final String CONTENTION_MESSAGE = "too much contention on these datastore entities. please try again.";
  static final String TRANSACTION_CLOSED = "transaction closed";
  static final String TRANSACTION_NOT_FOUND = "transaction has expired or is invalid";
  static final String QUERY_NOT_FOUND = "query has expired or is invalid. Please restart it with the last cursor to read more results.";
  private final AtomicLong entityId = new AtomicLong(1L);

  private final AtomicLong queryId = new AtomicLong(0L);
  private String backingStore;
  private Map<String, Profile> profiles = Collections.synchronizedMap(new HashMap());
  private Clock clock;
  private static final long MAX_BATCH_GET_KEYS = 1000000000L;
  private static final long MAX_ACTIONS_PER_TXN = 5L;
  private int maxQueryLifetimeMs;
  private int maxTransactionLifetimeMs;
  private final ScheduledThreadPoolExecutor scheduler = new ScheduledThreadPoolExecutor(2, new ThreadFactory()
  {
    public Thread newThread(Runnable r)
    {
      Thread thread = new Thread(r);

      thread.setDaemon(true);
      return thread;
    }
  });

  private final RemoveStaleQueries removeStaleQueriesTask = new RemoveStaleQueries();

  private final RemoveStaleTransactions removeStaleTransactionsTask = new RemoveStaleTransactions();

  private final PersistDatastore persistDatastoreTask = new PersistDatastore();

  private final AtomicInteger transactionHandleProvider = new AtomicInteger(0);
  private int storeDelayMs;
  private volatile boolean dirty;
  private final ReadWriteLock globalLock = new ReentrantReadWriteLock();
  private boolean noStorage;
  private Thread shutdownHook;
  private PseudoKinds pseudoKinds;
  private HighRepJobPolicy highRepJobPolicy;
  private boolean isHighRep;
  private LocalDatastoreCostAnalysis costAnalysis;
  private static Map<String, SpecialProperty> specialPropertyMap = Collections.singletonMap("__scatter__", SpecialProperty.SCATTER);

  private HTTPClientDatastoreProxy proxy;

  public void clearProfiles()
  {
    for (Profile profile : this.profiles.values()) {
      LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
      if (fullTextIndex != null) {
        fullTextIndex.close();
      }
    }
    this.profiles.clear();
  }

  public void clearQueryHistory()
  {
    LocalCompositeIndexManager.getInstance().clearQueryHistory();
  }

  public LocalDatastoreService()
  {
    setMaxQueryLifetime(30000);
    setMaxTransactionLifetime(300000);
    setStoreDelay(30000);
  }

  public void init(LocalServiceContext context, Map<String, String> properties)
  {
    this.clock = context.getClock();

    ResourceLoader res = ResourceLoader.getResourceLoader();
    String host = res.getPbServerIp();
    int port = res.getPbServerPort();
    boolean isSSL = res.getDatastoreSecurityMode();
    this.proxy = new HTTPClientDatastoreProxy(host, port, isSSL);

    String storeDelayTime = (String)properties.get("datastore.store_delay");
    this.storeDelayMs = parseInt(storeDelayTime, this.storeDelayMs, "datastore.store_delay");

    String maxQueryLifetime = (String)properties.get("datastore.max_query_lifetime");
    this.maxQueryLifetimeMs = parseInt(maxQueryLifetime, this.maxQueryLifetimeMs, "datastore.max_query_lifetime");

    String maxTxnLifetime = (String)properties.get("datastore.max_txn_lifetime");
    this.maxTransactionLifetimeMs = parseInt(maxTxnLifetime, this.maxTransactionLifetimeMs, "datastore.max_txn_lifetime");

    LocalCompositeIndexManager.getInstance().setAppDir(context.getLocalServerEnvironment().getAppDir());

    LocalCompositeIndexManager.getInstance().setClock(this.clock);

    String noIndexAutoGenProp = (String)properties.get("datastore.no_index_auto_gen");
    if (noIndexAutoGenProp != null) {
      LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(Boolean.valueOf(noIndexAutoGenProp).booleanValue());
    }

    initHighRepJobPolicy(properties);

    this.pseudoKinds = new PseudoKinds();
    this.pseudoKinds.register(new KindPseudoKind(this));
    this.pseudoKinds.register(new PropertyPseudoKind(this));
    this.pseudoKinds.register(new NamespacePseudoKind(this));
    if (isHighRep()) {
      this.pseudoKinds.register(new EntityGroupPseudoKind());
    }

    this.costAnalysis = new LocalDatastoreCostAnalysis(LocalCompositeIndexManager.getInstance());

    logger.info(String.format("Local Datastore initialized: \n\tType: %s\n\tStorage: %s", new Object[] { isHighRep() ? "High Replication" : "Master/Slave", this.noStorage ? "In-memory" : this.backingStore }));
  }

  boolean isHighRep()
  {
    return this.isHighRep;
  }

  private void initHighRepJobPolicy(Map<String, String> properties) {
    String highRepJobPolicyStr = (String)properties.get("datastore.high_replication_job_policy_class");
    if (highRepJobPolicyStr == null) {
      DefaultHighRepJobPolicy defaultPolicy = new DefaultHighRepJobPolicy(properties);

      this.isHighRep = (defaultPolicy.unappliedJobCutoff > 0);
      this.highRepJobPolicy = defaultPolicy;
    }
    else
    {
      this.isHighRep = true;
      try {
        Class highRepJobPolicyCls = Class.forName(highRepJobPolicyStr);
        Constructor ctor = highRepJobPolicyCls.getDeclaredConstructor(new Class[0]);

        ctor.setAccessible(true);

        this.highRepJobPolicy = ((HighRepJobPolicy)ctor.newInstance(new Object[0]));
      } catch (ClassNotFoundException e) {
        throw new IllegalArgumentException(e);
      } catch (InvocationTargetException e) {
        throw new IllegalArgumentException(e);
      } catch (NoSuchMethodException e) {
        throw new IllegalArgumentException(e);
      } catch (InstantiationException e) {
        throw new IllegalArgumentException(e);
      } catch (IllegalAccessException e) {
        throw new IllegalArgumentException(e);
      }
    }
  }

  private static int parseInt(String valStr, int defaultVal, String propName) {
    if (valStr != null) {
      try {
        return Integer.parseInt(valStr);
      } catch (NumberFormatException e) {
        logger.log(Level.WARNING, "Expected a numeric value for property " + propName + "but received, " + valStr + ". Resetting property to the default.");
      }
    }

    return defaultVal;
  }

  public void start()
  {
    AccessController.doPrivileged(new PrivilegedAction()
    {
      public Object run() {
        LocalDatastoreService.this.startInternal();
        return null;
      } } );
  }

  private void startInternal() {
    //load();
    this.scheduler.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
    this.scheduler.scheduleWithFixedDelay(this.removeStaleQueriesTask, this.maxQueryLifetimeMs * 5, this.maxQueryLifetimeMs * 5, TimeUnit.MILLISECONDS);

    this.scheduler.scheduleWithFixedDelay(this.removeStaleTransactionsTask, this.maxTransactionLifetimeMs * 5, this.maxTransactionLifetimeMs * 5, TimeUnit.MILLISECONDS);

    if (!this.noStorage) {
      this.scheduler.scheduleWithFixedDelay(this.persistDatastoreTask, this.storeDelayMs, this.storeDelayMs, TimeUnit.MILLISECONDS);
    }

    this.shutdownHook = new Thread()
    {
      public void run() {
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
      if (profile.getGroups() != null)
        for (LocalDatastoreService.Profile.EntityGroup eg : profile.getGroups().values())
          eg.rollForwardUnappliedJobs();
  }

  public void setMaxQueryLifetime(int milliseconds)
  {
    this.maxQueryLifetimeMs = milliseconds;
  }

  public void setMaxTransactionLifetime(int milliseconds) {
    this.maxTransactionLifetimeMs = milliseconds;
  }

  public void setBackingStore(String backingStore)
  {
    this.backingStore = backingStore;
  }

  public void setStoreDelay(int delayMs) {
    this.storeDelayMs = delayMs;
  }

  public void setNoStorage(boolean noStorage) {
    this.noStorage = noStorage;
  }

  public String getPackage()
  {
    return "datastore_v3";
  }
  @LatencyPercentiles(latency50th=10)
  public DatastorePb.GetResponse get(LocalRpcService.Status status, DatastorePb.GetRequest request) {
    DatastorePb.GetResponse response = new DatastorePb.GetResponse();
    /*
    LiveTxn liveTxn = null;
    for (OnestoreEntity.Reference key : request.keys()) {
      String app = key.getApp();
      OnestoreEntity.Path groupPath = getGroup(key);
      DatastorePb.GetResponse.Entity responseEntity = response.addEntity();
      Profile profile = getOrCreateProfile(app);
      synchronized (profile) {
        LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup(groupPath);
        if (request.hasTransaction()) {
          if (liveTxn == null) {
            liveTxn = profile.getTxn(request.getTransaction().getHandle());
          }

          eg.addTransaction(liveTxn);
        }
        boolean eventualConsistency = (request.hasFailoverMs()) && (liveTxn == null);
        OnestoreEntity.EntityProto entity = this.pseudoKinds.get(liveTxn, eg, key, eventualConsistency);
        if (entity == PseudoKinds.NOT_A_PSEUDO_KIND) {
          entity = eg.get(liveTxn, key, eventualConsistency);
        }
        if (entity != null) {
          responseEntity.getMutableEntity().copyFrom(entity);
          processEntityForSpecialProperties(responseEntity.getMutableEntity(), false);
        }

        profile.groom();
      }
    } */

    proxy.doPost(request.getKey(0).getApp(), "Get", request, response);
    return response;
  }
  @LatencyPercentiles(latency50th=30, dynamicAdjuster=WriteLatencyAdjuster.class)
  public DatastorePb.PutResponse put(LocalRpcService.Status status, DatastorePb.PutRequest request) {
    try {
      this.globalLock.readLock().lock();
      DatastorePb.PutResponse localPutResponse = putImpl(status, request);
      return localPutResponse; } finally { this.globalLock.readLock().unlock(); }
  }

  private static void processEntityForSpecialProperties(OnestoreEntity.EntityProto entity, boolean store)
  {
    for (Iterator iter = entity.propertyIterator(); iter.hasNext(); ) {
      if (getSpecialPropertyMap().containsKey(((OnestoreEntity.Property)iter.next()).getName())) {
        iter.remove();
      }
    }

    for (SpecialProperty specialProp : getSpecialPropertyMap().values())
      if (store ? specialProp.isStored() : specialProp.isVisible()) {
        OnestoreEntity.PropertyValue value = specialProp.getValue(entity);
        if (value != null)
          entity.addProperty(specialProp.getProperty(value));
      }
  }

  public DatastorePb.PutResponse putImpl(LocalRpcService.Status status, DatastorePb.PutRequest request)
  {
    DatastorePb.PutResponse response = new DatastorePb.PutResponse();
    if (request.entitySize() == 0) {
      return response;
    }
    DatastorePb.Cost totalCost = response.getMutableCost();
    String app = ((OnestoreEntity.EntityProto)request.entitys().get(0)).getKey().getApp();
    List clones = new ArrayList();
    for (OnestoreEntity.EntityProto entity : request.entitys()) {
      validateAndProcessEntityProto(entity);
      OnestoreEntity.EntityProto clone = (OnestoreEntity.EntityProto)entity.clone();
      clones.add(clone);
      Preconditions.checkArgument(clone.hasKey());
      OnestoreEntity.Reference key = clone.getKey();
      Preconditions.checkArgument(key.getPath().elementSize() > 0);

      clone.getMutableKey().setApp(app);

      OnestoreEntity.Path.Element lastPath = Utils.getLastElement(key);

      if ((lastPath.getId() == 0L) && (!lastPath.hasName())) {
        lastPath.setId(this.entityId.getAndIncrement());
      }

      //processEntityForSpecialProperties(clone, true);

      if (clone.getEntityGroup().elementSize() == 0)
      {
        OnestoreEntity.Path group = clone.getMutableEntityGroup();
        OnestoreEntity.Path.Element root = (OnestoreEntity.Path.Element)key.getPath().elements().get(0);
        OnestoreEntity.Path.Element pathElement = group.addElement();
        pathElement.setType(root.getType());
        if (root.hasName())
          pathElement.setName(root.getName());
        else
          pathElement.setId(root.getId());
      }
      else
      {
        Preconditions.checkState((clone.hasEntityGroup()) && (clone.getEntityGroup().elementSize() > 0));
      }
    }

    /*
    Map entitiesByEntityGroup = new LinkedHashMap();

    final Profile profile = getOrCreateProfile(app);
    synchronized (profile) {
      LiveTxn liveTxn = null;
      for (Object original : clones) {
        OnestoreEntity.EntityProto clone = (OnestoreEntity.EntityProto) original;
        LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup(clone.getEntityGroup());
        if (request.hasTransaction())
        {
          if (liveTxn == null) {
            liveTxn = profile.getTxn(request.getTransaction().getHandle());
          }

          eg.addTransaction(liveTxn).addWrittenEntity(clone);
        } else {
          List entities = (List)entitiesByEntityGroup.get(clone.getEntityGroup());
          if (entities == null) {
            entities = new ArrayList();
            entitiesByEntityGroup.put(clone.getEntityGroup(), entities);
          }
          entities.add(clone);
        }
        response.mutableKeys().add(clone.getKey());
      }
      for (Object originalEntry : entitiesByEntityGroup.entrySet()) {
        final Map.Entry entry = (Map.Entry) originalEntry;
        LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup((OnestoreEntity.Path)entry.getKey());
        eg.incrementVersion();
        LocalDatastoreJob job = new LocalDatastoreJob(this.highRepJobPolicy, eg.pathAsKey())
        {
          DatastorePb.Cost calculateJobCost() {
            return LocalDatastoreService.this.calculatePutCost(false, profile, (Collection)entry.getValue());
          }

          DatastorePb.Cost applyInternal()
          {
            return LocalDatastoreService.this.calculatePutCost(true, profile, (Collection)entry.getValue());
          }
        };
        addTo(totalCost, eg.addJob(job));
      }
    }
    if (!request.hasTransaction()) {
      logger.fine("put: " + request.entitySize() + " entities");
    }
    response.setCost(totalCost);
    */

    proxy.doPost(app, "Put", request, response);
    return response;
  }

  private void validateAndProcessEntityProto(OnestoreEntity.EntityProto entity) {
    validatePathForPut(entity.getKey());
    for (OnestoreEntity.Property prop : entity.propertys()) {
      validateAndProcessProperty(prop);
    }
    for (OnestoreEntity.Property prop : entity.rawPropertys())
      validateAndProcessProperty(prop);
  }

  private void validatePathForPut(OnestoreEntity.Reference key)
  {
    OnestoreEntity.Path path = key.getPath();
    for (OnestoreEntity.Path.Element ele : path.elements()) {
      String type = ele.getType();
      if ((RESERVED_NAME.matcher(type).matches()) && (!RESERVED_NAME_WHITELIST.contains(type)))
        throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, String.format("illegal key.path.element.type: %s", new Object[] { ele.getType() }));
    }
  }

  private void validateAndProcessProperty(OnestoreEntity.Property prop)
  {
    if (RESERVED_NAME.matcher(prop.getName()).matches()) {
      throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, String.format("illegal property.name: %s", new Object[] { prop.getName() }));
    }

    OnestoreEntity.PropertyValue val = prop.getMutableValue();
    if (val.hasUserValue())
    {
      OnestoreEntity.PropertyValue.UserValue userVal = val.getMutableUserValue();
      userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail().hashCode()));
    }
  }

  @LatencyPercentiles(latency50th=40, dynamicAdjuster=WriteLatencyAdjuster.class)
  public DatastorePb.DeleteResponse delete(LocalRpcService.Status status, DatastorePb.DeleteRequest request) {
    try {
      this.globalLock.readLock().lock();
      DatastorePb.DeleteResponse localDeleteResponse = deleteImpl(status, request);
      return localDeleteResponse; } finally { this.globalLock.readLock().unlock(); } 
  }

  @LatencyPercentiles(latency50th=1)
  public ApiBasePb.VoidProto addActions(LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request) {
    try {
      this.globalLock.readLock().lock();
      addActionsImpl(status, request);
    } finally {
      this.globalLock.readLock().unlock();
    }
    return new ApiBasePb.VoidProto();
  }

  private OnestoreEntity.Path getGroup(OnestoreEntity.Reference key)
  {
    OnestoreEntity.Path path = key.getPath();
    OnestoreEntity.Path group = new OnestoreEntity.Path();
    group.addElement(path.getElement(0));
    return group;
  }

  public DatastorePb.DeleteResponse deleteImpl(LocalRpcService.Status status, DatastorePb.DeleteRequest request)
  {
    DatastorePb.DeleteResponse response = new DatastorePb.DeleteResponse();
    if (request.keySize() == 0) {
      return response;
    }

    /*
    DatastorePb.Cost totalCost = response.getMutableCost();

    String app = ((OnestoreEntity.Reference)request.keys().get(0)).getApp();
    final Profile profile = getOrCreateProfile(app);
    LiveTxn liveTxn = null;

    Map keysByEntityGroup = new LinkedHashMap();
    synchronized (profile) {
      for (OnestoreEntity.Reference key : request.keys()) {
        OnestoreEntity.Path group = getGroup(key);
        if (request.hasTransaction()) {
          if (liveTxn == null) {
            liveTxn = profile.getTxn(request.getTransaction().getHandle());
          }
          LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup(group);

          eg.addTransaction(liveTxn).addDeletedEntity(key);
        } else {
          List keysToDelete = (List)keysByEntityGroup.get(group);
          if (keysToDelete == null) {
            keysToDelete = new ArrayList();
            keysByEntityGroup.put(group, keysToDelete);
          }
          keysToDelete.add(key);
        }

      }

      for (Object originalEntry : keysByEntityGroup.entrySet()) {
        final Map.Entry entry = (Map.Entry) originalEntry;
        LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup((OnestoreEntity.Path)entry.getKey());
        eg.incrementVersion();
        LocalDatastoreJob job = new LocalDatastoreJob(this.highRepJobPolicy, eg.pathAsKey())
        {
          DatastorePb.Cost calculateJobCost() {
            return LocalDatastoreService.this.calculateDeleteCost(false, profile, (Collection)entry.getValue());
          }

          public DatastorePb.Cost applyInternal()
          {
            return LocalDatastoreService.this.calculateDeleteCost(true, profile, (Collection)entry.getValue());
          }
        };
        addTo(totalCost, eg.addJob(job));
      }
    }
    */

    proxy.doPost(request.getKey(0).getApp(), "Delete", request, response);
    return response;
  }

  private void addActionsImpl(LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request)
  {
    if (request.addRequestSize() == 0) {
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

  @LatencyPercentiles(latency50th=20)
  public DatastorePb.QueryResult runQuery(LocalRpcService.Status status, DatastorePb.Query query)
  {
    final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new LocalCompositeIndexManager.ValidatedQuery(query);

    query = validatedQuery.getQuery();

    String app = query.getApp();
    Profile profile = getOrCreateProfile(app);

    synchronized (profile)
    {
      if ((query.hasTransaction()) || (query.hasAncestor()))
      {
        OnestoreEntity.Path groupPath = getGroup(query.getAncestor());
        LocalDatastoreService.Profile.EntityGroup eg = profile.getGroup(groupPath);
        if (query.hasTransaction()) {
          if (!app.equals(query.getTransaction().getApp())) {
            throw Utils.newError(DatastorePb.Error.ErrorCode.INTERNAL_ERROR, "Can't query app " + app + "in a transaction on app " + query.getTransaction().getApp());
          }

          LiveTxn liveTxn = profile.getTxn(query.getTransaction().getHandle());

          eg.addTransaction(liveTxn);
        }

        if ((query.hasAncestor()) && (
          (query.hasTransaction()) || (!query.hasFailoverMs())))
        {
          eg.rollForwardUnappliedJobs();
        }

      }

      LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
      if ((query.hasSearchQuery()) && (fullTextIndex == null)) {
        throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "full-text search unsupported");
      }

      DatastorePb.QueryResult queryResult = new DatastorePb.QueryResult();
      proxy.doPost(app, "RunQuery", query, queryResult);   
      List<EntityProto> queryEntities = new ArrayList<EntityProto>(queryResult.results());

      if (queryEntities == null) {
        Map extents = profile.getExtents();
        Extent extent = (Extent)extents.get(query.getKind());

        if (!query.hasSearchQuery()) {
          if (extent != null)
          {
            queryEntities = new ArrayList(extent.getEntities().values());
          } else if (!query.hasKind())
          {
            queryEntities = profile.getAllEntities();
            if (query.orderSize() == 0)
            {
              query.addOrder(new DatastorePb.Query.Order().setDirection(DatastorePb.Query.Order.Direction.ASCENDING).setProperty("__key__"));
            }
          }

        }
        else
        {
          List keys = fullTextIndex.search(query.getKind(), query.getSearchQuery());
          List entities = new ArrayList(keys.size());
          for (Object originalKey : keys) {
	    OnestoreEntity.Reference key = (OnestoreEntity.Reference) originalKey;
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

      if (query.hasAncestor()) {
        final List ancestorPath = query.getAncestor().getPath().elements();
        predicates.add(new Predicate()
        {
          public boolean apply(Object o) {
            OnestoreEntity.EntityProto entity = (OnestoreEntity.EntityProto) o;
            List path = entity.getKey().getPath().elements();
            return (path.size() >= ancestorPath.size()) && (path.subList(0, ancestorPath.size()).equals(ancestorPath));
          }

        });
      }

      final boolean hasNamespace = query.hasNameSpace();
      final String namespace = query.getNameSpace();
      predicates.add(new Predicate()
      {
        public boolean apply(Object o) {
          OnestoreEntity.EntityProto entity = (OnestoreEntity.EntityProto) o;
          OnestoreEntity.Reference ref = entity.getKey();

          if (hasNamespace) {
            if ((!ref.hasNameSpace()) || (!namespace.equals(ref.getNameSpace()))) {
              return false;
            }
          }
          else if (ref.hasNameSpace()) {
            return false;
          }

          return true;
        }
      });
      final EntityProtoComparators.EntityProtoComparator entityComparator = new EntityProtoComparators.EntityProtoComparator(validatedQuery.getQuery().orders(), validatedQuery.getQuery().filters());

      predicates.add(new Predicate()
      {
        public boolean apply(Object o) {
          OnestoreEntity.EntityProto entity = (OnestoreEntity.EntityProto) o;
          return entityComparator.matches(entity);
        }
      });
      Predicate queryPredicate = Predicates.not(Predicates.and(predicates));

      Iterators.removeIf(queryEntities.iterator(), queryPredicate);

      if (query.propertyNameSize() > 0) {
        queryEntities = createIndexOnlyQueryResults(queryEntities, entityComparator);
      }

      Collections.sort(queryEntities, entityComparator);

      LiveQuery liveQuery = new LiveQuery(queryEntities, query, entityComparator, this.clock);

      /*
      AccessController.doPrivileged(new PrivilegedAction()
      {
        public Object run() {
          LocalCompositeIndexManager.getInstance().processQuery(validatedQuery.getQuery());
          return null;
        }
      }); */
      int count;
      if (query.hasCount()) {
        count = query.getCount();
      }
      else
      {
        if (query.hasLimit())
          count = query.getLimit();
        else {
          count = 20;
        }
      }

      DatastorePb.QueryResult result = nextImpl(liveQuery, query.getOffset(), count, query.isCompile());
      if (query.isCompile()) {
        result.setCompiledQuery(liveQuery.compileQuery());
      }
      if (result.isMoreResults()) {
        long cursor = this.queryId.getAndIncrement();
        profile.addQuery(cursor, liveQuery);
        result.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
      }

/*
      for (OnestoreEntity.Index index : LocalCompositeIndexManager.getInstance().queryIndexList(query)) {
        result.addIndex(wrapIndexInCompositeIndex(app, index));
      } */
      return result;
    }
  }

  private List<OnestoreEntity.EntityProto> createIndexOnlyQueryResults(List<OnestoreEntity.EntityProto> queryEntities, EntityProtoComparators.EntityProtoComparator entityComparator)
  {
    Set postfixProps = Sets.newHashSetWithExpectedSize(entityComparator.getAdjustedOrders().size());

    for (DatastorePb.Query.Order order : entityComparator.getAdjustedOrders()) {
      postfixProps.add(order.getProperty());
    }

    List results = Lists.newArrayListWithExpectedSize(queryEntities.size());
    for (OnestoreEntity.EntityProto entity : queryEntities) {
      List indexEntities = createIndexEntities(entity, postfixProps, entityComparator);
      results.addAll(indexEntities);
    }

    return results;
  }

  private List<OnestoreEntity.EntityProto> createIndexEntities(OnestoreEntity.EntityProto entity, Set<String> postfixProps, EntityProtoComparators.EntityProtoComparator entityComparator)
  {
    Multimap toSplit = HashMultimap.create(postfixProps.size(), 1);
    Set seen = Sets.newHashSet();
    boolean splitRequired = false;
    for (OnestoreEntity.Property prop : entity.propertys()) {
      if (postfixProps.contains(prop.getName()))
      {
        splitRequired |= !seen.add(prop.getName());

        if (entityComparator.matches(prop)) {
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

    for (Object originalEntry : toSplit.asMap().entrySet()) {
      Map.Entry entry = (Map.Entry) originalEntry;
      if (((Collection)entry.getValue()).size() == 1)
      {
        for (Object originalResult : results) {
	  OnestoreEntity.EntityProto result = (OnestoreEntity.EntityProto) originalResult;
          //result.addProperty().setName((String)entry.getKey()).setMeaning(OnestoreEntity.Property.Meaning.INDEX_VALUE).getMutableValue().copyFrom((ProtocolMessage)Iterables.getOnlyElement((Iterable)entry.getValue()));
          result.addProperty().setName((String)entry.getKey()).setMeaning(OnestoreEntity.Property.Meaning.INDEX_VALUE).getMutableValue().copyFrom((PropertyValue)Iterables.getOnlyElement((Iterable)entry.getValue()));
        }

        continue;
      }
      List splitResults = Lists.newArrayListWithCapacity(results.size() * ((Collection)entry.getValue()).size());

      for (Iterator i = ((Collection)entry.getValue()).iterator(); i.hasNext(); ) { 
	OnestoreEntity.PropertyValue value = (OnestoreEntity.PropertyValue)i.next();
        for (Object originalResult : results) {
	  OnestoreEntity.EntityProto result = (OnestoreEntity.EntityProto) originalResult;
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

  private static <T> T safeGetFromExpiringMap(Map<Long, T> map, long key, String errorMsg)
  {
    T value = map.get(Long.valueOf(key));
    if (value == null) {
      throw Utils.newError(DatastorePb.Error.ErrorCode.INTERNAL_ERROR, errorMsg);
    }
    return value;
  }
  @LatencyPercentiles(latency50th=50)
  public DatastorePb.QueryResult next(LocalRpcService.Status status, DatastorePb.NextRequest request) {
    Profile profile = (Profile)this.profiles.get(request.getCursor().getApp());
    LiveQuery liveQuery = profile.getQuery(request.getCursor().getCursor());

    int count = request.hasCount() ? request.getCount() : 20;
    DatastorePb.QueryResult result = nextImpl(liveQuery, request.getOffset(), count, request.isCompile());

    if (result.isMoreResults())
      result.setCursor(request.getCursor());
    else {
      profile.removeQuery(request.getCursor().getCursor());
    }

    return result;
  }

  private DatastorePb.QueryResult nextImpl(LiveQuery liveQuery, int offset, int count, boolean compile)
  {
    DatastorePb.QueryResult result = new DatastorePb.QueryResult();
    if (offset > 0) {
      result.setSkippedResults(liveQuery.offsetResults(offset));
    }

    if (offset == result.getSkippedResults())
    {
      int end = Math.min(300, count);
      result.mutableResults().addAll(liveQuery.nextResults(end));
    }
    result.setMoreResults(liveQuery.entitiesRemaining().size() > 0);
    result.setKeysOnly(liveQuery.isKeysOnly());
    if (compile) {
      result.getMutableCompiledCursor().addPosition(liveQuery.compilePosition());
    }
    return result;
  }

  public ApiBasePb.VoidProto deleteCursor(LocalRpcService.Status status, DatastorePb.Cursor request) {
    Profile profile = (Profile)this.profiles.get(request.getApp());
    profile.removeQuery(request.getCursor());
    return new ApiBasePb.VoidProto();
  }

  @LatencyPercentiles(latency50th=1)
  public DatastorePb.Transaction beginTransaction(LocalRpcService.Status status, DatastorePb.BeginTransactionRequest req)
  {
    Profile profile = getOrCreateProfile(req.getApp());
    DatastorePb.Transaction txn = new DatastorePb.Transaction().setApp(req.getApp()).setHandle(this.transactionHandleProvider.getAndIncrement());

    if ((req.isAllowMultipleEg()) && (!isHighRep())) {
      throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "transactions on multiple entity groups only allowed in High Replication applications");
    }
    proxy.doPost(req.getApp(), "BeginTransaction", req, txn);
    return txn;
  }
  @LatencyPercentiles(latency50th=20, dynamicAdjuster=WriteLatencyAdjuster.class)
  public DatastorePb.CommitResponse commit(LocalRpcService.Status status, DatastorePb.Transaction req) {
    Profile profile = (Profile)this.profiles.get(req.getApp());
    DatastorePb.CommitResponse response = new DatastorePb.CommitResponse();
    proxy.doPost(req.getApp(), "Commit", req, response);

    synchronized (profile) {
      /*
      LiveTxn liveTxn = profile.removeTxn(req.getHandle());
      if (liveTxn.isDirty()) {
        try {
          this.globalLock.readLock().lock();
          response.setCost(commitImpl(liveTxn, profile));
        } finally {
          this.globalLock.readLock().unlock();
        }
      }
      else {
        response.setCost(new DatastorePb.Cost().setEntityWrites(0).setIndexWrites(0));
      } */

      LiveTxn liveTxn = profile.removeTxn(req.getHandle());
      for (TaskQueuePb.TaskQueueAddRequest action : liveTxn.actions) {
        try {
          ApiProxy.makeSyncCall("taskqueue", "Add", action.toByteArray());
        } catch (ApiProxy.ApplicationException e) {
          logger.log(Level.WARNING, "Transactional task: " + action + " has been dropped.", e);
        }
      }
    }
    return response;
  }

  private DatastorePb.Cost commitImpl(LiveTxn liveTxn, final Profile profile)
  {
    for (EntityGroupTracker tracker : liveTxn.getAllTrackers())
    {
      tracker.checkEntityGroupVersion();
    }

    int deleted = 0;
    int written = 0;
    DatastorePb.Cost totalCost = new DatastorePb.Cost();
    for (EntityGroupTracker tracker : liveTxn.getAllTrackers()) {
      LocalDatastoreService.Profile.EntityGroup eg = tracker.getEntityGroup();
      eg.incrementVersion();

      final Collection writtenEntities = tracker.getWrittenEntities();
      final Collection deletedKeys = tracker.getDeletedKeys();
      LocalDatastoreJob job = new LocalDatastoreJob(this.highRepJobPolicy, eg.pathAsKey()) {
        private DatastorePb.Cost calculateJobCost(boolean apply) {
          DatastorePb.Cost cost = LocalDatastoreService.this.calculatePutCost(apply, profile, writtenEntities);
          //LocalDatastoreService.access$1000(cost, LocalDatastoreService.this.calculateDeleteCost(apply, profile, deletedKeys));
          return cost;
        }

        DatastorePb.Cost calculateJobCost()
        {
          return calculateJobCost(false);
        }

        DatastorePb.Cost applyInternal()
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
  @LatencyPercentiles(latency50th=1)
  public ApiBasePb.VoidProto rollback(LocalRpcService.Status status, DatastorePb.Transaction req) {
    VoidProto response = new VoidProto();
    proxy.doPost(req.getApp(), "Rollback", req, response);
    return response;
  }

  public ApiBasePb.Integer64Proto createIndex(LocalRpcService.Status status, OnestoreEntity.CompositeIndex req)
  {
    Integer64Proto response = new Integer64Proto();
    if (req.getId() != 0) {
      throw new IllegalArgumentException("New index id must be 0.");
    }
    proxy.doPost(req.getAppId(), "CreateIndex", req, response);
    //logger.log(Level.INFO, "createIndex response: " + response.toFlatString());
    return response;
    // throw new UnsupportedOperationException("Not yet implemented.");
  }

  public ApiBasePb.VoidProto updateIndex(LocalRpcService.Status status, OnestoreEntity.CompositeIndex req) {
    VoidProto response = new ApiBasePb.VoidProto();
    proxy.doPost(req.getAppId(), "UpdateIndex", req, response);
    return response;
  }

  private OnestoreEntity.CompositeIndex wrapIndexInCompositeIndex(String app, OnestoreEntity.Index index) {
    OnestoreEntity.CompositeIndex ci = new OnestoreEntity.CompositeIndex().setAppId(app).setState(OnestoreEntity.CompositeIndex.State.READ_WRITE);

    if (index != null) {
      ci.setDefinition(index);
    }
    return ci;
  }

  public DatastorePb.CompositeIndices getIndices(LocalRpcService.Status status, ApiBasePb.StringProto req) {
    DatastorePb.CompositeIndices answer = new DatastorePb.CompositeIndices();
    proxy.doPost(req.getValue(), "GetIndices", req, answer);
    return answer;
  }

  public ApiBasePb.VoidProto deleteIndex(LocalRpcService.Status status, OnestoreEntity.CompositeIndex req) {
    VoidProto response = new VoidProto();
    proxy.doPost(req.getAppId(), "DeleteIndex", req, response);
    return response;
  }
  @LatencyPercentiles(latency50th=1)
  public DatastorePb.AllocateIdsResponse allocateIds(LocalRpcService.Status status, DatastorePb.AllocateIdsRequest req) {
    try {
      this.globalLock.readLock().lock();
      DatastorePb.AllocateIdsResponse localAllocateIdsResponse = allocateIdsImpl(req);
      return localAllocateIdsResponse; } finally { this.globalLock.readLock().unlock(); } 
  }

  private DatastorePb.AllocateIdsResponse allocateIdsImpl(DatastorePb.AllocateIdsRequest req)
  {
    if (req.hasSize() && req.getSize() > MAX_BATCH_GET_KEYS) {
      throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(), "cannot get more than 1000000000 keys in a single call");
    }

    DatastorePb.AllocateIdsResponse response = new DatastorePb.AllocateIdsResponse();
    proxy.doPost("appId", "AllocateIds", req, response);
    return response;
  }

  Profile getOrCreateProfile(String app)
  {
    synchronized (this.profiles) {
      Preconditions.checkArgument((app != null) && (app.length() > 0), "appId not set");
      Profile profile = (Profile)this.profiles.get(app);
      if (profile == null) {
        profile = new Profile();
        this.profiles.put(app, profile);
      }
      return profile;
    }
  }

  Extent getOrCreateExtent(Profile profile, String kind) {
    Map extents = profile.getExtents();
    synchronized (extents) {
      Extent e = (Extent)extents.get(kind);
      if (e == null) {
        e = new Extent();
        extents.put(kind, e);
      }
      return e;
    }
  }

  private void load()
  {
    if (this.noStorage) {
      return;
    }
    File backingStoreFile = new File(this.backingStore);
    String path = backingStoreFile.getAbsolutePath();
    if (!backingStoreFile.exists()) {
      logger.log(Level.INFO, "The backing store, " + path + ", does not exist. " + "It will be created.");

      return;
    }
    try
    {
      long start = this.clock.getCurrentTime();
      ObjectInputStream objectIn = new ObjectInputStream(new BufferedInputStream(new FileInputStream(this.backingStore)));

      this.entityId.set(objectIn.readLong());

      Map profilesOnDisk = (Map)objectIn.readObject();
      this.profiles = profilesOnDisk;

      objectIn.close();
      long end = this.clock.getCurrentTime();

      logger.log(Level.INFO, "Time to load datastore: " + (end - start) + " ms");
    }
    catch (FileNotFoundException e) {
      logger.log(Level.SEVERE, "Failed to find the backing store, " + path);
    } catch (IOException e) {
      logger.log(Level.INFO, "Failed to load from the backing store, " + path, e);
    } catch (ClassNotFoundException e) {
      logger.log(Level.INFO, "Failed to load from the backing store, " + path, e);
    }
  }

  static void pruneHasCreationTimeMap(long now, int maxLifetimeMs, Map<Long, ? extends HasCreationTime> hasCreationTimeMap)
  {
    long deadline = now - maxLifetimeMs;
    Iterator queryIt = hasCreationTimeMap.entrySet().iterator();
    while (queryIt.hasNext()) {
      Map.Entry entry = (Map.Entry)queryIt.next();
      HasCreationTime query = (HasCreationTime)entry.getValue();
      if (query.getCreationTime() < deadline)
        queryIt.remove();
    }
  }

  static Map<String, SpecialProperty> getSpecialPropertyMap()
  {
    return specialPropertyMap;
  }

  void removeStaleQueriesNow()
  {
    this.removeStaleQueriesTask.run();
  }

  void removeStaleTxnsNow()
  {
    this.removeStaleTransactionsTask.run();
  }

  public Double getDefaultDeadline(boolean isOfflineRequest)
  {
    return Double.valueOf(30.0D);
  }

  public Double getMaximumDeadline(boolean isOfflineRequest)
  {
    return Double.valueOf(30.0D);
  }

  public CreationCostAnalysis getCreationCostAnalysis(Entity e)
  {
    return this.costAnalysis.getCreationCostAnalysis(EntityTranslator.convertToPb(e));
  }

  private static void addTo(DatastorePb.Cost target, DatastorePb.Cost addMe)
  {
    target.setEntityWrites(target.getEntityWrites() + addMe.getEntityWrites());
    target.setIndexWrites(target.getIndexWrites() + addMe.getIndexWrites());
  }

  private DatastorePb.Cost calculatePutCost(boolean apply, Profile profile, Collection<OnestoreEntity.EntityProto> entities)
  {
    DatastorePb.Cost totalCost = new DatastorePb.Cost();
    for (OnestoreEntity.EntityProto entityProto : entities) {
      String kind = Utils.getKind(entityProto.getKey());
      Extent extent = getOrCreateExtent(profile, kind);
      OnestoreEntity.EntityProto oldEntity;
      if (apply) {
        oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().put(entityProto.getKey(), entityProto);

        LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
        if (fullTextIndex != null)
          fullTextIndex.write(entityProto);
      }
      else {
        oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().get(entityProto.getKey());
      }
      addTo(totalCost, this.costAnalysis.getWriteOps(oldEntity, entityProto));
    }
    if (apply) {
      this.dirty = true;
    }
    return totalCost;
  }

  private DatastorePb.Cost calculateDeleteCost(boolean apply, Profile profile, Collection<OnestoreEntity.Reference> keys)
  {
    DatastorePb.Cost totalCost = new DatastorePb.Cost();
    for (OnestoreEntity.Reference key : keys) {
      String kind = Utils.getKind(key);
      Map extents = profile.getExtents();
      Extent extent = (Extent)extents.get(kind);
      if (extent != null)
      {
        OnestoreEntity.EntityProto oldEntity;
        if (apply) {
          oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().remove(key);
          LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
          if (fullTextIndex != null)
            fullTextIndex.delete(key);
        }
        else {
          oldEntity = (OnestoreEntity.EntityProto)extent.getEntities().get(key);
        }
        if (oldEntity != null) {
          addTo(totalCost, this.costAnalysis.getWriteCost(oldEntity));
        }
      }
    }
    if (apply) {
      this.dirty = true;
    }
    return totalCost;
  }

  private class PersistDatastore
    implements Runnable
  {
    private PersistDatastore()
    {
    }

    public void run()
    {
      try
      {
        LocalDatastoreService.this.globalLock.writeLock().lock();
        privilegedPersist();
      } catch (IOException e) {
        LocalDatastoreService.logger.log(Level.SEVERE, "Unable to save the datastore", e);
      } finally {
        LocalDatastoreService.this.globalLock.writeLock().unlock();
      }
    }

    private void privilegedPersist() throws IOException {
      try {
        AccessController.doPrivileged(new PrivilegedExceptionAction()
        {
          public Object run() throws IOException {
            LocalDatastoreService.PersistDatastore.this.persist();
            return null;
          } } );
      } catch (PrivilegedActionException e) {
        Throwable t = e.getCause();
        if ((t instanceof IOException)) {
          throw ((IOException)t);
        }
        throw new RuntimeException(t);
      }
    }

    private void persist() throws IOException {
      if ((LocalDatastoreService.this.noStorage) || (!LocalDatastoreService.this.dirty)) {
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

    private final String name;
    private final boolean isVisible;
    private final boolean isStored;

    private SpecialProperty(boolean isVisible, boolean isStored)
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

    OnestoreEntity.PropertyValue getValue(OnestoreEntity.EntityProto entity)
    {
      throw new UnsupportedOperationException();
    }

    OnestoreEntity.Property getProperty(OnestoreEntity.PropertyValue value)
    {
      OnestoreEntity.Property processedProp = new OnestoreEntity.Property();
      processedProp.setName(getName());
      processedProp.setValue(value);
      processedProp.setMultiple(false);
      return processedProp;
    }
  }

  private class RemoveStaleTransactions
    implements Runnable
  {
    private RemoveStaleTransactions()
    {
    }

    public void run()
    {
      for (LocalDatastoreService.Profile profile : LocalDatastoreService.this.profiles.values())
        synchronized (profile.txns) {
          LocalDatastoreService.pruneHasCreationTimeMap(LocalDatastoreService.this.clock.getCurrentTime(), LocalDatastoreService.this.maxTransactionLifetimeMs, profile.txns);
        }
    }
  }

  private class RemoveStaleQueries
    implements Runnable
  {
    private RemoveStaleQueries()
    {
    }

    public void run()
    {
      for (LocalDatastoreService.Profile profile : LocalDatastoreService.this.profiles.values())
        synchronized (profile.queries) {
          LocalDatastoreService.pruneHasCreationTimeMap(LocalDatastoreService.this.clock.getCurrentTime(), LocalDatastoreService.this.maxQueryLifetimeMs, profile.queries);
        }
    }
  }

  static class EntityGroupTracker
  {
    private LocalDatastoreService.Profile.EntityGroup entityGroup;
    private Long entityGroupVersion;
    private final Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> written = new HashMap();
    private final Set<OnestoreEntity.Reference> deleted = new HashSet();

    EntityGroupTracker(LocalDatastoreService.Profile.EntityGroup entityGroup) {
      this.entityGroup = entityGroup;
      this.entityGroupVersion = Long.valueOf(entityGroup.getVersion());
    }

    synchronized LocalDatastoreService.Profile.EntityGroup getEntityGroup() {
      return this.entityGroup;
    }

    synchronized void checkEntityGroupVersion() {
      if (!this.entityGroupVersion.equals(Long.valueOf(this.entityGroup.getVersion())))
        throw Utils.newError(DatastorePb.Error.ErrorCode.CONCURRENT_TRANSACTION, "too much contention on these datastore entities. please try again.");
    }

    synchronized Long getEntityGroupVersion()
    {
      return this.entityGroupVersion;
    }

    synchronized void addWrittenEntity(OnestoreEntity.EntityProto entity)
    {
      OnestoreEntity.Reference key = entity.getKey();
      this.written.put(key, entity);

      this.deleted.remove(key);
    }

    synchronized void addDeletedEntity(OnestoreEntity.Reference key)
    {
      this.deleted.add(key);

      this.written.remove(key);
    }

    synchronized Collection<OnestoreEntity.EntityProto> getWrittenEntities() {
      return new ArrayList(this.written.values());
    }

    synchronized Collection<OnestoreEntity.Reference> getDeletedKeys() {
      return new ArrayList(this.deleted);
    }

    synchronized boolean isDirty() {
      return this.written.size() + this.deleted.size() > 0;
    }
  }

  static class LiveTxn extends LocalDatastoreService.HasCreationTime
  {
    private final Map<LocalDatastoreService.Profile.EntityGroup, LocalDatastoreService.EntityGroupTracker> entityGroups = new HashMap();

    private final List<TaskQueuePb.TaskQueueAddRequest> actions = new ArrayList();
    private final boolean allowMultipleEg;
    private boolean failed = false;

    LiveTxn(Clock clock, boolean allowMultipleEg) {
      super(clock.getCurrentTime());
      this.allowMultipleEg = allowMultipleEg;
    }

    synchronized LocalDatastoreService.EntityGroupTracker trackEntityGroup(LocalDatastoreService.Profile.EntityGroup newEntityGroup)
    {
      if (newEntityGroup == null) {
        throw new NullPointerException("entityGroup cannot be null");
      }
      checkFailed();
      LocalDatastoreService.EntityGroupTracker tracker = (LocalDatastoreService.EntityGroupTracker)this.entityGroups.get(newEntityGroup);
      if (tracker == null) {
        if (this.allowMultipleEg) {
          if (this.entityGroups.size() >= 5) {
            throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "operating on too many entity groups in a single transaction.");
          }
        }
        else if (this.entityGroups.size() >= 1) {
          LocalDatastoreService.Profile.EntityGroup entityGroup = (LocalDatastoreService.Profile.EntityGroup)this.entityGroups.keySet().iterator().next();
          throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "can't operate on multiple entity groups in a single transaction.found both " + entityGroup + " and " + newEntityGroup);
        }

        for (LocalDatastoreService.EntityGroupTracker other : getAllTrackers()) {
          try {
            other.checkEntityGroupVersion();
          }
          catch (ApiProxy.ApplicationException e) {
            this.failed = true;
            throw e;
          }
        }

        tracker = new LocalDatastoreService.EntityGroupTracker(newEntityGroup);
        this.entityGroups.put(newEntityGroup, tracker);
      }
      return tracker;
    }

    synchronized Collection<LocalDatastoreService.EntityGroupTracker> getAllTrackers() {
      return this.entityGroups.values();
    }

    synchronized void addActions(Collection<TaskQueuePb.TaskQueueAddRequest> newActions) {
      checkFailed();
      if (this.actions.size() + newActions.size() > 5L) {
        throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "Too many messages, maximum allowed: 5");
      }

      this.actions.addAll(newActions);
    }

    synchronized Collection<TaskQueuePb.TaskQueueAddRequest> getActions() {
      return new ArrayList(this.actions);
    }

    synchronized boolean isDirty() {
      checkFailed();
      for (LocalDatastoreService.EntityGroupTracker tracker : getAllTrackers()) {
        if (tracker.isDirty()) {
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
      if (this.failed)
        throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "transaction closed");
    }
  }

  static class LiveQuery extends LocalDatastoreService.HasCreationTime
  {
    private final Set<String> orderProperties;
    private final Set<String> projectedProperties;
    private final DatastorePb.Query query;
    private List<OnestoreEntity.EntityProto> entities;
    private OnestoreEntity.EntityProto lastResult = null;

    public LiveQuery(List<OnestoreEntity.EntityProto> entities, DatastorePb.Query query, EntityProtoComparators.EntityProtoComparator entityComparator, Clock clock)
    {
      super(clock.getCurrentTime());
      if (entities == null) {
        throw new NullPointerException("entities cannot be null");
      }

      this.query = query;
      this.entities = entities;

      this.orderProperties = new HashSet();
      for (DatastorePb.Query.Order order : entityComparator.getAdjustedOrders()) {
        if (!"__key__".equals(order.getProperty())) {
          this.orderProperties.add(order.getProperty());
        }
      }

      this.projectedProperties = Sets.newHashSet(query.propertyNames());
      applyCursors(entityComparator);
      applyLimit();
      entities = Lists.newArrayList(entities);
    }

    private void applyCursors(EntityProtoComparators.EntityProtoComparator entityComparator) {
      DecompiledCursor startCursor = new DecompiledCursor(this.query.getCompiledCursor());
      this.lastResult = startCursor.getCursorEntity();
      int endCursorPos = new DecompiledCursor(this.query.getEndCompiledCursor()).getPosition(entityComparator, this.entities.size());

      int startCursorPos = Math.min(endCursorPos, startCursor.getPosition(entityComparator, 0));

      this.entities = this.entities.subList(startCursorPos, endCursorPos);
    }

    private void applyLimit() {
      if (this.query.hasLimit()) {
        int toIndex = this.query.getLimit() + this.query.getOffset();
        if ((toIndex < 0) || (toIndex > this.entities.size())) {
          toIndex = this.entities.size();
        }
        this.entities = this.entities.subList(0, toIndex);
      }
    }

    public List<OnestoreEntity.EntityProto> entitiesRemaining() {
      return this.entities;
    }

    public int offsetResults(int offset) {
      int realOffset = Math.min(Math.min(offset, this.entities.size()), 300);
      if (realOffset > 0) {
        this.lastResult = ((OnestoreEntity.EntityProto)this.entities.get(realOffset - 1));
        this.entities = this.entities.subList(realOffset, this.entities.size());
      }
      return realOffset;
    }

    public List<OnestoreEntity.EntityProto> nextResults(int end) {
      List subList = this.entities.subList(0, Math.min(end, this.entities.size()));

      if (subList.size() > 0)
      {
        this.lastResult = ((OnestoreEntity.EntityProto)subList.get(subList.size() - 1));
      }

      List results = new ArrayList(subList.size());
      for (Object originalEntity : subList)
      {
	OnestoreEntity.EntityProto entity = (OnestoreEntity.EntityProto) originalEntity;
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
                throw Utils.newError(DatastorePb.Error.ErrorCode.INTERNAL_ERROR, "LocalDatstoreServer produced invalude results.");
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
        //LocalDatastoreService.access$1600(result, false);
        results.add(result);
      }
      subList.clear();
      return results;
    }

    public void restrictRange(int fromIndex, int toIndex)
    {
      toIndex = Math.max(fromIndex, toIndex);

      if (fromIndex > 0)
      {
        this.lastResult = ((OnestoreEntity.EntityProto)this.entities.get(fromIndex - 1));
      }

      if ((fromIndex != 0) || (toIndex != this.entities.size()))
        this.entities = new ArrayList(this.entities.subList(fromIndex, toIndex));
    }

    public boolean isKeysOnly()
    {
      return this.query.isKeysOnly();
    }

    public OnestoreEntity.EntityProto decompilePosition(DatastorePb.CompiledCursor.Position position) {
      OnestoreEntity.EntityProto result = new OnestoreEntity.EntityProto();
      if (position.hasKey()) {
        if ((this.query.hasKind()) && (!this.query.getKind().equals(((OnestoreEntity.Path.Element)Iterables.getLast(position.getKey().getPath().elements())).getType())))
        {
          throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
        }
        result.setKey(position.getKey());
      }

      Set remainingProperties = new HashSet(this.orderProperties);
      for (DatastorePb.CompiledCursor.PositionIndexValue prop : position.indexValues()) {
        if (!this.orderProperties.contains(prop.getProperty()))
        {
          throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
        }
        remainingProperties.remove(prop.getProperty());
        result.addProperty().setName(prop.getProperty()).setValue(prop.getValue());
      }

      if (!remainingProperties.isEmpty()) {
        throw Utils.newError(DatastorePb.Error.ErrorCode.BAD_REQUEST, "Cursor does not match query.");
      }
      return result;
    }

    public DatastorePb.CompiledCursor.Position compilePosition()
    {
      DatastorePb.CompiledCursor.Position position = new DatastorePb.CompiledCursor.Position();

      if (this.lastResult != null)
      {
        position.setKey(this.lastResult.getKey());

        for (OnestoreEntity.Property prop : this.lastResult.propertys()) {
          if (this.orderProperties.contains(prop.getName())) {
            position.addIndexValue().setProperty(prop.getName()).setValue(prop.getValue());
          }
        }

        position.setStartInclusive(false);
      }

      return position;
    }

    public DatastorePb.CompiledQuery compileQuery() {
      DatastorePb.CompiledQuery result = new DatastorePb.CompiledQuery();
      DatastorePb.CompiledQuery.PrimaryScan scan = result.getMutablePrimaryScan();

      scan.setIndexNameAsBytes(this.query.toByteArray());

      return result;
    }

    class DecompiledCursor
    {
      final OnestoreEntity.EntityProto cursorEntity;
      final boolean inclusive;

      public DecompiledCursor(DatastorePb.CompiledCursor compiledCursor)
      {
        if ((compiledCursor == null) || (compiledCursor.positionSize() == 0)) {
          this.cursorEntity = null;
          this.inclusive = false;
          return;
        }

        DatastorePb.CompiledCursor.Position position = compiledCursor.getPosition(0);
        if ((!position.hasStartKey()) && (!position.hasKey()) && (position.indexValueSize() <= 0)) {
          this.cursorEntity = null;
          this.inclusive = false;
          return;
        }

        this.cursorEntity = LocalDatastoreService.LiveQuery.this.decompilePosition(position);
        this.inclusive = position.isStartInclusive();
      }

      public int getPosition(EntityProtoComparators.EntityProtoComparator entityComparator, int defaultValue) {
        if (this.cursorEntity == null) {
          return defaultValue;
        }

        int loc = Collections.binarySearch(LocalDatastoreService.LiveQuery.this.entities, this.cursorEntity, entityComparator);
        if (loc < 0) {
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

    HasCreationTime(long creationTime)
    {
      this.creationTime = creationTime;
    }

    long getCreationTime() {
      return this.creationTime;
    }
  }

  static class Extent
    implements Serializable
  {
    private Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> entities = new LinkedHashMap();

    public Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto> getEntities() {
      return this.entities;
    }
  }

  static class Profile
    implements Serializable
  {
    private final Map<String, LocalDatastoreService.Extent> extents = Collections.synchronizedMap(new HashMap());
    private transient Map<OnestoreEntity.Path, EntityGroup> groups;
    private transient Set<OnestoreEntity.Path> groupsWithUnappliedJobs;
    private transient Map<Long, LocalDatastoreService.LiveQuery> queries;
    private transient Map<Long, LocalDatastoreService.LiveTxn> txns;
    private final LocalFullTextIndex fullTextIndex;

    public synchronized List<OnestoreEntity.EntityProto> getAllEntities()
    {
      List entities = new ArrayList();
      for (LocalDatastoreService.Extent extent : this.extents.values()) {
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

      if (indexClass == null) {
        return null;
      }
      try
      {
        return (LocalFullTextIndex)indexClass.newInstance();
      } catch (InstantiationException e) {
        throw new RuntimeException(e); 
      } catch (IllegalAccessException e) {
      }
      throw new RuntimeException();
    }

    private Class getFullTextIndexClass()
    {
      try
      {
        return Class.forName("com.google.appengine.api.datastore.dev.LuceneFullTextIndex");
      }
      catch (ClassNotFoundException e) {
        return null; } catch (NoClassDefFoundError e) {
      }
      return null;
    }

    public Map<String, LocalDatastoreService.Extent> getExtents()
    {
      return this.extents;
    }

    public synchronized EntityGroup getGroup(OnestoreEntity.Path path) {
      Map map = getGroups();
      EntityGroup group = (EntityGroup)map.get(path);
      if (group == null) {
        group = new EntityGroup(path);
        map.put(path, group);
      }
      return group;
    }

    private synchronized void groom()
    {
      for (Object originalPath : new HashSet(getGroupsWithUnappliedJobs())) {
        OnestoreEntity.Path path = (OnestoreEntity.Path) originalPath;
        EntityGroup eg = getGroup(path);
        eg.maybeRollForwardUnappliedJobs();
      }
    }

    public synchronized LocalDatastoreService.LiveQuery getQuery(long cursor) {
      LocalDatastoreService.LiveQuery result = getQueries().get(cursor);
      if (result == null) {
        throw new RuntimeException("query has expired or is invalid. Please restart it with the last cursor to read more results.");
      } else {
        return result;
      }
    }

    public synchronized void addQuery(long cursor, LocalDatastoreService.LiveQuery query) {
      getQueries().put(Long.valueOf(cursor), query);
    }

    private synchronized LocalDatastoreService.LiveQuery removeQuery(long cursor) {
      LocalDatastoreService.LiveQuery query = getQuery(cursor);
      this.queries.remove(Long.valueOf(cursor));
      return query;
    }

    private synchronized Map<Long, LocalDatastoreService.LiveQuery> getQueries() {
      if (this.queries == null) {
        this.queries = new HashMap();
      }
      return this.queries;
    }

    public synchronized LocalDatastoreService.LiveTxn getTxn(long handle) {
      LocalDatastoreService.LiveTxn result = getTxns().get(handle);
      if (result == null) {
        throw new RuntimeException("transaction has expired or is invalid");
      } else {
        return result;
      }
    }

    public LocalFullTextIndex getFullTextIndex()
    {
      return this.fullTextIndex;
    }

    public synchronized void addTxn(long handle, LocalDatastoreService.LiveTxn txn) {
      getTxns().put(Long.valueOf(handle), txn);
    }

    private synchronized LocalDatastoreService.LiveTxn removeTxn(long handle) {
      LocalDatastoreService.LiveTxn txn = getTxn(handle);
      txn.close();
      this.txns.remove(Long.valueOf(handle));
      return txn;
    }

    private synchronized Map<Long, LocalDatastoreService.LiveTxn> getTxns() {
      if (this.txns == null) {
        this.txns = new HashMap();
      }
      return this.txns;
    }

    private synchronized Map<OnestoreEntity.Path, EntityGroup> getGroups() {
      if (this.groups == null) {
        this.groups = new LinkedHashMap();
      }
      return this.groups;
    }

    private synchronized Set<OnestoreEntity.Path> getGroupsWithUnappliedJobs() {
      if (this.groupsWithUnappliedJobs == null) {
        this.groupsWithUnappliedJobs = new LinkedHashSet();
      }
      return this.groupsWithUnappliedJobs;
    }

    class EntityGroup
    {
      private final OnestoreEntity.Path path;
      private final AtomicLong version = new AtomicLong();
      private final WeakHashMap<LocalDatastoreService.LiveTxn, LocalDatastoreService.Profile> snapshots = new WeakHashMap();

      private final LinkedList<LocalDatastoreJob> unappliedJobs = new LinkedList();

      private EntityGroup(OnestoreEntity.Path path)
      {
        this.path = path;
      }

      public long getVersion() {
        return this.version.get();
      }

      public void incrementVersion()
      {
        long oldVersion = this.version.getAndIncrement();
        LocalDatastoreService.Profile snapshot = null;
        for (LocalDatastoreService.LiveTxn txn : this.snapshots.keySet())
          if (txn.trackEntityGroup(this).getEntityGroupVersion().longValue() == oldVersion) {
            if (snapshot == null) {
              snapshot = takeSnapshot();
            }
            this.snapshots.put(txn, snapshot);
          }
      }

      public OnestoreEntity.EntityProto get(LocalDatastoreService.LiveTxn liveTxn, OnestoreEntity.Reference key, boolean eventualConsistency)
      {
        if (!eventualConsistency)
        {
          rollForwardUnappliedJobs();
        }
        LocalDatastoreService.Profile profile = getSnapshot(liveTxn);
        Map extents = profile.getExtents();
        LocalDatastoreService.Extent extent = (LocalDatastoreService.Extent)extents.get(Utils.getKind(key));
        if (extent != null) {
          Map entities = extent.getEntities();
          return (OnestoreEntity.EntityProto)entities.get(key);
        }
        return null;
      }

      public LocalDatastoreService.EntityGroupTracker addTransaction(LocalDatastoreService.LiveTxn txn) {
        LocalDatastoreService.EntityGroupTracker tracker = txn.trackEntityGroup(this);
        if (!this.snapshots.containsKey(txn)) {
          this.snapshots.put(txn, null);
        }
        return tracker;
      }

      public void removeTransaction(LocalDatastoreService.LiveTxn txn) {
        this.snapshots.remove(txn);
      }

      private LocalDatastoreService.Profile getSnapshot(LocalDatastoreService.LiveTxn txn) {
        if (txn == null) {
          return LocalDatastoreService.Profile.this;
        }
        LocalDatastoreService.Profile snapshot = (LocalDatastoreService.Profile)this.snapshots.get(txn);
        if (snapshot == null) {
          return LocalDatastoreService.Profile.this;
        }
        return snapshot;
      }

      private LocalDatastoreService.Profile takeSnapshot()
      {
        try {
          ByteArrayOutputStream bos = new ByteArrayOutputStream();
          ObjectOutputStream oos = new ObjectOutputStream(bos);
          oos.writeObject(LocalDatastoreService.Profile.this);
          oos.close();
          ByteArrayInputStream bis = new ByteArrayInputStream(bos.toByteArray());
          ObjectInputStream ois = new ObjectInputStream(bis);
          return (LocalDatastoreService.Profile)ois.readObject();
        } catch (IOException ex) {
          throw new RuntimeException("Unable to take transaction snapshot.", ex); } catch (ClassNotFoundException ex) {
        }
        throw new RuntimeException("Unable to take transaction snapshot.");
      }

      public String toString()
      {
        return this.path.toString();
      }

      public DatastorePb.Cost addJob(LocalDatastoreJob job)
      {
        this.unappliedJobs.addLast(job);
        LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().add(this.path);
        return maybeRollForwardUnappliedJobs();
      }

      public void rollForwardUnappliedJobs()
      {
        if (!this.unappliedJobs.isEmpty()) {
          for (LocalDatastoreJob applyJob : this.unappliedJobs) {
            applyJob.apply();
          }
          this.unappliedJobs.clear();
          LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().remove(this.path);
          LocalDatastoreService.logger.fine("Rolled forward unapplied jobs for " + this.path);
        }
      }

      public DatastorePb.Cost maybeRollForwardUnappliedJobs()
      {
        int jobsAtStart = this.unappliedJobs.size();
        LocalDatastoreService.logger.fine(String.format("Maybe rolling forward %d unapplied jobs for %s.", new Object[] { Integer.valueOf(jobsAtStart), this.path }));

        int applied = 0;
        DatastorePb.Cost totalCost = new DatastorePb.Cost();
        for (Iterator iter = this.unappliedJobs.iterator(); iter.hasNext(); ) {
          LocalDatastoreJob.TryApplyResult result = ((LocalDatastoreJob)iter.next()).tryApply();
          //LocalDatastoreService.access$1000(totalCost, result.cost);
          if (!result.applied) break;
          iter.remove();
          applied++;
        }

        if (this.unappliedJobs.isEmpty()) {
          LocalDatastoreService.Profile.this.getGroupsWithUnappliedJobs().remove(this.path);
        }
        LocalDatastoreService.logger.fine(String.format("Rolled forward %d of %d jobs for %s", new Object[] { Integer.valueOf(applied), Integer.valueOf(jobsAtStart), this.path }));

        return totalCost;
      }

      public Key pathAsKey() {
        OnestoreEntity.Reference entityGroupRef = new OnestoreEntity.Reference();
        entityGroupRef.setPath(this.path);
        return LocalCompositeIndexManager.KeyTranslator.createFromPb(entityGroupRef);
      }
    }
  }
}
