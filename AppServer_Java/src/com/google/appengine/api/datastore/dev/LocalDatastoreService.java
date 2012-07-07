package com.google.appengine.api.datastore.dev;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;

import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.EntityProtoComparators;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.base.Predicate;
import com.google.appengine.repackaged.com.google.common.base.Predicates;
import com.google.appengine.repackaged.com.google.common.collect.Iterators;
import com.google.appengine.repackaged.com.google.common.collect.Lists;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LatencyPercentiles;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiBasePb.Integer64Proto;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.api.DatastorePb.CommitResponse;
import com.google.apphosting.api.DatastorePb.QueryResult;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;
import com.google.storage.onestore.v3.OnestoreEntity.Path.Element;
import com.google.storage.onestore.v3.OnestoreEntity.Property;

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService extends AbstractLocalRpcService {
    private static final Logger logger = Logger
            .getLogger(LocalDatastoreService.class.getName());
    static final int DEFAULT_BATCH_SIZE = 20;
    static final int MAXIMUM_RESULTS_SIZE = 300;
    public static final String PACKAGE = "datastore_v3";
    public static final String MAX_QUERY_LIFETIME_PROPERTY = "datastore.max_query_lifetime";
    // private static final int DEFAULT_MAX_QUERY_LIFETIME = 30000;
    public static final String MAX_TRANSACTION_LIFETIME_PROPERTY = "datastore.max_txn_lifetime";
    // private static final int DEFAULT_MAX_TRANSACTION_LIFETIME = 300000;
    public static final String STORE_DELAY_PROPERTY = "datastore.store_delay";
    static final int DEFAULT_STORE_DELAY_MS = 30000;
    public static final int MAX_EG_PER_TXN = 5;
    public static final String BACKING_STORE_PROPERTY = "datastore.backing_store";
    public static final String NO_INDEX_AUTO_GEN_PROP = "datastore.no_index_auto_gen";
    public static final String NO_STORAGE_PROPERTY = "datastore.no_storage";
    public static final String HIGH_REP_JOB_POLICY_CLASS_PROPERTY = "datastore.high_replication_job_policy_class";
    private static final Pattern RESERVED_NAME = Pattern.compile("^__.*__$");

    // add for AppScale
    private Map<Long, List<TaskQueueAddRequest>> tx_actions = new HashMap<Long, List<TaskQueueAddRequest>>();
    private Map<Long, LiveQuery> live_queries = new HashMap<Long, LiveQuery>();
    private HTTPClientDatastoreProxy proxy;

    private static final Set<String> RESERVED_NAME_WHITELIST = new HashSet<String>(
            Arrays.asList(new String[] { "__BlobUploadSession__",
                    "__BlobInfo__", "__ProspectiveSearchSubscriptions__",
                    "__BlobFileIndex__", "__GsFileInfo__" }));
    static final String ENTITY_GROUP_MESSAGE = "can't operate on multiple entity groups in a single transaction.";
    static final String TOO_MANY_ENTITY_GROUP_MESSAGE = "operating on too many entity groups in a single transaction.";
    static final String MULTI_EG_TXN_NOT_ALLOWED = "transactions on multiple entity groups only allowed in High Replication applications";
    static final String CONTENTION_MESSAGE = "too much contention on these datastore entities. please try again.";
    static final String TRANSACTION_CLOSED = "transaction closed";
    static final String TRANSACTION_NOT_FOUND = "transaction has expired or is invalid";
    static final String QUERY_NOT_FOUND = "query has expired or is invalid. Please restart it with the last cursor to read more results.";
    private final AtomicLong entityId = new AtomicLong(1L);

    private final AtomicLong queryId = new AtomicLong(0L);
    private Clock clock;
    private static final long MAX_BATCH_GET_KEYS = 1000000000L;
//    private static final long MAX_ACTIONS_PER_TXN = 5L;
    private final ScheduledThreadPoolExecutor scheduler = new ScheduledThreadPoolExecutor(
            2, new ThreadFactory() {
                public Thread newThread(Runnable r) {
                    Thread thread = new Thread(r);
                    thread.setDaemon(true);
                    return thread;
                }
            });

    private final AtomicInteger transactionHandleProvider = new AtomicInteger(0);
    private Thread shutdownHook;
    //TODO deal with highRepJobPolicy
    @SuppressWarnings("unused")
    private HighRepJobPolicy highRepJobPolicy;
    private boolean isHighRep;
    private LocalDatastoreCostAnalysis costAnalysis;
    private static Map<String, SpecialProperty> specialPropertyMap = Collections
            .singletonMap("__scatter__", SpecialProperty.SCATTER);

    public void clearQueryHistory() {
        LocalCompositeIndexManager.getInstance().clearQueryHistory();
    }

    public LocalDatastoreService() {
    }

    public void init(LocalServiceContext context, Map<String, String> properties) {
        this.clock = context.getClock();

        LocalCompositeIndexManager.getInstance().setAppDir(
                context.getLocalServerEnvironment().getAppDir());

        LocalCompositeIndexManager.getInstance().setClock(this.clock);

        String noIndexAutoGenProp = (String) properties
                .get("datastore.no_index_auto_gen");
        if (noIndexAutoGenProp != null) {
            LocalCompositeIndexManager.getInstance().setNoIndexAutoGen(
                    Boolean.valueOf(noIndexAutoGenProp).booleanValue());
        }

        initHighRepJobPolicy(properties);

        this.costAnalysis = new LocalDatastoreCostAnalysis(
                LocalCompositeIndexManager.getInstance());
        logger.log(Level.INFO, "Datastore initialized");
        ResourceLoader res = ResourceLoader.getResouceLoader();
        String host = res.getPbServerIp();
        int port = res.getPbServerPort();
        boolean isSSL = res.getDatastoreSeurityMode();
        proxy = new HTTPClientDatastoreProxy(host, port, isSSL);

        logger.info(String.format(
                "Local Datastore initialized: \n\tType: %s\n\tStorage: %s",
                new Object[] {
                        isHighRep() ? "High Replication" : "Master/Slave",
                        "data store" }));
    }

    boolean isHighRep() {
        return this.isHighRep;
    }

    @SuppressWarnings({ "unchecked", "rawtypes" })
    private void initHighRepJobPolicy(Map<String, String> properties) {
        String highRepJobPolicyStr = (String) properties
                .get("datastore.high_replication_job_policy_class");
        if (highRepJobPolicyStr == null) {
            DefaultHighRepJobPolicy defaultPolicy = new DefaultHighRepJobPolicy(
                    properties);
            this.isHighRep = (defaultPolicy.unappliedJobCutoff > 0);
            this.highRepJobPolicy = defaultPolicy;
        } else {
            this.isHighRep = true;
            try {
                Class highRepJobPolicyCls = Class.forName(highRepJobPolicyStr);
                Constructor ctor = highRepJobPolicyCls
                        .getDeclaredConstructor(new Class[0]);
                ctor.setAccessible(true);
                this.highRepJobPolicy = ((HighRepJobPolicy) ctor
                        .newInstance(new Object[0]));
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

    public void start() {
        AccessController.doPrivileged(new PrivilegedAction<Object>() {
            public Object run() {
                startInternal();
                return null;
            }
        });
    }

    private void startInternal() {
        this.scheduler.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
        this.shutdownHook = new Thread() {
            public void run() {
                LocalDatastoreService.this.stop();
            }
        };
        Runtime.getRuntime().addShutdownHook(this.shutdownHook);
    }

    public void stop() {
        this.scheduler.shutdown();
        try {
            Runtime.getRuntime().removeShutdownHook(this.shutdownHook);
        } catch (IllegalStateException ex) {
        }
    }

    public String getPackage() {
        return "datastore_v3";
    }

    @LatencyPercentiles(latency50th = 10)
    public DatastorePb.GetResponse get(LocalRpcService.Status status,
            DatastorePb.GetRequest request) {
        DatastorePb.GetResponse response = new DatastorePb.GetResponse();
        // logger.log(Level.INFO, "Get Request: " + request.toFlatString());
        proxy.doPost(request.getKey(0).getApp(), "Get", request, response);
        if (response.entitySize() == 0)
            response.addEntity();
        // logger.log(Level.INFO, "Get Response: " + response.toFlatString());
        return response;
    }

    @LatencyPercentiles(latency50th = 30, dynamicAdjuster = WriteLatencyAdjuster.class)
    public DatastorePb.PutResponse put(LocalRpcService.Status status,
            DatastorePb.PutRequest request) {
        DatastorePb.PutResponse localPutResponse = putImpl(status, request);
        return localPutResponse;
    }

    private void processEntityForSpecialProperties(
            OnestoreEntity.EntityProto entity, boolean store) {
        for (Iterator<Property> iter = entity.propertyIterator(); iter
                .hasNext();) {
            if (getSpecialPropertyMap().containsKey(iter.next().getName())) {
                iter.remove();
            }
        }

        for (SpecialProperty specialProp : getSpecialPropertyMap().values())
            if (store ? specialProp.isStored() : specialProp.isVisible()) {
                OnestoreEntity.PropertyValue value = specialProp
                        .getValue(entity);
                if (value != null)
                    entity.addProperty(specialProp.getProperty(value));
            }
    }

    public DatastorePb.PutResponse putImpl(LocalRpcService.Status status,
            DatastorePb.PutRequest request) {
        DatastorePb.PutResponse response = new DatastorePb.PutResponse();
        if (request.entitySize() == 0) {
            return response;
        }

        String app = request.entitys().get(0).getKey().getApp();
        List<OnestoreEntity.EntityProto> clones = new ArrayList<OnestoreEntity.EntityProto>();
        for (OnestoreEntity.EntityProto entity : request.entitys()) {
            validateAndProcessEntityProto(entity);
            OnestoreEntity.EntityProto clone = entity.clone();
            clones.add(clone);
            Preconditions.checkArgument(clone.hasKey());
            OnestoreEntity.Reference key = clone.getKey();
            Preconditions.checkArgument(key.getPath().elementSize() > 0);
            clone.getMutableKey().setApp(app);
            OnestoreEntity.Path.Element lastPath = getLast(key.getPath()
                    .elements());

            if ((lastPath.getId() == 0L) && (!lastPath.hasName())) {
                lastPath.setId(this.entityId.getAndIncrement());
            }
            // TODO
            // special proeprties are not supported 
            // processEntityForSpecialProperties(clone, true);

            if (clone.getEntityGroup().elementSize() == 0) {
                OnestoreEntity.Path group = clone.getMutableEntityGroup();
                OnestoreEntity.Path.Element root = key.getPath().elements()
                        .get(0);
                OnestoreEntity.Path.Element pathElement = group.addElement();
                pathElement.setType(root.getType());
                if (root.hasName())
                    pathElement.setName(root.getName());
                else
                    pathElement.setId(root.getId());
            } else {
                Preconditions.checkState((clone.hasEntityGroup())
                        && (clone.getEntityGroup().elementSize() > 0));
            }
        }

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

    private void validatePathForPut(OnestoreEntity.Reference key) {
        OnestoreEntity.Path path = key.getPath();
        for (OnestoreEntity.Path.Element ele : path.elements()) {
            String type = ele.getType();
            if ((RESERVED_NAME.matcher(type).matches())
                    && (!RESERVED_NAME_WHITELIST.contains(type)))
                throw newError(DatastorePb.Error.ErrorCode.BAD_REQUEST,
                        String.format("illegal key.path.element.type: %s",
                                new Object[] { ele.getType() }));
        }
    }

    private void validateAndProcessProperty(OnestoreEntity.Property prop) {
        if (RESERVED_NAME.matcher(prop.getName()).matches()) {
            throw newError(DatastorePb.Error.ErrorCode.BAD_REQUEST,
                    String.format("illegal property.name: %s",
                            new Object[] { prop.getName() }));
        }

        OnestoreEntity.PropertyValue val = prop.getMutableValue();
        if (val.hasUserValue()) {
            OnestoreEntity.PropertyValue.UserValue userVal = val
                    .getMutableUserValue();
            userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail()
                    .hashCode()));
        }
    }

    @LatencyPercentiles(latency50th = 40, dynamicAdjuster = WriteLatencyAdjuster.class)
    public DatastorePb.DeleteResponse delete(LocalRpcService.Status status,
            DatastorePb.DeleteRequest request) {
        DatastorePb.DeleteResponse localDeleteResponse = deleteImpl(status,
                request);
        return localDeleteResponse;
    }

    @LatencyPercentiles(latency50th = 1)
    public ApiBasePb.VoidProto addActions(LocalRpcService.Status status,
            TaskQueuePb.TaskQueueBulkAddRequest request) {
        addActionsImpl(status, request);
        return new ApiBasePb.VoidProto();
    }

    public DatastorePb.DeleteResponse deleteImpl(LocalRpcService.Status status,
            DatastorePb.DeleteRequest request) {
        DatastorePb.DeleteResponse response = new DatastorePb.DeleteResponse();
        if (request.keySize() != 0) {
            proxy.doPost(request.getKey(0).getApp(), "Delete", request,
                    response);
        }
        return response;
    }

    private void addActionsImpl(LocalRpcService.Status status,
            TaskQueuePb.TaskQueueBulkAddRequest request) {
        if (request.addRequestSize() == 0) {
            return;
        }

        List<TaskQueueAddRequest> addRequests = new ArrayList<TaskQueueAddRequest>(
                request.addRequestSize());

        for (TaskQueueAddRequest addRequest : request.addRequests()) {
            addRequests.add(addRequest.clone().clearTransaction());
        }

        // cache locally
        // TODO clear upon partial commit to avoid memory leak?
        tx_actions.put((request.addRequests().get(0)).getTransaction()
                .getHandle(), addRequests);
    }

    // TODO full text index?
    @LatencyPercentiles(latency50th = 20)
    public DatastorePb.QueryResult runQuery(LocalRpcService.Status status,
            DatastorePb.Query query) {
        final LocalCompositeIndexManager.ValidatedQuery validatedQuery = new LocalCompositeIndexManager.ValidatedQuery(
                query);

        query = validatedQuery.getQuery();
        DatastorePb.QueryResult queryResult = new DatastorePb.QueryResult();
        String appID = query.getApp();
        proxy.doPost(appID, "RunQuery", query, queryResult);
        // deal with results, filter order etc...
        List<EntityProto> queryEntities = new ArrayList<EntityProto>(
                queryResult.results());

        List<Predicate<OnestoreEntity.EntityProto>> predicates = new ArrayList<Predicate<OnestoreEntity.EntityProto>>();

        if (query.hasAncestor()) {
            final List<Element> ancestorPath = query.getAncestor().getPath().elements();
            predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
                public boolean apply(OnestoreEntity.EntityProto entity) {
                    List<Element> path = entity.getKey().getPath().elements();
                    return (path.size() >= ancestorPath.size()) && (path.subList(0, ancestorPath.size()).equals(ancestorPath));
                }
            });
        }

        final boolean hasNamespace = query.hasNameSpace();
        final String namespace = query.getNameSpace();
        predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
            public boolean apply(OnestoreEntity.EntityProto entity) {
                OnestoreEntity.Reference ref = entity.getKey();
                if (hasNamespace) {
                    if ((!ref.hasNameSpace()) || (!namespace.equals(ref.getNameSpace()))) {
                        return false;
                    }
                } else if (ref.hasNameSpace()) {
                    return false;
                }
                return true;
            }
        });
        final EntityProtoComparators.EntityProtoComparator entityComparator = new EntityProtoComparators.EntityProtoComparator(
                validatedQuery.getQuery().orders(), validatedQuery.getQuery().filters());

        predicates.add(new Predicate<OnestoreEntity.EntityProto>() {
            public boolean apply(OnestoreEntity.EntityProto entity) {
                return entityComparator.matches(entity);
            }
        });
        // filter
        Iterators.removeIf(queryEntities.iterator(),Predicates.not(Predicates.and(predicates)));
        // sort
        Collections.sort(queryEntities, entityComparator);

        LiveQuery liveQuery = new LiveQuery(queryEntities, query, entityComparator, this.clock);

        // indexing is done by back end
/*        AccessController.doPrivileged(new PrivilegedAction<Object>() {
            public Object run() {
                LocalCompositeIndexManager.getInstance().processQuery(validatedQuery.getQuery());
                return null;
            }
        });
*/        
        int count;
        if (query.hasCount()) {
            count = query.getCount();
        } else {
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
            live_queries.put(cursor, liveQuery);
            result.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
        }
/*
        for (OnestoreEntity.Index index : LocalCompositeIndexManager
                .getInstance().queryIndexList(query)) {
            result.addIndex(wrapIndexInCompositeIndex(app, index));
        }
*/
        return result;

    }


    @LatencyPercentiles(latency50th = 50)
    public DatastorePb.QueryResult next(LocalRpcService.Status status,DatastorePb.NextRequest request) {
        LiveQuery liveQuery = this.live_queries.get(request.getCursor().getCursor());

        int count = request.hasCount() ? request.getCount() : 20;
        QueryResult result = nextImpl(liveQuery, request.getOffset(), count, request.isCompile());

        if (result.isMoreResults())
            result.setCursor(request.getCursor());
        else {
            live_queries.remove(request.getCursor().getCursor());
        }
        return result;
    }

    private DatastorePb.QueryResult nextImpl(LiveQuery liveQuery, int offset,
            int count, boolean compile) {
        DatastorePb.QueryResult result = new DatastorePb.QueryResult();
        if (offset > 0) {
            result.setSkippedResults(liveQuery.offsetResults(offset));
        }

        if (offset == result.getSkippedResults()) {
            int end = Math.min(300, count);

            for (OnestoreEntity.EntityProto proto : liveQuery.nextResults(end)) {
                OnestoreEntity.EntityProto clone = proto.clone();
                // TODO
                // special properties are not supported 
                // processEntityForSpecialProperties(clone, false);
                result.addResult(clone);
            }
        }
        result.setMoreResults(liveQuery.entitiesRemaining().size() > 0);
        result.setKeysOnly(liveQuery.isKeysOnly());
        if (compile) {
            result.getMutableCompiledCursor().addPosition(liveQuery.compilePosition());
        }
        return result;
    }

    public ApiBasePb.VoidProto deleteCursor(LocalRpcService.Status status,
            DatastorePb.Cursor request) {
        this.live_queries.remove(request.getCursor());
        return new ApiBasePb.VoidProto();
    }

    @LatencyPercentiles(latency50th = 1)
    public DatastorePb.Transaction beginTransaction(LocalRpcService.Status status, DatastorePb.BeginTransactionRequest req) {
        DatastorePb.Transaction txn = new DatastorePb.Transaction().setApp(
                req.getApp()).setHandle(
                this.transactionHandleProvider.getAndIncrement());
        if ((req.isAllowMultipleEg()) && (!isHighRep())) {
            throw newError(
                    DatastorePb.Error.ErrorCode.BAD_REQUEST,
                    "transactions on multiple entity groups only allowed in High Replication applications");
        }
        proxy.doPost(req.getApp(), "BeginTransaction", req, txn);
        return txn;
    }

    @LatencyPercentiles(latency50th = 20, dynamicAdjuster = WriteLatencyAdjuster.class)
    public DatastorePb.CommitResponse commit(LocalRpcService.Status status,
            DatastorePb.Transaction req) {
        CommitResponse response = new CommitResponse();
        proxy.doPost(req.getApp(), "Commit", req, response);
        List<TaskQueueAddRequest> actions = this.tx_actions.get(req.getHandle());
        if (actions != null) {
            for (TaskQueueAddRequest action : actions)
                try {
                    ApiProxy.makeSyncCall("taskqueue", "Add", action.toByteArray());
                } catch (ApplicationException e) {
                    LocalDatastoreService.logger.log(Level.WARNING, "Transactional task: " + action
                            + " has been dropped.", e);
                }
            this.tx_actions.remove(req.getHandle());
        }
        //logger.log(Level.INFO, "Commit Response: " + response.toFlatString());
        return response;
    }

    @LatencyPercentiles(latency50th = 1)
    public ApiBasePb.VoidProto rollback(LocalRpcService.Status status, DatastorePb.Transaction req) {
        // TODO req.setApp?
        //logger.log(Level.INFO, "Rollback Request: " + req.toFlatString());
        VoidProto response = new VoidProto();
        proxy.doPost(req.getApp(), "Rollback", req, response);
        //logger.log(Level.INFO, "Rollback Response: " + response.toFlatString());
        return response;
    }

    public ApiBasePb.Integer64Proto createIndex(LocalRpcService.Status status,
            OnestoreEntity.CompositeIndex req) {
        Integer64Proto response = new Integer64Proto();
        if (req.getId() != 0) {
            throw new IllegalArgumentException("New index id must be 0.");
        }
        proxy.doPost(req.getAppId(), "CreateIndex", req, response);
        //logger.log(Level.INFO, "createIndex response: " + response.toFlatString());
        return response;
        // throw new UnsupportedOperationException("Not yet implemented.");
    }

    public ApiBasePb.VoidProto updateIndex(LocalRpcService.Status status,
            OnestoreEntity.CompositeIndex req) {
        VoidProto response = new ApiBasePb.VoidProto();
        proxy.doPost(req.getAppId(), "UpdateIndex", req, response);
        return response;
    }

    public DatastorePb.CompositeIndices getIndices(
            LocalRpcService.Status status, ApiBasePb.StringProto req) {
        DatastorePb.CompositeIndices answer = new DatastorePb.CompositeIndices();
        proxy.doPost(req.getValue(), "GetIndices", req, answer);
        return answer;
    }

    public ApiBasePb.VoidProto deleteIndex(LocalRpcService.Status status,
            OnestoreEntity.CompositeIndex req) {
        VoidProto response = new VoidProto();
        proxy.doPost(req.getAppId(), "DeleteIndex", req, response);
        return response;
    }

    @LatencyPercentiles(latency50th = 1)
    public DatastorePb.AllocateIdsResponse allocateIds(LocalRpcService.Status status, DatastorePb.AllocateIdsRequest req) {
        return allocateIdsImpl(req);
    }

    private DatastorePb.AllocateIdsResponse allocateIdsImpl(DatastorePb.AllocateIdsRequest req) {
        if (req.hasSize() && req.getSize() > MAX_BATCH_GET_KEYS) {
            throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
                    "cannot get more than 1000000000 keys in a single call");
        }

        DatastorePb.AllocateIdsResponse response = new DatastorePb.AllocateIdsResponse();
        proxy.doPost("appId", "AllocateIds", req, response);
        return response;
    }

    private static <T> T getLast(List<T> list) {
        return list.get(list.size() - 1);
    }

    @SuppressWarnings("unchecked")
    static void pruneHasCreationTimeMap(long now, int maxLifetimeMs,
            Map<Long, ? extends HasCreationTime> hasCreationTimeMap) {
        long deadline = now - maxLifetimeMs;
        Iterator<?> queryIt = hasCreationTimeMap.entrySet().iterator();
        while (queryIt.hasNext()) {
            Map.Entry<Long, ? extends HasCreationTime> entry = (Entry<Long, ? extends HasCreationTime>) queryIt
                    .next();
            HasCreationTime query = entry.getValue();
            if (query.getCreationTime() < deadline)
                queryIt.remove();
        }
    }

    static Map<String, SpecialProperty> getSpecialPropertyMap() {
        return specialPropertyMap;
    }

    public Double getDefaultDeadline(boolean isOfflineRequest) {
        return Double.valueOf(30.0D);
    }

    public Double getMaximumDeadline(boolean isOfflineRequest) {
        return Double.valueOf(30.0D);
    }

    public CreationCostAnalysis getCreationCostAnalysis(Entity e) {
        return this.costAnalysis.getCreationCostAnalysis(e);
    }

    static ApiProxy.ApplicationException newError(
            DatastorePb.Error.ErrorCode error, String message) {
        return new ApiProxy.ApplicationException(error.getValue(), message);
    }

    static enum SpecialProperty {
        SCATTER(false, true);

        private final String name;
        private final boolean isVisible;
        private final boolean isStored;

        private SpecialProperty(boolean isVisible, boolean isStored) {
            this.name = ("__" + name().toLowerCase() + "__");
            this.isVisible = isVisible;
            this.isStored = isStored;
        }

        public final String getName() {
            return this.name;
        }

        public final boolean isVisible() {
            return this.isVisible;
        }

        final boolean isStored() {
            return this.isStored;
        }

        OnestoreEntity.PropertyValue getValue(OnestoreEntity.EntityProto entity) {
            throw new UnsupportedOperationException();
        }

        OnestoreEntity.Property getProperty(OnestoreEntity.PropertyValue value) {
            OnestoreEntity.Property processedProp = new OnestoreEntity.Property();
            processedProp.setName(getName());
            processedProp.setValue(value);
            processedProp.setMultiple(false);
            return processedProp;
        }
    }

    static class LiveQuery extends LocalDatastoreService.HasCreationTime {
        private final Set<String> orderProperties;
        private final DatastorePb.Query query;
        private List<OnestoreEntity.EntityProto> entities;
        private OnestoreEntity.EntityProto lastResult = null;

        public LiveQuery(List<OnestoreEntity.EntityProto> entities,
                DatastorePb.Query query,
                EntityProtoComparators.EntityProtoComparator entityComparator,
                Clock clock) {
            super(System.currentTimeMillis());
            if (entities == null) {
                throw new NullPointerException("entities cannot be null");
            }

            this.query = query;
            this.entities = entities;

            this.orderProperties = new HashSet<String>();
            for (DatastorePb.Query.Order order : entityComparator
                    .getAdjustedOrders()) {
                if (!"__key__".equals(order.getProperty())) {
                    this.orderProperties.add(order.getProperty());
                }
            }

            applyCursors(entityComparator);
            applyLimit();
            entities = Lists.newArrayList(entities);
        }

        private void applyCursors(
                EntityProtoComparators.EntityProtoComparator entityComparator) {
            DecompiledCursor startCursor = new DecompiledCursor(
                    this.query.getCompiledCursor());
            this.lastResult = startCursor.getCursorEntity();
            int endCursorPos = new DecompiledCursor(
                    this.query.getEndCompiledCursor()).getPosition(
                    entityComparator, this.entities.size());

            int startCursorPos = Math.min(endCursorPos,
                    startCursor.getPosition(entityComparator, 0));

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
            int realOffset = Math.min(Math.min(offset, this.entities.size()),
                    300);
            if (realOffset > 0) {
                this.lastResult = ((OnestoreEntity.EntityProto) this.entities
                        .get(realOffset - 1));
                this.entities = this.entities.subList(realOffset,
                        this.entities.size());
            }
            return realOffset;
        }

        public List<OnestoreEntity.EntityProto> nextResults(int end) {
            List<OnestoreEntity.EntityProto> subList = this.entities.subList(0,
                    Math.min(end, this.entities.size()));

            if (subList.size() > 0) {
                this.lastResult = subList.get(subList.size() - 1);
            }
            List<EntityProto> result;
            if (this.query.isKeysOnly()) {
                result = new ArrayList<EntityProto>();
                for (OnestoreEntity.EntityProto entity : subList) {
                    result.add(((OnestoreEntity.EntityProto) entity.clone())
                            .clearOwner().clearProperty().clearRawProperty());
                }
            } else {
                result = new ArrayList<EntityProto>(subList);
            }
            subList.clear();

            return result;
        }

        public void restrictRange(int fromIndex, int toIndex) {
            toIndex = Math.max(fromIndex, toIndex);

            if (fromIndex > 0) {
                this.lastResult = ((OnestoreEntity.EntityProto) this.entities
                        .get(fromIndex - 1));
            }

            if ((fromIndex != 0) || (toIndex != this.entities.size()))
                this.entities = new ArrayList<EntityProto>(
                        this.entities.subList(fromIndex, toIndex));
        }

        public boolean isKeysOnly() {
            return this.query.isKeysOnly();
        }

        public OnestoreEntity.EntityProto decompilePosition(
                DatastorePb.CompiledCursor.Position position) {
            OnestoreEntity.EntityProto result = new OnestoreEntity.EntityProto();
            if (position.hasKey()) {
                if ((this.query.hasKind())
                        && (!this.query.getKind()
                                .equals((getLast(position.getKey().getPath()
                                        .elements())).getType()))) {
                    throw LocalDatastoreService.newError(
                            DatastorePb.Error.ErrorCode.BAD_REQUEST,
                            "Cursor does not match query.");
                }
                result.setKey(position.getKey());
            }

            Set<String> remainingProperties = new HashSet<String>(
                    this.orderProperties);
            for (DatastorePb.CompiledCursor.PositionIndexValue prop : position
                    .indexValues()) {
                if (!this.orderProperties.contains(prop.getProperty())) {
                    throw LocalDatastoreService.newError(
                            DatastorePb.Error.ErrorCode.BAD_REQUEST,
                            "Cursor does not match query.");
                }
                remainingProperties.remove(prop.getProperty());
                result.addProperty().setName(prop.getProperty())
                        .setValue(prop.getValue());
            }

            if (!remainingProperties.isEmpty()) {
                throw LocalDatastoreService.newError(
                        DatastorePb.Error.ErrorCode.BAD_REQUEST,
                        "Cursor does not match query.");
            }
            return result;
        }

        public DatastorePb.CompiledCursor.Position compilePosition() {
            DatastorePb.CompiledCursor.Position position = new DatastorePb.CompiledCursor.Position();

            if (this.lastResult != null) {
                position.setKey(this.lastResult.getKey());

                for (OnestoreEntity.Property prop : this.lastResult.propertys()) {
                    if (this.orderProperties.contains(prop.getName())) {
                        position.addIndexValue().setProperty(prop.getName())
                                .setValue(prop.getValue());
                    }
                }

                position.setStartInclusive(false);
            }

            return position;
        }

        public DatastorePb.CompiledQuery compileQuery() {
            DatastorePb.CompiledQuery result = new DatastorePb.CompiledQuery();
            DatastorePb.CompiledQuery.PrimaryScan scan = result
                    .getMutablePrimaryScan();

            scan.setIndexNameAsBytes(this.query.toByteArray());

            return result;
        }

        class DecompiledCursor {
            final OnestoreEntity.EntityProto cursorEntity;
            final boolean inclusive;

            public DecompiledCursor(DatastorePb.CompiledCursor compiledCursor) {
                if ((compiledCursor == null)
                        || (compiledCursor.positionSize() == 0)) {
                    this.cursorEntity = null;
                    this.inclusive = false;
                    return;
                }

                DatastorePb.CompiledCursor.Position position = compiledCursor
                        .getPosition(0);
                if ((!position.hasStartKey()) && (!position.hasKey())
                        && (position.indexValueSize() <= 0)) {
                    this.cursorEntity = null;
                    this.inclusive = false;
                    return;
                }

                this.cursorEntity = LocalDatastoreService.LiveQuery.this
                        .decompilePosition(position);
                this.inclusive = position.isStartInclusive();
            }

            public int getPosition(
                    EntityProtoComparators.EntityProtoComparator entityComparator,
                    int defaultValue) {
                if (this.cursorEntity == null) {
                    return defaultValue;
                }

                int loc = Collections.binarySearch(
                        LocalDatastoreService.LiveQuery.this.entities,
                        this.cursorEntity, entityComparator);
                if (loc < 0) {
                    return -(loc + 1);
                }
                return this.inclusive ? loc : loc + 1;
            }

            public OnestoreEntity.EntityProto getCursorEntity() {
                return this.cursorEntity;
            }
        }
    }

    static class HasCreationTime {
        private final long creationTime;

        HasCreationTime(long creationTime) {
            this.creationTime = creationTime;
        }

        long getCreationTime() {
            return this.creationTime;
        }
    }
}