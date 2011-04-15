package com.google.appengine.api.datastore.dev;

import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;

import com.google.appengine.api.labs.taskqueue.TaskQueuePb;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.api.DatastorePb.DeleteResponse;
import com.google.apphosting.api.DatastorePb.Query;
import com.google.apphosting.api.DatastorePb.QueryResult;
import com.google.apphosting.api.DatastorePb.GetResponse.Entity;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService implements LocalRpcService {
	private static final Logger logger = Logger
			.getLogger(LocalDatastoreService.class.getName());
	static final int DEFAULT_BATCH_SIZE = 20;
	static final int MAXIMUM_RESULTS_SIZE = 1000;
	public static final String PACKAGE = "datastore_v3";
	public static final String MAX_QUERY_LIFETIME_PROPERTY = "datastore.max_query_lifetime";
	private static final int DEFAULT_MAX_QUERY_LIFETIME = 30000;
	public static final String MAX_TRANSACTION_LIFETIME_PROPERTY = "datastore.max_txn_lifetime";
	private static final int DEFAULT_MAX_TRANSACTION_LIFETIME = 30000;
	public static final String STORE_DELAY_PROPERTY = "datastore.store_delay";
	static final int DEFAULT_STORE_DELAY_MS = 30000;
	public static final String BACKING_STORE_PROPERTY = "datastore.backing_store";
	public static final String NO_INDEX_AUTO_GEN_PROP = "datastore.no_index_auto_gen";
	public static final String NO_STORAGE_PROPERTY = "datastore.no_storage";
	private static final Pattern RESERVED_NAME = Pattern.compile("__.*__");
	static final String ENTITY_GROUP_MESSAGE = "can't operate on multiple entity groups in a single transaction.";
	static final String CONTENTION_MESSAGE = "too much contention on these datastore entities. please try again.";
	static final String HANDLE_NOT_FOUND_MESSAGE_FORMAT = "handle %s not found";
	static final String GET_SCHEMA_START_PAST_END = "start_kind must be <= end_kind";
	private final AtomicLong entityId = new AtomicLong(1L);

	private final AtomicLong queryId = new AtomicLong(0L);
	private String backingStore;
	// private Map<String, Profile> profiles = Collections
	// .synchronizedMap(new HashMap<String, Profile>());
	private Clock clock;
	private static final long MAX_BATCH_GET_KEYS = 1000000000L;
	private static final long MAX_ACTIONS_PER_TXN = 5L;
	private int maxQueryLifetimeMs;
	private int maxTransactionLifetimeMs;
	// private final ScheduledThreadPoolExecutor scheduler = new
	// ScheduledThreadPoolExecutor(
	// 2);

	// private final RemoveStaleQueries removeStaleQueriesTask = new
	// RemoveStaleQueries();

	// private final RemoveStaleTransactions removeStaleTransactionsTask = new
	// RemoveStaleTransactions();

	// private final PersistDatastore persistDatastoreTask = new
	// PersistDatastore();

	private final AtomicInteger transactionHandleProvider = new AtomicInteger(0);
	// private int storeDelayMs;
	private boolean dirty;
	// private final ReadWriteLock globalLock = new ReentrantReadWriteLock();
	private boolean noStorage;
	private Thread shutdownHook;
	private HTTPClientDatastoreProxy proxy;

	public void clearProfiles() {
		// for (Profile profile : this.profiles.values()) {
		// LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
		// if (fullTextIndex != null) {
		// fullTextIndex.close();
		// }
		// }
		//
		// this.profiles.clear();
	}

	public LocalDatastoreService() {
		ResourceLoader res = ResourceLoader.getResouceLoader();
		String host = res.getPbServerIp();
		int port = res.getPbServerPort();
		boolean isSSL = res.getDatastoreSeurityMode();
		System.out.println("host: " + host);
		System.out.println(" port: " + port);
		System.out.println(" isSSL: " + isSSL);
		proxy = new HTTPClientDatastoreProxy(host, port, isSSL);
		// setMaxQueryLifetime(30000);
		// setMaxTransactionLifetime(30000);
		// setStoreDelay(30000);
	}

	public void init(LocalServiceContext context, Map<String, String> properties) {
		// System.out.println("appdir: "+
		// context.getLocalServerEnvironment().getAppDir().getName());
		// System.out.println("abs path: "+context.getLocalServerEnvironment().getAppDir().getAbsolutePath());
		// this.clock = context.getClock();
		// String storeFile = (String)
		// properties.get("datastore.backing_store");
		// if (storeFile == null) {
		// File dir = GenerationDirectory.getGenerationDirectory(context
		// .getLocalServerEnvironment().getAppDir());
		//
		// dir.mkdirs();
		// storeFile = dir.getAbsolutePath() + File.separator + "local_db.bin";
		// }
		// setBackingStore(storeFile);
		//
		// String noStorageProp = (String)
		// properties.get("datastore.no_storage");
		// if (noStorageProp != null) {
		// this.noStorage = Boolean.valueOf(noStorageProp).booleanValue();
		// }
		//
		// String storeDelayTime = (String) properties
		// .get("datastore.store_delay");
		// this.storeDelayMs = parseInt(storeDelayTime, this.storeDelayMs,
		// "datastore.store_delay");
		//
		// String maxQueryLifetime = (String) properties
		// .get("datastore.max_query_lifetime");
		// this.maxQueryLifetimeMs = parseInt(maxQueryLifetime,
		// this.maxQueryLifetimeMs, "datastore.max_query_lifetime");
		//
		// String maxTxnLifetime = (String) properties
		// .get("datastore.max_txn_lifetime");
		// this.maxTransactionLifetimeMs = parseInt(maxTxnLifetime,
		// this.maxTransactionLifetimeMs, "datastore.max_txn_lifetime");
		//
		// LocalCompositeIndexManager.getInstance().setAppDir(
		// context.getLocalServerEnvironment().getAppDir());
		//
		// LocalCompositeIndexManager.getInstance().setClock(this.clock);
		//
		// String noIndexAutoGenProp = (String) properties
		// .get("datastore.no_index_auto_gen");
		// if (noIndexAutoGenProp != null)
		// LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(
		// Boolean.valueOf(noIndexAutoGenProp).booleanValue());
	}

	// private static int parseInt(String valStr, int defaultVal, String
	// propName) {
	// if (valStr != null) {
	// try {
	// return Integer.parseInt(valStr);
	// } catch (NumberFormatException e) {
	// logger.log(Level.WARNING,
	// "Expected a numeric value for property " + propName
	// + "but received, " + valStr
	// + ". Resetting property to the default.");
	// }
	// }
	//
	// return defaultVal;
	// }

	private static int parseInt(String valStr, int defaultVal, String propName) {
		if (valStr != null) {
			try {
				return Integer.parseInt(valStr);
			} catch (NumberFormatException e) {
				logger.log(Level.WARNING,
						"Expected a numeric value for property " + propName
								+ "but received, " + valStr
								+ ". Resetting property to the default.");
			}
		}

		return defaultVal;
	}

	public void start() {
		AccessController.doPrivileged(new PrivilegedAction<Object>() {
			public Object run() {
				LocalDatastoreService.this.start_();
				return null;
			}
		});
	}

	private void start_() {
		// if (!(this.noStorage)) {
		// load();
		// }
		// this.scheduler.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
		// this.scheduler.scheduleWithFixedDelay(this.removeStaleQueriesTask,
		// this.maxQueryLifetimeMs * 5, this.maxQueryLifetimeMs * 5,
		// TimeUnit.MILLISECONDS);
		//
		// this.scheduler.scheduleWithFixedDelay(this.removeStaleTransactionsTask,
		// this.maxTransactionLifetimeMs * 5,
		// this.maxTransactionLifetimeMs * 5, TimeUnit.MILLISECONDS);
		//
		// if (!(this.noStorage)) {
		// this.scheduler
		// .scheduleWithFixedDelay(this.persistDatastoreTask,
		// this.storeDelayMs, this.storeDelayMs,
		// TimeUnit.MILLISECONDS);
		// }

		this.shutdownHook = new Thread() {
			public void run() {
				LocalDatastoreService.this.stop();
			}

		};
		Runtime.getRuntime().addShutdownHook(this.shutdownHook);
	}

	public void stop() {
		// this.scheduler.shutdown();
		// if (!(this.noStorage)) {
		// this.persistDatastoreTask.run();
		// }

		clearProfiles();
		try {
			Runtime.getRuntime().removeShutdownHook(this.shutdownHook);
		} catch (IllegalStateException ex) {
		}
	}

	// public void setMaxQueryLifetime(int milliseconds) {
	// this.maxQueryLifetimeMs = milliseconds;
	// }
	//
	// public void setMaxTransactionLifetime(int milliseconds) {
	// this.maxTransactionLifetimeMs = milliseconds;
	// }
	//
	// public void setBackingStore(String backingStore) {
	// this.backingStore = backingStore;
	// }
	//
	// public void setStoreDelay(int delayMs) {
	// this.storeDelayMs = delayMs;
	// }
	//
	// public void setNoStorage(boolean noStorage) {
	// this.noStorage = noStorage;
	// }

	public String getPackage() {
		return "datastore_v3";
	}

	public DatastorePb.GetResponse get(LocalRpcService.Status status,
			DatastorePb.GetRequest request) {

		log(request, "get request! ");
		/* modified */
		DatastorePb.GetResponse response = new DatastorePb.GetResponse();
		response.parseFrom(this.outputToSocket(request.getKey(0).getApp(),
				"Get", request));
		if (response.entitySize() == 0)
			response.addEntity(new Entity());
		/* modification end */

		// LiveTxn liveTxn = null;
		// for (OnestoreEntity.Reference key : request.keys()) {
		// String app = key.getApp();
		// OnestoreEntity.Path groupPath = getGroup(key);
		// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
		// getLast(key
		// .getPath().elements());
		// DatastorePb.GetResponse.Entity group = response.addEntity();
		// Profile profile = getOrCreateProfile(app);
		// synchronized (profile) {
		// Profile.EntityGroup eg = profile.getGroup(groupPath);
		// if (request.hasTransaction()) {
		// if (liveTxn == null) {
		// liveTxn = profile.getTxn(request.getTransaction()
		// .getHandle());
		// }
		//
		// eg.addTransaction(liveTxn);
		// }
		//
		// OnestoreEntity.EntityProto entity = eg.get(liveTxn, key);
		// if (entity != null) {
		// group.getMutableEntity().copyFrom(entity);
		// }
		// }
		// }

		log(response, "get response: ");
		return response;
	}

	public DatastorePb.PutResponse put(LocalRpcService.Status status,
			DatastorePb.PutRequest request) {
		try {
			// this.globalLock.readLock().lock();
			DatastorePb.PutResponse localPutResponse = putImpl(status, request);

			return localPutResponse;
		} finally {
			// this.globalLock.readLock().unlock();
		}
	}

	public DatastorePb.PutResponse putImpl(LocalRpcService.Status status,
			DatastorePb.PutRequest request) {
		log(request, "put request! ");
		DatastorePb.PutResponse response = new DatastorePb.PutResponse();

		/* modified */
		String app = request.getEntity(0).getKey().getApp();
		response.parseFrom(outputToSocket(app, "Put", request));
		/* modification end */

		// List<OnestoreEntity.EntityProto> clones = new
		// ArrayList<OnestoreEntity.EntityProto>();
		// String app = null;
		// Profile profile = null;
		// LiveTxn liveTxn = null;
		// for (OnestoreEntity.EntityProto entity : request.entitys()) {
		// validateAndProcessEntityProto(entity);
		// OnestoreEntity.EntityProto clone = (OnestoreEntity.EntityProto)
		// entity
		// .clone();
		// clones.add(clone);
		// Preconditions.checkArgument(clone.hasKey());
		// OnestoreEntity.Reference key = clone.getKey();
		// Preconditions.checkArgument(key.getPath().elementSize() > 0);
		//
		// if (app == null) {
		// app = key.getApp();
		// profile = getOrCreateProfile(app);
		// }
		//
		// clone.getMutableKey().setApp(app);
		//
		// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
		// getLast(key
		// .getPath().elements());
		//
		// if ((!(lastPath.hasId())) && (!(lastPath.hasName()))) {
		// lastPath.setId(this.entityId.getAndIncrement());
		// }
		//
		// if (clone.getEntityGroup().elementSize() == 0) {
		// OnestoreEntity.Path group = clone.getMutableEntityGroup();
		// OnestoreEntity.Path.Element root = (OnestoreEntity.Path.Element) key
		// .getPath().elements().get(0);
		// OnestoreEntity.Path.Element pathElement = group.addElement();
		// pathElement.setType(root.getType());
		// if (root.hasName())
		// pathElement.setName(root.getName());
		// else
		// pathElement.setId(root.getId());
		// } else {
		// Preconditions.checkState((clone.hasEntityGroup())
		// && (clone.getEntityGroup().elementSize() > 0));
		// }
		// }
		//
		// synchronized (profile) {
		// for (OnestoreEntity.EntityProto clone : clones) {
		// OnestoreEntity.Reference key = clone.getKey();
		// String kind = ((OnestoreEntity.Path.Element) getLast(key
		// .getPath().elements())).getType();
		// Extent extent = getOrCreateExtent(profile, kind);
		// Profile.EntityGroup eg = profile.getGroup(clone
		// .getEntityGroup());
		// if (request.hasTransaction()) {
		// if (liveTxn == null) {
		// liveTxn = profile.getTxn(request.getTransaction()
		// .getHandle());
		// }
		//
		// eg.addTransaction(liveTxn);
		// liveTxn.addWrittenEntity(clone);
		// } else {
		// eg.incrementVersion();
		// extent.getEntities().put(key, clone);
		// LocalFullTextIndex fullTextIndex = profile
		// .getFullTextIndex();
		// if (fullTextIndex != null) {
		// fullTextIndex.write(clone);
		// }
		// this.dirty = true;
		// }
		// response.mutableKeys().add(clone.getKey());
		// }
		// }

		log(response, "put result! ");
		return response;
	}

	 private void validateAndProcessEntityProto(OnestoreEntity.EntityProto entity) {
		    for (OnestoreEntity.Property prop : entity.propertys()) {
		      validateAndProcessProperty(prop);
		    }
		    for (OnestoreEntity.Property prop : entity.rawPropertys())
		      validateAndProcessProperty(prop);
		  }
	  private void validateAndProcessProperty(OnestoreEntity.Property prop)
	  {
	    if (RESERVED_NAME.matcher(prop.getName()).matches()) {
	      throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(), String.format("'%s' matches the pattern for reserved property names and can therefore not be used.", new Object[] { prop.getName() }));
	    }

	    OnestoreEntity.PropertyValue val = prop.getMutableValue();
	    if (!val.hasUserValue())
	      return;
	    OnestoreEntity.PropertyValue.UserValue userVal = val.getMutableUserValue();
	    userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail().hashCode()));
	  }
	 
	// private void validateAndProcessEntityProto(OnestoreEntity.EntityProto
	// entity) {
	// for (OnestoreEntity.Property prop : entity.propertys()) {
	// validateAndProcessProperty(prop);
	// }
	// for (OnestoreEntity.Property prop : entity.rawPropertys())
	// validateAndProcessProperty(prop);
	// }

	// private void validateAndProcessProperty(OnestoreEntity.Property prop) {
	// if (RESERVED_NAME.matcher(prop.getName()).matches()) {
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
	// String
	// .format(
	// "'%s' matches the pattern for reserved property names and can therefore not be used.",
	// new Object[] { prop.getName() }));
	// }
	//
	// OnestoreEntity.PropertyValue val = prop.getMutableValue();
	// if (!(val.hasUserValue()))
	// return;
	// OnestoreEntity.PropertyValue.UserValue userVal = val
	// .getMutableUserValue();
	// userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail()
	// .hashCode()));
	// }

	public DatastorePb.DeleteResponse delete(LocalRpcService.Status status,
			DatastorePb.DeleteRequest request) {
		try {
			// this.globalLock.readLock().lock();
			DatastorePb.DeleteResponse localDeleteResponse = deleteImpl(status,
					request);

			return localDeleteResponse;
		} finally {
			// this.globalLock.readLock().unlock();
		}
	}

	public ApiBasePb.VoidProto addActions(LocalRpcService.Status status,
			TaskQueuePb.TaskQueueBulkAddRequest request) {
		try {
			// this.globalLock.readLock().lock();
			addActionsImpl(status, request);
		} finally {
			// this.globalLock.readLock().unlock();
		}
		return new ApiBasePb.VoidProto();
	}

	// private OnestoreEntity.Path getGroup(OnestoreEntity.Reference key) {
	// OnestoreEntity.Path path = key.getPath();
	// OnestoreEntity.Path group = new OnestoreEntity.Path();
	// group.addElement(path.getElement(0));
	// return group;
	// }

	public DatastorePb.DeleteResponse deleteImpl(LocalRpcService.Status status,
			DatastorePb.DeleteRequest request) {
		log(request, "delete request! ");

		/* modified */
		outputToSocket(request.getKey(0).getApp(), "Delete", request);
		/* modification end */

		// LiveTxn liveTxn = null;
		// for (OnestoreEntity.Reference key : request.keys()) {
		// String app = key.getApp();
		// OnestoreEntity.Path group = getGroup(key);
		// Profile profile = getOrCreateProfile(app);
		// if (request.hasTransaction()) {
		// if (liveTxn == null) {
		// liveTxn = profile.getTxn(request.getTransaction()
		// .getHandle());
		// }
		// synchronized (profile) {
		// Profile.EntityGroup eg = profile.getGroup(group);
		//
		// eg.addTransaction(liveTxn);
		// liveTxn.addDeletedEntity(key);
		// }
		//
		// }
		//
		// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
		// getLast(key
		// .getPath().elements());
		// String kind = lastPath.getType();
		// Map<String, Extent> extents = profile.getExtents();
		// Extent extent = extents.get(kind);
		// if (extent == null) {
		// continue;
		// }
		// synchronized (profile) {
		// Profile.EntityGroup eg = profile.getGroup(group);
		// if (extent.getEntities().containsKey(key)) {
		// eg.incrementVersion();
		// extent.getEntities().remove(key);
		// LocalFullTextIndex fullTextIndex = profile
		// .getFullTextIndex();
		// if (fullTextIndex != null) {
		// fullTextIndex.delete(key);
		// }
		// this.dirty = true;
		// }
		// }
		// }
		DeleteResponse a = new DatastorePb.DeleteResponse();
		log(a, "delete response! ");
		return a;
	}

	private void addActionsImpl(LocalRpcService.Status status,
			TaskQueuePb.TaskQueueBulkAddRequest request) {
		log(request, "add action!");
		System.out.println("calling addActionsImpl, not implemented!");

		// if (request.addRequestSize() == 0) {
		// return;
		// }
		//
		// List<TaskQueuePb.TaskQueueAddRequest> addRequests = new
		// ArrayList<TaskQueuePb.TaskQueueAddRequest>(
		// request.addRequestSize());
		//
		// for (TaskQueuePb.TaskQueueAddRequest addRequest :
		// request.addRequests()) {
		// addRequests.add(((TaskQueuePb.TaskQueueAddRequest) addRequest
		// .clone()).clearTransaction());
		// }
		//
		// Profile profile = (Profile) this.profiles
		// .get(((TaskQueuePb.TaskQueueAddRequest) request.addRequests()
		// .get(0)).getTransaction().getApp());
		// LiveTxn liveTxn = profile
		// .getTxn(((TaskQueuePb.TaskQueueAddRequest) request
		// .addRequests().get(0)).getTransaction().getHandle());
		// liveTxn.addActions(addRequests);
	}

	public DatastorePb.QueryResult runQuery(LocalRpcService.Status status,
			DatastorePb.Query query) {

		return runQuery_New(status, query);

		// final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new
		// LocalCompositeIndexManager.ValidatedQuery(
		// query);
		//
		// query = validatedQuery.getQuery();
		//
		// String app = query.getApp();
		// Profile profile = getOrCreateProfile(app);
		//
		// synchronized (profile) {
		// if (query.hasTransaction()) {
		// if (!(app.equals(query.getTransaction().getApp()))) {
		// throw new ApiProxy.ApplicationException(
		// DatastorePb.Error.ErrorCode.INTERNAL_ERROR
		// .getValue(), "Can't query app " + app
		// + "in a transaction on app "
		// + query.getTransaction().getApp());
		// }
		//
		// OnestoreEntity.Path groupPath = getGroup(query.getAncestor());
		// Profile.EntityGroup eg = profile.getGroup(groupPath);
		// LiveTxn liveTxn = profile.getTxn(query.getTransaction()
		// .getHandle());
		//
		// eg.addTransaction(liveTxn);
		// }
		// }
		//
		// LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
		// if ((query.hasSearchQuery()) && (fullTextIndex == null)) {
		// throw new ApiProxy.ApplicationException(
		// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
		// "full-text search unsupported");
		// }
		//
		// List<OnestoreEntity.EntityProto> queryEntities = null;
		//
		// Map<String, Extent> extents = profile.getExtents();
		// Extent extent = (Extent) extents.get(query.getKind());
		//
		// if (extent != null) {
		// synchronized (profile) {
		// if (!(query.hasSearchQuery())) {
		// queryEntities = new ArrayList<OnestoreEntity.EntityProto>(
		// extent.getEntities().values());
		// } else {
		// List<Reference> keys = fullTextIndex.search(
		// query.getKind(), query.getSearchQuery());
		// List<OnestoreEntity.EntityProto> entities = new
		// ArrayList<OnestoreEntity.EntityProto>(
		// keys.size());
		// for (OnestoreEntity.Reference key : keys) {
		// entities.add(extent.getEntities().get(key));
		// }
		// queryEntities = entities;
		// }
		// }
		// }
		//
		// if (queryEntities == null) {
		// queryEntities = Collections.emptyList();
		// }
		//
		// List<Predicate<EntityProto>> predicates = new
		// ArrayList<Predicate<OnestoreEntity.EntityProto>>();
		//
		// if (query.hasAncestor()) {
		// final List<Element> ancestorPath = query.getAncestor().getPath()
		// .elements();
		// predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
		// public boolean apply(OnestoreEntity.EntityProto entity) {
		// List<Element> path = entity.getKey().getPath().elements();
		// return ((path.size() >= ancestorPath.size()) && (path
		// .subList(0, ancestorPath.size())
		// .equals(ancestorPath)));
		// }
		//
		// });
		// }
		//
		// final boolean hasNamespace = query.hasNameSpace();
		// final String namespace = query.getNameSpace();
		// predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
		// public boolean apply(OnestoreEntity.EntityProto entity) {
		// OnestoreEntity.Reference ref = entity.getKey();
		//
		// if (hasNamespace) {
		// if ((!(ref.hasNameSpace()))
		// || (!(namespace.equals(ref.getNameSpace())))) {
		// return false;
		// }
		// } else if (ref.hasNameSpace()) {
		// return false;
		// }
		//
		// return true;
		// }
		//
		// });
		// final EntityProtoComparators.EntityProtoComparator entityComparator =
		// new EntityProtoComparators.EntityProtoComparator(
		// validatedQuery.getQuery().orders(), validatedQuery.getQuery()
		// .filters());
		//
		// predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
		// public boolean apply(OnestoreEntity.EntityProto entity) {
		// return entityComparator.matches(entity);
		// }
		//
		// });
		// Iterators.removeIf(queryEntities.iterator(),
		// Predicates.not(Predicates
		// .and((Iterable) predicates)));
		//
		// Collections.sort(queryEntities, entityComparator);
		//
		// long cursor = this.queryId.getAndIncrement();
		// LiveQuery liveQuery = new LiveQuery(queryEntities, query,
		// entityComparator, this.clock);
		//
		// int offset = query.getOffset();
		// if (query.hasCompiledCursor()) {
		// offset += getQueryOffsetFromCursor(query.getCompiledCursor(),
		// liveQuery, entityComparator);
		// }
		//
		// int limit = (query.hasLimit()) ? query.getLimit() : queryEntities
		// .size();
		// liveQuery.offsetAndLimit(offset, limit);
		//
		// profile.addQuery(cursor, liveQuery);
		//
		// AccessController.doPrivileged(new PrivilegedAction<Object>() {
		// public Object run() {
		// LocalCompositeIndexManager.getInstance().processQuery(
		// validatedQuery.getQuery());
		// return null;
		// }
		// });
		// int count = 0;
		// if (query.hasCount())
		// count = query.getCount();
		// else if (query.hasLimit())
		// count = query.getLimit();
		// else {
		// count = 20;
		// }
		//
		// DatastorePb.NextRequest nextReq = new DatastorePb.NextRequest();
		// nextReq.setCompile(query.isCompile());
		// nextReq.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
		// nextReq.setCount(count);
		// DatastorePb.QueryResult result = next(status, nextReq);
		// if (query.isCompile()) {
		// result.setCompiledQuery(liveQuery.compileQuery());
		// }
		// log(((DatastorePb.QueryResult) (DatastorePb.QueryResult) result),
		// "query result! ");
		//
		// return ((DatastorePb.QueryResult) (DatastorePb.QueryResult) result);
	}

	private QueryResult runQuery_New(Status status, Query query) {
		log(query, "querying! ");

		DatastorePb.QueryResult queryResult = new DatastorePb.QueryResult();
		String appID = query.getApp();
		queryResult.parseFrom(this.outputToSocket(appID, "RunQuery", query));

		// not sure about this...
		long cursor = this.queryId.getAndIncrement();

		// System.out.println("the current cursor is: "+ cursor);
		int count = 0;
		if (query.hasCount())
			count = query.getCount();
		else if (query.hasLimit())
			count = query.getLimit();
		else {
			count = 20;
		}

		int end = Math.min(count, queryResult.resultSize());
		List<EntityProto> subList = queryResult.results().subList(0, end);
		List<EntityProto> nextResults = new ArrayList<EntityProto>(subList);

		DatastorePb.QueryResult final_oresult = new DatastorePb.QueryResult();

		for (Object proto : nextResults) {
			if (!(nextResults instanceof OnestoreEntity.EntityProto)) {

			} else {

			}
			final_oresult.addResult((OnestoreEntity.EntityProto) proto);
		}

		final_oresult.getMutableCursor().setCursor(cursor);
		final_oresult.setKeysOnly(query.isKeysOnly());
		final_oresult.setMoreResults((queryResult.results().size() - end) > 0);

		log(final_oresult, "query result!");
		return final_oresult;
	}

	// static int getQueryOffsetFromCursor(
	// DatastorePb.CompiledCursor compiledCursor, LiveQuery liveQuery,
	// Comparator<OnestoreEntity.EntityProto> sortComparator) {
	// if (compiledCursor.positionSize() == 0) {
	// return 0;
	// }
	//
	// DatastorePb.CompiledCursor.Position position = compiledCursor
	// .getPosition(0);
	// if (!(position.hasStartKey())) {
	// return 0;
	// }
	// OnestoreEntity.EntityProto cursorEntity = liveQuery
	// .decompilePosition(position);
	//
	// int loc = Collections.binarySearch(liveQuery.entitiesRemaining(),
	// cursorEntity, sortComparator);
	// if (loc < 0) {
	// return (-(loc + 1));
	// }
	// return ((position.isStartInclusive()) ? loc : loc + 1);
	// }

	// private static <T> T safeGetFromExpiringMap(Map<Long, T> map, long key) {
	// T value = map.get(Long.valueOf(key));
	// if (value == null) {
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.INTERNAL_ERROR.getValue(),
	// String.format("handle %s not found", new Object[] { Long
	// .valueOf(key) }));
	// }
	//
	// return value;
	// }

	public DatastorePb.QueryResult next(LocalRpcService.Status status,
			DatastorePb.NextRequest request) {
		log(request, "next request! ");

		DatastorePb.QueryResult result = new DatastorePb.QueryResult();

		/* modified */
		result.parseFrom(outputToSocket("sudoId_for_next", "Next", request));

		/* modification end */

		// Profile profile = (Profile) this.profiles.get(request.getCursor()
		// .getApp());
		// LiveQuery liveQuery =
		// profile.getQuery(request.getCursor().getCursor());
		//
		// int count = (request.hasCount()) ? request.getCount() : 20;
		// int end = Math.min(1000, count);
		//
		// for (OnestoreEntity.EntityProto proto : liveQuery.nextResults(end)) {
		// result.addResult(proto);
		// }
		// result.setCursor(request.getCursor());
		// result.setMoreResults(liveQuery.entitiesRemaining().size() > 0);
		// result.setKeysOnly(liveQuery.isKeysOnly());
		//
		// if (request.isCompile()) {
		// result.getMutableCompiledCursor().addPosition(
		// liveQuery.compilePosition());
		// }
		log(result, "log next result!");
		return result;
	}

	public ApiBasePb.Integer64Proto count(LocalRpcService.Status status,
			DatastorePb.Query request) {
		log(request, "count request!");
		System.out.println("calling count! Not implmeneted!");
		ApiBasePb.Integer64Proto results = new ApiBasePb.Integer64Proto();

		// LocalRpcService.Status queryStatus = new LocalRpcService.Status();
		// DatastorePb.QueryResult queryResult = runQuery(queryStatus, request);
		// long cursor = queryResult.getCursor().getCursor();
		//
		// Profile profile = (Profile) this.profiles.get(request.getApp());
		// int sizeRemaining =
		// profile.getQuery(cursor).entitiesRemaining().size();
		//
		// profile.removeQuery(cursor);
		// ApiBasePb.Integer64Proto results = new ApiBasePb.Integer64Proto();
		// results.setValue(sizeRemaining + queryResult.resultSize());
		return results;
	}

	public ApiBasePb.VoidProto deleteCursor(LocalRpcService.Status status,
			DatastorePb.Cursor request) {
		log(request, "deleteCursor!");
		System.out.println("calling delete cursor! Not implemented!");
		// Profile profile = (Profile) this.profiles.get(request.getApp());
		// profile.removeQuery(request.getCursor());
		return new ApiBasePb.VoidProto();
	}

//	public DatastorePb.QueryExplanation explain(LocalRpcService.Status status,
//			DatastorePb.Query req) {
//		log(req, "explain!");
//		throw new UnsupportedOperationException("Not yet implemented.");
//	}

	public DatastorePb.Transaction beginTransaction(
			LocalRpcService.Status status,
			DatastorePb.BeginTransactionRequest req) {
		log(req, "begin Transaction!");
		// Profile profile = getOrCreateProfile(req.getApp());
		// DatastorePb.Transaction txn = new DatastorePb.Transaction().setApp(
		// req.getApp()).setHandle(
		// this.transactionHandleProvider.getAndIncrement());
		//
		// profile.addTxn(txn.getHandle(), new LiveTxn(this.clock));
		// return txn;
		return new DatastorePb.Transaction();
	}

	public DatastorePb.CommitResponse commit(LocalRpcService.Status status,
			final DatastorePb.Transaction req) {

		log(req, "commit!");
		System.out.println("calling commit! Not implemented!");

		// final Profile profile = (Profile) this.profiles.get(req.getApp());
		//
		// Runnable runnable = new Runnable() {
		// public void run() {
		// LocalDatastoreService.LiveTxn liveTxn = profile.removeTxn(req
		// .getHandle());
		// if (liveTxn.isDirty()) {
		// try {
		// // LocalDatastoreService.this.globalLock.readLock().lock();
		// LocalDatastoreService.this.commitImpl(liveTxn, profile);
		// } finally {
		// // LocalDatastoreService.this.globalLock.readLock()
		// // .unlock();
		// }
		//
		// }
		//
		// for (TaskQueuePb.TaskQueueAddRequest action : liveTxn
		// .getActions())
		// try {
		// ApiProxy.makeSyncCall("taskqueue", "Add", action
		// .toByteArray());
		// } catch (ApiProxy.ApplicationException e) {
		// LocalDatastoreService.logger.log(Level.WARNING,
		// "Transactional task: " + action
		// + " has been dropped.", e);
		// }
		// }
		// };
		// synchronized (profile) {
		// runnable.run();
		// }
		return new DatastorePb.CommitResponse();
	}

	// private void commitImpl(LiveTxn liveTxn, Profile profile) {
	// Profile.EntityGroup eg = liveTxn.getEntityGroup();
	//
	// liveTxn.checkEntityGroupVersion();
	// eg.incrementVersion();
	// LocalFullTextIndex fullTextIndex = profile.getFullTextIndex();
	// for (OnestoreEntity.EntityProto entity : liveTxn.getWrittenEntities()) {
	// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
	// getLast(entity
	// .getKey().getPath().elements());
	// String kind = lastPath.getType();
	// Extent extent = getOrCreateExtent(profile, kind);
	// extent.getEntities().put(entity.getKey(), entity);
	// if (fullTextIndex != null) {
	// fullTextIndex.write(entity);
	// }
	// }
	// for (OnestoreEntity.Reference key : liveTxn.getDeletedKeys()) {
	// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
	// getLast(key
	// .getPath().elements());
	// String kind = lastPath.getType();
	// Map<String, Extent> extents = profile.getExtents();
	// Extent extent = (Extent) extents.get(kind);
	// if (extent != null) {
	// extent.getEntities().remove(key);
	// }
	// if (fullTextIndex != null) {
	// fullTextIndex.delete(key);
	// }
	//
	// }
	//
	// this.dirty = true;
	// }

	public ApiBasePb.VoidProto rollback(LocalRpcService.Status status,
			DatastorePb.Transaction req) {
		log(req, "rollback!");
		System.out.println("callling rollback! Not implemented!");
		// final Profile profile = (Profile) this.profiles.get(req.getApp());
		// final long handle = req.getHandle();
		//
		// Runnable runnable = new Runnable() {
		// public void run() {
		// profile.removeTxn(handle);
		// }
		// };
		// synchronized (profile) {
		// runnable.run();
		// }
		return new ApiBasePb.VoidProto();
	}

	public DatastorePb.Schema getSchema(LocalRpcService.Status status,
			DatastorePb.GetSchemaRequest req) {
		log(req, "get schema!");
		System.out.println("callling get schema! Not implemented!");

		// if ((req.hasStartKind()) && (req.hasEndKind())) {
		// Preconditions.checkArgument(req.getStartKind().compareTo(
		// req.getEndKind()) <= 0, "start_kind must be <= end_kind");
		// }
		//
		// DatastorePb.Schema schema = new DatastorePb.Schema();
		// Profile profile = getOrCreateProfile(req.getApp());
		// Map<String, Extent> extents = profile.getExtents();
		// OnestoreEntity.EntityProto allPropsProto;
		// Map<String, OnestoreEntity.Property> allProps;
		// synchronized (extents) {
		// for (Map.Entry<String, Extent> entry : extents.entrySet()) {
		// String kind = (String) entry.getKey();
		// if ((req.hasStartKind())
		// && (kind.compareTo(req.getStartKind()) < 0))
		// continue;
		// if ((req.hasEndKind())
		// && (kind.compareTo(req.getEndKind()) > 0)) {
		// continue;
		// }
		// if (((Extent) entry.getValue()).getEntities().isEmpty()) {
		// continue;
		// }
		//
		// allPropsProto = new OnestoreEntity.EntityProto();
		// schema.addKind(allPropsProto);
		// OnestoreEntity.Path path = new OnestoreEntity.Path();
		// path.addElement().setType(kind);
		// allPropsProto.setKey(new OnestoreEntity.Reference().setApp(
		// req.getApp()).setPath(path));
		//
		// allPropsProto.getMutableEntityGroup();
		//
		// if (req.isProperties()) {
		// allProps = new HashMap<String, OnestoreEntity.Property>();
		// for (OnestoreEntity.EntityProto entity : ((Extent) entry
		// .getValue()).getEntities().values()) {
		// for (OnestoreEntity.Property prop : entity.propertys()) {
		// OnestoreEntity.Property schemaProp = (OnestoreEntity.Property)
		// allProps
		// .get(prop.getName());
		// if (schemaProp == null) {
		// schemaProp = allPropsProto.addProperty()
		// .setName(prop.getName()).setMultiple(
		// false);
		//
		// allProps.put(prop.getName(), schemaProp);
		// }
		//
		// PropertyType type = PropertyType.getType(prop
		// .getValue());
		// schemaProp.getMutableValue().mergeFrom(
		// type.placeholderValue);
		// }
		// }
		// }
		// }
		// }
		//
		// schema.setMoreResults(false);
		// return schema;
		return null;
	}

	public ApiBasePb.Integer64Proto createIndex(LocalRpcService.Status status,
			OnestoreEntity.CompositeIndex req) {
		log(req, "creat index");
		throw new UnsupportedOperationException("Not yet implemented.");
	}

	public ApiBasePb.VoidProto updateIndex(LocalRpcService.Status status,
			OnestoreEntity.CompositeIndex req) {
		log(req, "update index");
		throw new UnsupportedOperationException("Not yet implemented.");
	}

	public DatastorePb.CompositeIndices getIndices(
			LocalRpcService.Status status, ApiBasePb.StringProto req) {
		log(req, "get index");
		throw new UnsupportedOperationException("Not yet implemented.");

	}

	public ApiBasePb.VoidProto deleteIndex(LocalRpcService.Status status,
			OnestoreEntity.CompositeIndex req) {
		throw new UnsupportedOperationException("Not yet implemented.");
	}

	public DatastorePb.AllocateIdsResponse allocateIds(
			LocalRpcService.Status status, DatastorePb.AllocateIdsRequest req) {
		try {
			// this.globalLock.readLock().lock();
			DatastorePb.AllocateIdsResponse localAllocateIdsResponse = allocateIdsImpl(req);

			return localAllocateIdsResponse;
		} finally {
			// this.globalLock.readLock().unlock();
		}
	}

	private DatastorePb.AllocateIdsResponse allocateIdsImpl(
			DatastorePb.AllocateIdsRequest req) {
		log(req, "allocate id!");
		System.out.println("callling allocating id! Not implemented!");
		// if (req.getSize() > 1000000000L) {
		// throw new ApiProxy.ApplicationException(
		// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
		// "cannot get more than 1000000000 keys in a single call");
		// }
		//
		// long start = this.entityId.getAndAdd(req.getSize());
		// return new DatastorePb.AllocateIdsResponse().setStart(start).setEnd(
		// start + req.getSize() - 1L);
		return null;
	}

	// private Profile getOrCreateProfile(String app) {
	// synchronized (this.profiles) {
	// Preconditions.checkArgument((app != null) && (app.length() > 0));
	// Profile profile = (Profile) this.profiles.get(app);
	// if (profile == null) {
	// profile = new Profile();
	// this.profiles.put(app, profile);
	// }
	// return profile;
	// }
	// }

	// private Extent getOrCreateExtent(Profile profile, String kind) {
	// Map<String, Extent> extents = profile.getExtents();
	// synchronized (extents) {
	// Extent e = (Extent) extents.get(kind);
	// if (e == null) {
	// e = new Extent();
	// extents.put(kind, e);
	// }
	// return e;
	// }
	// }

	// private void load() {
	// File backingStoreFile = new File(this.backingStore);
	// String path = backingStoreFile.getAbsolutePath();
	// if (!(backingStoreFile.exists())) {
	// logger.log(Level.INFO, "The backing store, " + path
	// + ", does not exist. " + "It will be created.");
	//
	// return;
	// }
	// try {
	// long start = this.clock.getCurrentTime();
	// ObjectInputStream objectIn = new ObjectInputStream(
	// new BufferedInputStream(new FileInputStream(
	// this.backingStore)));
	//
	// this.entityId.set(objectIn.readLong());
	//
	// Map<String, Profile> profilesOnDisk = (Map<String, Profile>) objectIn
	// .readObject();
	// this.profiles = profilesOnDisk;
	//
	// objectIn.close();
	// long end = this.clock.getCurrentTime();
	//
	// logger.log(Level.INFO, "Time to load datastore: " + (end - start)
	// + " ms");
	// } catch (FileNotFoundException e) {
	// logger.log(Level.SEVERE, "Failed to find the backing store, "
	// + path);
	// } catch (IOException e) {
	// logger.log(Level.INFO, "Failed to load from the backing store, "
	// + path, e);
	// } catch (ClassNotFoundException e) {
	// logger.log(Level.INFO, "Failed to load from the backing store, "
	// + path, e);
	// }
	// }

	// private static <T> T getLast(List<T> list) {
	// return list.get(list.size() - 1);
	// }

	// static void pruneHasCreationTimeMap(long now, int maxLifetimeMs,
	// Map<Long, ? extends HasCreationTime> hasCreationTimeMap) {
	// long deadline = now - maxLifetimeMs;
	// Iterator queryIt = hasCreationTimeMap.entrySet().iterator();
	// while (queryIt.hasNext()) {
	// Map.Entry entry = (Map.Entry) queryIt.next();
	// HasCreationTime query = (HasCreationTime) entry.getValue();
	// if (query.getCreationTime() < deadline)
	// queryIt.remove();
	// }
	// }

	// void removeStaleQueriesNow() {
	// this.removeStaleQueriesTask.run();
	// }

	// void removeStaleTxnsNow() {
	// this.removeStaleTransactionsTask.run();
	// }

	// private class PersistDatastore implements Runnable {
	// public void run() {
	// try {
	// LocalDatastoreService.this.globalLock.writeLock().lock();
	// privilegedPersist();
	// } catch (IOException e) {
	// LocalDatastoreService.logger.log(Level.SEVERE,
	// "Unable to save the datastore", e);
	// } finally {
	// LocalDatastoreService.this.globalLock.writeLock().unlock();
	// }
	// }
	//
	// private void privilegedPersist() throws IOException {
	// try {
	// AccessController
	// .doPrivileged(new PrivilegedExceptionAction<Object>() {
	// public Object run() throws IOException {
	// LocalDatastoreService.PersistDatastore.this
	// .persist();
	// return null;
	// }
	// });
	// } catch (PrivilegedActionException e) {
	// Throwable t = e.getCause();
	// if (t instanceof IOException) {
	// throw ((IOException) t);
	// }
	// throw new RuntimeException(t);
	// }
	// }
	//
	// private void persist() throws IOException {
	// if (!(LocalDatastoreService.this.dirty)) {
	// return;
	// }
	//
	// long start = LocalDatastoreService.this.clock.getCurrentTime();
	// ObjectOutputStream objectOut = new ObjectOutputStream(
	// new BufferedOutputStream(new FileOutputStream(
	// LocalDatastoreService.this.backingStore)));
	//
	// objectOut.writeLong(LocalDatastoreService.this.entityId.get());
	// objectOut.writeObject(LocalDatastoreService.this.profiles);
	//
	// objectOut.close();
	// dirty = false;
	// long end = LocalDatastoreService.this.clock.getCurrentTime();
	//
	// LocalDatastoreService.logger.log(Level.INFO,
	// "Time to persist datastore: " + (end - start) + " ms");
	// }
	// }

	// private class RemoveStaleTransactions implements Runnable {
	// public void run() {
	// for (LocalDatastoreService.Profile profile :
	// LocalDatastoreService.this.profiles
	// .values())
	// synchronized (profile) {
	// LocalDatastoreService
	// .pruneHasCreationTimeMap(
	// LocalDatastoreService.this.clock
	// .getCurrentTime(),
	// LocalDatastoreService.this.maxTransactionLifetimeMs,
	// profile.getTxns());
	// }
	// }
	// }

	// private class RemoveStaleQueries implements Runnable {
	// public void run() {
	// for (LocalDatastoreService.Profile profile :
	// LocalDatastoreService.this.profiles
	// .values())
	// synchronized (profile) {
	// LocalDatastoreService.pruneHasCreationTimeMap(
	// LocalDatastoreService.this.clock.getCurrentTime(),
	// LocalDatastoreService.this.maxQueryLifetimeMs,
	// profile.getQueries());
	// }
	// }
	// }

	// static class LiveTxn extends LocalDatastoreService.HasCreationTime {
	// private LocalDatastoreService.Profile.EntityGroup entityGroup;
	// private Long entityGroupVersion;
	// private final Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto>
	// written = new HashMap<OnestoreEntity.Reference,
	// OnestoreEntity.EntityProto>();
	// private final Set<OnestoreEntity.Reference> deleted = new
	// HashSet<OnestoreEntity.Reference>();
	// private final List<TaskQueuePb.TaskQueueAddRequest> actions = new
	// ArrayList<TaskQueuePb.TaskQueueAddRequest>();
	//
	// public LiveTxn(Clock clock) {
	// super(clock.getCurrentTime());
	// }
	//
	// public synchronized void setEntityGroup(
	// LocalDatastoreService.Profile.EntityGroup newEntityGroup) {
	// if (newEntityGroup == null) {
	// throw new NullPointerException("entityGroup cannot be null");
	// }
	//
	// if (this.entityGroupVersion == null) {
	// this.entityGroupVersion = Long.valueOf(newEntityGroup
	// .getVersion());
	// this.entityGroup = newEntityGroup;
	// }
	//
	// if (!(newEntityGroup.equals(this.entityGroup)))
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
	// "can't operate on multiple entity groups in a single transaction. found both "
	// + this.entityGroup + " and " + newEntityGroup);
	// }
	//
	// public synchronized LocalDatastoreService.Profile.EntityGroup
	// getEntityGroup() {
	// return this.entityGroup;
	// }
	//
	// public synchronized void checkEntityGroupVersion() {
	// if (!(this.entityGroupVersion.equals(Long.valueOf(this.entityGroup
	// .getVersion()))))
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.CONCURRENT_TRANSACTION
	// .getValue(),
	// "too much contention on these datastore entities. please try again.");
	// }
	//
	// public synchronized Long getEntityGroupVersion() {
	// return this.entityGroupVersion;
	// }
	//
	// public synchronized void addWrittenEntity(
	// OnestoreEntity.EntityProto entity) {
	// OnestoreEntity.Reference key = entity.getKey();
	// this.written.put(key, entity);
	//
	// this.deleted.remove(key);
	// }
	//
	// public synchronized void addDeletedEntity(OnestoreEntity.Reference key) {
	// this.deleted.add(key);
	//
	// this.written.remove(key);
	// }
	//
	// public synchronized void addActions(
	// Collection<TaskQueuePb.TaskQueueAddRequest> newActions) {
	// if (this.actions.size() + newActions.size() > 5L) {
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
	// "Too many messages, maximum allowed: 5");
	// }
	//
	// this.actions.addAll(newActions);
	// }
	//
	// public synchronized Collection<OnestoreEntity.EntityProto>
	// getWrittenEntities() {
	// return new ArrayList<OnestoreEntity.EntityProto>(this.written
	// .values());
	// }
	//
	// public synchronized Collection<OnestoreEntity.Reference> getDeletedKeys()
	// {
	// return new ArrayList<OnestoreEntity.Reference>(this.deleted);
	// }
	//
	// public synchronized Collection<TaskQueuePb.TaskQueueAddRequest>
	// getActions() {
	// return new ArrayList<TaskQueuePb.TaskQueueAddRequest>(this.actions);
	// }
	//
	// public synchronized boolean isDirty() {
	// return (this.written.size() + this.deleted.size() > 0);
	// }
	//
	// public synchronized void close() {
	// if (this.entityGroup != null)
	// this.entityGroup.removeTransaction(this);
	// }
	// }

	// static class LiveQuery extends LocalDatastoreService.HasCreationTime {
	// private final Set<String> orderProperties;
	// private final DatastorePb.Query query;
	// private List<OnestoreEntity.EntityProto> entities;
	// private OnestoreEntity.EntityProto lastResult = null;
	//
	// public LiveQuery(List<OnestoreEntity.EntityProto> entities,
	// DatastorePb.Query query,
	// EntityProtoComparators.EntityProtoComparator entityComparator,
	// Clock clock) {
	// super(clock.getCurrentTime());
	//
	// this.orderProperties = new HashSet<String>();
	// for (DatastorePb.Query.Order order : entityComparator
	// .getAdjustedOrders()) {
	// this.orderProperties.add(order.getProperty());
	// }
	//
	// if (entities == null) {
	// throw new NullPointerException("entities cannot be null");
	// }
	// this.query = query;
	// this.entities = entities;
	// }
	//
	// public List<OnestoreEntity.EntityProto> entitiesRemaining() {
	// return this.entities;
	// }
	//
	// public List<OnestoreEntity.EntityProto> nextResults(int end) {
	// List<OnestoreEntity.EntityProto> subList = this.entities.subList(0,
	// Math.min(end, this.entities.size()));
	//
	// if (subList.size() > 0) {
	// this.lastResult = ((OnestoreEntity.EntityProto) subList
	// .get(subList.size() - 1));
	// }
	// List<OnestoreEntity.EntityProto> result;
	// if (this.query.isKeysOnly()) {
	// result = new ArrayList<OnestoreEntity.EntityProto>();
	// for (OnestoreEntity.EntityProto entity : subList) {
	// result.add(((OnestoreEntity.EntityProto) entity.clone())
	// .clearOwner().clearProperty().clearRawProperty());
	// }
	// } else {
	// result = new ArrayList<OnestoreEntity.EntityProto>(subList);
	// }
	// subList.clear();
	//
	// return result;
	// }
	//
	// public void offsetAndLimit(int offset, int limit) {
	// int fromIndex = Math.min(offset, this.entities.size());
	// int toIndex = Math.min(fromIndex + limit, this.entities.size());
	//
	// if (fromIndex > 0) {
	// this.lastResult = ((OnestoreEntity.EntityProto) this.entities
	// .get(fromIndex - 1));
	// }
	//
	// if ((fromIndex != 0) || (toIndex != this.entities.size()))
	// this.entities = new ArrayList<OnestoreEntity.EntityProto>(
	// this.entities.subList(fromIndex, toIndex));
	// }
	//
	// public boolean isKeysOnly() {
	// return this.query.isKeysOnly();
	// }
	//
	// public OnestoreEntity.EntityProto decompilePosition(
	// DatastorePb.CompiledCursor.Position position) {
	// OnestoreEntity.EntityProto result = new OnestoreEntity.EntityProto();
	// result.mergeFrom(position.getStartKeyAsBytes());
	//
	// DatastorePb.Query relevantInfo = new DatastorePb.Query();
	// relevantInfo.mergeFrom(result.getKey().getPath().getElement(0)
	// .getTypeAsBytes());
	// if (!(validateQuery(relevantInfo))) {
	// throw new ApiProxy.ApplicationException(
	// DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
	// "Cursor does not match query.");
	// }
	//
	// result.getKey().getPath().removeElement(0);
	// return result;
	// }
	//
	// private boolean validateQuery(DatastorePb.Query relevantInfo) {
	// if (!(relevantInfo.filters().equals(this.query.filters()))) {
	// return false;
	// }
	//
	// if (!(relevantInfo.orders().equals(this.query.orders()))) {
	// return false;
	// }
	//
	// if (relevantInfo.hasAncestor()) {
	// if ((!(this.query.hasAncestor()))
	// || (!(relevantInfo.getAncestor().equals(this.query
	// .getAncestor()))))
	// return false;
	// } else if (this.query.hasAncestor()) {
	// return false;
	// }
	//
	// if (relevantInfo.hasKind()) {
	// if ((!(this.query.hasKind()))
	// || (!(relevantInfo.getKind().equals(this.query
	// .getKind()))))
	// return false;
	// } else if (this.query.hasKind()) {
	// return false;
	// }
	//
	// if (relevantInfo.hasNameSpace()) {
	// if ((!(this.query.hasNameSpace()))
	// || (!(relevantInfo.getNameSpace().equals(this.query
	// .getNameSpace()))))
	// return false;
	// } else if (this.query.hasNameSpace()) {
	// return false;
	// }
	//
	// if (relevantInfo.hasSearchQuery())
	// if ((!(this.query.hasSearchQuery()))
	// || (!(relevantInfo.getSearchQuery().equals(this.query
	// .getSearchQuery())))) {
	// return false;
	// } else if (this.query.hasSearchQuery()) {
	// return false;
	// }
	//
	// return true;
	// }
	//
	// public DatastorePb.CompiledCursor.Position compilePosition() {
	// DatastorePb.CompiledCursor.Position position = new
	// DatastorePb.CompiledCursor.Position();
	//
	// DatastorePb.Query relevantInfo = (DatastorePb.Query) this.query
	// .clone();
	//
	// relevantInfo.clearApp().clearCompile().clearCompiledCursor()
	// .clearCompositeIndex().clearCount().clearDistinct()
	// .clearFailoverMs().clearHint().clearKeysOnly().clearLimit()
	// .clearOffset().clearTransaction();
	//
	// if (this.lastResult != null) {
	// OnestoreEntity.EntityProto savedEntity = new
	// OnestoreEntity.EntityProto();
	//
	// savedEntity.setKey((OnestoreEntity.Reference) this.lastResult
	// .getKey().clone());
	//
	// savedEntity.getKey().getPath().insertElement(
	// 0,
	// new OnestoreEntity.Path.Element()
	// .setTypeAsBytes(relevantInfo.toByteArray()));
	//
	// for (OnestoreEntity.Property prop : this.lastResult.propertys()) {
	// if (this.orderProperties.contains(prop.getName())) {
	// savedEntity.addProperty((OnestoreEntity.Property) prop
	// .clone());
	// }
	// }
	//
	// position.setStartKeyAsBytes(savedEntity.toByteArray());
	//
	// position.setStartInclusive(false);
	// }
	//
	// return position;
	// }
	//
	// public DatastorePb.CompiledQuery compileQuery() {
	// DatastorePb.CompiledQuery result = new DatastorePb.CompiledQuery();
	// DatastorePb.CompiledQuery.PrimaryScan scan = result
	// .getMutablePrimaryScan();
	//
	// scan.setIndexNameAsBytes(this.query.toByteArray());
	//
	// return result;
	// }
	// }

	// static abstract class HasCreationTime {
	// private final long creationTime;
	//
	// HasCreationTime(long creationTime) {
	// this.creationTime = creationTime;
	// }
	//
	// long getCreationTime() {
	// return this.creationTime;
	// }
	// }

	// private static class Extent implements Serializable {
	// /**
	// *
	// */
	// private static final long serialVersionUID = 1L;
	// private Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto>
	// entities;
	//
	// private Extent() {
	// this.entities = new LinkedHashMap<OnestoreEntity.Reference,
	// OnestoreEntity.EntityProto>();
	// }
	//
	// public Map<OnestoreEntity.Reference, OnestoreEntity.EntityProto>
	// getEntities() {
	// return this.entities;
	// }
	// }

	// private static class Profile implements Serializable {
	// /**
	// *
	// */
	// private static final long serialVersionUID = 1L;
	// private final Map<String, LocalDatastoreService.Extent> extents =
	// Collections
	// .synchronizedMap(new HashMap<String, LocalDatastoreService.Extent>());
	// private transient Map<OnestoreEntity.Path, EntityGroup> groups;
	// private transient Map<Long, LocalDatastoreService.LiveQuery> queries;
	// private transient Map<Long, LocalDatastoreService.LiveTxn> txns;
	// private final LocalFullTextIndex fullTextIndex;
	//
	// public Profile() {
	// this.fullTextIndex = createFullTextIndex();
	// }
	//
	// private LocalFullTextIndex createFullTextIndex() {
	// Class<LocalFullTextIndex> indexClass = getFullTextIndexClass();
	//
	// if (indexClass == null) {
	// return null;
	// }
	// try {
	// return ((LocalFullTextIndex) indexClass.newInstance());
	// } catch (InstantiationException e) {
	// throw new RuntimeException(e);
	// } catch (IllegalAccessException e) {
	// throw new RuntimeException(e);
	// }
	// }
	//
	// private Class<LocalFullTextIndex> getFullTextIndexClass() {
	// try {
	// return (Class<LocalFullTextIndex>) Class
	// .forName("com.google.appengine.api.datastore.dev.LuceneFullTextIndex");
	// } catch (ClassNotFoundException e) {
	// return null;
	// } catch (NoClassDefFoundError e) {
	// }
	// return null;
	// }
	//
	// public Map<String, LocalDatastoreService.Extent> getExtents() {
	// return this.extents;
	// }
	//
	// public synchronized EntityGroup getGroup(OnestoreEntity.Path path) {
	// if (this.groups == null) {
	// this.groups = new HashMap<OnestoreEntity.Path, EntityGroup>();
	// }
	// EntityGroup group = (EntityGroup) this.groups.get(path);
	// if (group == null) {
	// group = new EntityGroup(path);
	// this.groups.put(path, group);
	// }
	// return group;
	// }
	//
	// public synchronized LocalDatastoreService.LiveQuery getQuery(long cursor)
	// {
	// return ((LocalDatastoreService.LiveQuery) LocalDatastoreService
	// .safeGetFromExpiringMap(getQueries(), cursor));
	// }
	//
	// public synchronized void addQuery(long cursor,
	// LocalDatastoreService.LiveQuery query) {
	// getQueries().put(Long.valueOf(cursor), query);
	// }
	//
	// private synchronized LocalDatastoreService.LiveQuery removeQuery(
	// long cursor) {
	// LocalDatastoreService.LiveQuery query = getQuery(cursor);
	// this.queries.remove(Long.valueOf(cursor));
	// return query;
	// }
	//
	// private synchronized Map<Long, LocalDatastoreService.LiveQuery>
	// getQueries() {
	// if (this.queries == null) {
	// this.queries = new HashMap<Long, LocalDatastoreService.LiveQuery>();
	// }
	// return this.queries;
	// }
	//
	// public synchronized LocalDatastoreService.LiveTxn getTxn(long handle) {
	// return ((LocalDatastoreService.LiveTxn) LocalDatastoreService
	// .safeGetFromExpiringMap(getTxns(), handle));
	// }
	//
	// public LocalFullTextIndex getFullTextIndex() {
	// return this.fullTextIndex;
	// }
	//
	// public synchronized void addTxn(long handle,
	// LocalDatastoreService.LiveTxn txn) {
	// getTxns().put(Long.valueOf(handle), txn);
	// }
	//
	// private synchronized LocalDatastoreService.LiveTxn removeTxn(long handle)
	// {
	// LocalDatastoreService.LiveTxn txn = getTxn(handle);
	// txn.close();
	// this.txns.remove(Long.valueOf(handle));
	// return txn;
	// }
	//
	// private synchronized Map<Long, LocalDatastoreService.LiveTxn> getTxns() {
	// if (this.txns == null) {
	// this.txns = new HashMap<Long, LocalDatastoreService.LiveTxn>();
	// }
	// return this.txns;
	// }
	//
	// private class EntityGroup {
	// private final OnestoreEntity.Path path;
	// private final AtomicLong version = new AtomicLong();
	// private final WeakHashMap<LocalDatastoreService.LiveTxn,
	// LocalDatastoreService.Profile> snapshots = new
	// WeakHashMap<LocalDatastoreService.LiveTxn,
	// LocalDatastoreService.Profile>();
	//
	// private EntityGroup(OnestoreEntity.Path paramPath) {
	// this.path = paramPath;
	// }
	//
	// public long getVersion() {
	// return this.version.get();
	// }
	//
	// public void incrementVersion() {
	// long oldVersion = this.version.getAndIncrement();
	// LocalDatastoreService.Profile snapshot = null;
	// for (LocalDatastoreService.LiveTxn txn : this.snapshots
	// .keySet())
	// if (txn.getEntityGroupVersion().longValue() == oldVersion) {
	// if (snapshot == null) {
	// snapshot = takeSnapshot();
	// }
	// this.snapshots.put(txn, snapshot);
	// }
	// }
	//
	// public OnestoreEntity.EntityProto get(
	// LocalDatastoreService.LiveTxn liveTxn,
	// OnestoreEntity.Reference key) {
	// LocalDatastoreService.Profile profile = getSnapshot(liveTxn);
	// Map<String, Extent> extents = profile.getExtents();
	// OnestoreEntity.Path.Element lastPath = (OnestoreEntity.Path.Element)
	// LocalDatastoreService
	// .getLast(key.getPath().elements());
	// LocalDatastoreService.Extent extent = (LocalDatastoreService.Extent)
	// extents
	// .get(lastPath.getType());
	// if (extent != null) {
	// Map<Reference, EntityProto> entities = extent.getEntities();
	// return ((OnestoreEntity.EntityProto) entities.get(key));
	// }
	// return null;
	// }
	//
	// public void addTransaction(LocalDatastoreService.LiveTxn txn) {
	// txn.setEntityGroup(this);
	// if (!(this.snapshots.containsKey(txn)))
	// this.snapshots.put(txn, null);
	// }
	//
	// public void removeTransaction(LocalDatastoreService.LiveTxn txn) {
	// this.snapshots.remove(txn);
	// }
	//
	// private LocalDatastoreService.Profile getSnapshot(
	// LocalDatastoreService.LiveTxn txn) {
	// if (txn == null) {
	// return LocalDatastoreService.Profile.this;
	// }
	// LocalDatastoreService.Profile snapshot = (LocalDatastoreService.Profile)
	// this.snapshots
	// .get(txn);
	// if (snapshot == null) {
	// return LocalDatastoreService.Profile.this;
	// }
	// return snapshot;
	// }
	//
	// private LocalDatastoreService.Profile takeSnapshot() {
	// try {
	// ByteArrayOutputStream bos = new ByteArrayOutputStream();
	// ObjectOutputStream oos = new ObjectOutputStream(bos);
	// oos.writeObject(LocalDatastoreService.Profile.this);
	// oos.close();
	// ByteArrayInputStream bis = new ByteArrayInputStream(bos
	// .toByteArray());
	// ObjectInputStream ois = new ObjectInputStream(bis);
	// return ((LocalDatastoreService.Profile) ois.readObject());
	// } catch (IOException ex) {
	// throw new RuntimeException(
	// "Unable to take transaction snapshot.", ex);
	// } catch (ClassNotFoundException ex) {
	// throw new RuntimeException(
	// "Unable to take transaction snapshot.", ex);
	// }
	// }
	//
	// public String toString() {
	// return this.path.toString();
	// }
	// }
	// }

	// //////////////////////////////////////////////////////////////
	public byte[] outputToSocket(String appId, String method,
			ProtocolMessage msg) {

		return proxy.doPost(appId, method, msg);
		// System.out.println("sending "+ method+ " complete");
	}

	private void log(ProtocolMessage msg, String des) {
		System.out.println(des + " " + msg.toFlatString());
	}
	// //////////////////////////////////////////////////////////////
}