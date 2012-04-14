package com.google.appengine.api.datastore.dev;

import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Map.Entry;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;

import com.google.appengine.api.datastore.EntityProtoComparators;
import com.google.appengine.api.datastore.EntityProtoComparators.EntityProtoComparator;
import com.google.appengine.api.datastore.dev.LocalCompositeIndexManager.ValidatedQuery;
import com.google.appengine.api.taskqueue.TaskQueuePb;
import com.google.appengine.api.taskqueue.Transaction;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueAddRequest;
import com.google.appengine.api.taskqueue.TaskQueuePb.TaskQueueBulkAddRequest;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.base.Predicate;
import com.google.appengine.repackaged.com.google.common.base.Predicates;
import com.google.appengine.repackaged.com.google.common.collect.Iterators;
import com.google.appengine.repackaged.com.google.common.collect.Lists;
import com.google.appengine.tools.development.Clock;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiProxy;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.api.ApiBasePb.Integer64Proto;
import com.google.apphosting.api.ApiBasePb.StringProto;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import com.google.apphosting.api.DatastorePb.AllocateIdsRequest;
import com.google.apphosting.api.DatastorePb.AllocateIdsResponse;
import com.google.apphosting.api.DatastorePb.BeginTransactionRequest;
import com.google.apphosting.api.DatastorePb.CommitResponse;
import com.google.apphosting.api.DatastorePb.CompiledCursor;
import com.google.apphosting.api.DatastorePb.CompiledQuery;
import com.google.apphosting.api.DatastorePb.CompositeIndices;
import com.google.apphosting.api.DatastorePb.Cursor;
import com.google.apphosting.api.DatastorePb.DeleteRequest;
import com.google.apphosting.api.DatastorePb.DeleteResponse;
import com.google.apphosting.api.DatastorePb.GetRequest;
import com.google.apphosting.api.DatastorePb.GetResponse;
import com.google.apphosting.api.DatastorePb.GetSchemaRequest;
import com.google.apphosting.api.DatastorePb.NextRequest;
import com.google.apphosting.api.DatastorePb.PutRequest;
import com.google.apphosting.api.DatastorePb.PutResponse;
import com.google.apphosting.api.DatastorePb.Query;
import com.google.apphosting.api.DatastorePb.QueryResult;
import com.google.apphosting.api.DatastorePb.Schema;
import com.google.apphosting.api.DatastorePb.CompiledCursor.Position;
import com.google.apphosting.api.DatastorePb.GetResponse.Entity;
import com.google.storage.onestore.v3.OnestoreEntity.CompositeIndex;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;
import com.google.storage.onestore.v3.OnestoreEntity.Path;
import com.google.storage.onestore.v3.OnestoreEntity.Property;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue;
import com.google.storage.onestore.v3.OnestoreEntity.Reference;
import com.google.storage.onestore.v3.OnestoreEntity.Path.Element;

@ServiceProvider(LocalRpcService.class)
public final class LocalDatastoreService implements LocalRpcService {
    private static final Logger logger = Logger.getLogger(LocalDatastoreService.class.getName());
    static final int DEFAULT_BATCH_SIZE = 20;
    static final int MAXIMUM_RESULTS_SIZE = 1000;
    public static final String PACKAGE = "datastore_v3";
    public static final String MAX_QUERY_LIFETIME_PROPERTY = "datastore.max_query_lifetime";
    private static final int DEFAULT_MAX_QUERY_LIFETIME = 30000;
    public static final String MAX_TRANSACTION_LIFETIME_PROPERTY = "datastore.max_txn_lifetime";
    // private static final int DEFAULT_MAX_TRANSACTION_LIFETIME = 300000;
    public static final String STORE_DELAY_PROPERTY = "datastore.store_delay";
    static final int DEFAULT_STORE_DELAY_MS = 30000;
    public static final String BACKING_STORE_PROPERTY = "datastore.backing_store";
    public static final String NO_INDEX_AUTO_GEN_PROP = "datastore.no_index_auto_gen";
    public static final String NO_STORAGE_PROPERTY = "datastore.no_storage";
    public static final String HIGH_REP_JOB_POLICY_CLASS_PROPERTY = "datastore.high_replication_job_policy_class";
    private static final Pattern RESERVED_NAME = Pattern.compile("^__.*__$");
    static final String ENTITY_GROUP_MESSAGE = "can't operate on multiple entity groups in a single transaction.";
    static final String CONTENTION_MESSAGE = "too much contention on these datastore entities. please try again.";
    static final String HANDLE_NOT_FOUND_MESSAGE_FORMAT = "handle %s not found";
    static final String GET_SCHEMA_START_PAST_END = "start_kind must be <= end_kind";
    private final AtomicLong entityId = new AtomicLong(1L);
    private final AtomicLong queryId = new AtomicLong(0L);
    private Clock clock;
    private static final long MAX_BATCH_GET_KEYS = 1000000000L;
    private final RemoveStaleQueries removeStaleQueriesTask = new RemoveStaleQueries();
    // private static final long MAX_ACTIONS_PER_TXN = 5L;
    private int maxQueryLifetimeMs;
    // private int maxTransactionLifetimeMs;
    private final ScheduledThreadPoolExecutor scheduler = new ScheduledThreadPoolExecutor(2);

    private Map<Long, List<TaskQueueAddRequest>> tx_actions = new HashMap<Long, List<TaskQueueAddRequest>>();
    private Map<Long, LiveQuery> live_queries = new HashMap<Long, LiveQuery>();

    private Thread shutdownHook;
    // private static Map<String, SpecialProperty> specialPropertyMap =
    // Collections.singletonMap("__scatter__",
    // SpecialProperty.SCATTER);
    private HTTPClientDatastoreProxy proxy;

    public LocalDatastoreService() {
    }

    public void init(LocalServiceContext context, Map<String, String> properties) {
        logger.log(Level.INFO, "Datastore initialized");
        ResourceLoader res = ResourceLoader.getResouceLoader();
        String host = res.getPbServerIp();
        int port = res.getPbServerPort();
        boolean isSSL = res.getDatastoreSeurityMode();
        //logger.log(Level.INFO, "port: " + port);
        //logger.log(Level.INFO, "host: " + host);
        //logger.log(Level.INFO, "isSSL: " + isSSL);
        proxy = new HTTPClientDatastoreProxy(host, port, isSSL);
        this.maxQueryLifetimeMs = DEFAULT_MAX_QUERY_LIFETIME;
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
        this.scheduler.scheduleWithFixedDelay(this.removeStaleQueriesTask, this.maxQueryLifetimeMs * 5,
                this.maxQueryLifetimeMs * 5, TimeUnit.MILLISECONDS);
        this.shutdownHook = new Thread() {
            public void run() {
                //logger.log(Level.INFO, "datastore is shutting down");
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

    public GetResponse get(LocalRpcService.Status status, GetRequest request) {
        GetResponse response = new GetResponse();
        //logger.log(Level.INFO, "Get Request: " + request.toFlatString());
        proxy.doPost(request.getKey(0).getApp(), "Get", request, response);
        if (response.entitySize() == 0)
            response.addEntity(new Entity());
        //logger.log(Level.INFO, "Get Response: " + response.toFlatString());
        return response;
    }

    // TODO set trusted? and validateAppId?
    public PutResponse put(LocalRpcService.Status status, PutRequest request) {
        //logger.log(Level.INFO, "original Put Reqeust: " + request.toFlatString());
        PutResponse response = new PutResponse();
        if (request.entitySize() == 0) {
            return response;
        }
        String app = request.getEntity(0).getKey().getApp();
        //logger.log(Level.INFO, "first check");
        for (EntityProto entity : request.entitys()) {
            Reference key = entity.getKey();
            Iterator<Element> iter = key.getPath().elementIterator();
            /*
            while (iter.hasNext()) {
                Element s = iter.next();
                //logger.log(Level.INFO, "-----------------");
                //logger.log(Level.INFO, "ele: id: " + s.getId());
                //logger.log(Level.INFO, "ele: name: " + s.getName());
            } */
        }
        // check entities
        for (EntityProto entity : request.entitys()) {
            validateAndProcessEntityProto(entity);
            // EntityProto clone = entity.clone();
            Preconditions.checkArgument(entity.hasKey());
            Reference key = entity.getKey();
            Preconditions.checkArgument(key.getPath().elementSize() > 0);
            entity.getMutableKey().setApp(app);
            Element lastPath = getLast(key.getPath().elements());
            if ((lastPath.getId() == 0L) && (!lastPath.hasName())) {
                //logger.log(Level.INFO, "setting id for key: ");
                lastPath.setId(this.entityId.getAndIncrement());
            } 
            // special entities are not supported yet
            // processEntityForSpecialProperties(clone, false);

            if (entity.getEntityGroup().elementSize() == 0) {
                Path group = entity.getMutableEntityGroup();
                Element root = key.getPath().elements().get(0);
                Element pathElement = group.addElement();
                pathElement.setType(root.getType());
                if (root.hasName())
                    pathElement.setName(root.getName());
                else
                    pathElement.setId(root.getId());
            } else {
                Preconditions.checkState((entity.hasEntityGroup()) && (entity.getEntityGroup().elementSize() > 0));
            }
        }

        for (EntityProto entity : request.entitys()) {
            Reference key = entity.getKey();
            Iterator<Element> iter = key.getPath().elementIterator();
            /*while (iter.hasNext()) {
                Element s = iter.next();
                logger.log(Level.INFO, "-----------------");
                logger.log(Level.INFO, "ele has id? " + s.hasId());
                logger.log(Level.INFO, "ele has name? " + s.hasName());
                logger.log(Level.INFO, "ele: id: " + s.getId());
                logger.log(Level.INFO, "ele: name: " + s.getName());
            } */
        }
        //logger.log(Level.INFO, "modified Put Reqeust: " + request.toFlatString());
        proxy.doPost(app, "Put", request, response);
        //logger.log(Level.INFO, "Put Response: " + response.toFlatString());
        return response;
    }

    // private void processEntityForSpecialProperties(EntityProto entity,
    // boolean store) {
    // for (Iterator<Property> iter = entity.propertyIterator();
    // iter.hasNext();) {
    // if (getSpecialPropertyMap().containsKey((iter.next()).getName())) {
    // iter.remove();
    // }
    // }
    //
    // for (SpecialProperty specialProp : getSpecialPropertyMap().values())
    // if (store ? specialProp.isStored() : specialProp.isVisible()) {
    // PropertyValue value = specialProp.getValue(entity);
    // if (value != null)
    // entity.addProperty(specialProp.getProperty(value));
    // }
    // }

    private void validateAndProcessEntityProto(EntityProto entity) {
        for (Property prop : entity.propertys()) {
            validateAndProcessProperty(prop);
        }
        for (Property prop : entity.rawPropertys())
            validateAndProcessProperty(prop);
    }

    private void validateAndProcessProperty(Property prop) {
        if (RESERVED_NAME.matcher(prop.getName()).matches()) {
            throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(), String.format(
                    "'%s' matches the pattern for reserved property names and can therefore not be used.",
                    new Object[] { prop.getName() }));
        }

        PropertyValue val = prop.getMutableValue();
        if (val.hasUserValue()) {
            PropertyValue.UserValue userVal = val.getMutableUserValue();
            userVal.setObfuscatedGaiaid(Integer.toString(userVal.getEmail().hashCode()));
        }
    }

    public DeleteResponse delete(LocalRpcService.Status status, DeleteRequest request) {
        //logger.log(Level.INFO, "Delete Request: " + request.toFlatString());
        DatastorePb.DeleteResponse response = new DatastorePb.DeleteResponse();
        if (request.keySize() == 0) {
            return response;
        }
        proxy.doPost(request.getKey(0).getApp(), "Delete", request, response);
        //logger.log(Level.INFO, "Delete Response: " + response.toFlatString());
        return response;
    }

    public ApiBasePb.VoidProto addActions(LocalRpcService.Status status, TaskQueuePb.TaskQueueBulkAddRequest request) {
        addActionsImpl(status, request);
        return new ApiBasePb.VoidProto();
    }

    private void addActionsImpl(Status status, TaskQueueBulkAddRequest request) {
        //logger.log(Level.INFO, "Add Action Request: " + request.toFlatString());

        if (request.addRequestSize() == 0) {
            return;
        }

        List<TaskQueueAddRequest> addRequests = new ArrayList<TaskQueueAddRequest>(request.addRequestSize());

        for (TaskQueueAddRequest addRequest : request.addRequests()) {
            addRequests.add((addRequest.clone()).clearTransaction());
        }
        // cache locally
        tx_actions.put((request.addRequests().get(0)).getTransaction().getHandle(), addRequests);
        //logger.log(Level.INFO, "Add Action Response: void");
    }

    // TODO full text index?
    public DatastorePb.QueryResult runQuery(Status status, Query query) {
        //logger.log(Level.INFO, "Run Query Request: " + query.toFlatString());

        // prepare query
        final ValidatedQuery validatedQuery = new ValidatedQuery(query);
        query = validatedQuery.getQuery();

        DatastorePb.QueryResult queryResult = new DatastorePb.QueryResult();
        String appID = query.getApp();
        proxy.doPost(appID, "RunQuery", query, queryResult);
        // deal with results, filter order etc...

        List<EntityProto> queryEntities = new ArrayList<EntityProto>(queryResult.results());
        List<Predicate<EntityProto>> predicates = new ArrayList<Predicate<EntityProto>>();

        if (query.hasAncestor()) {
            final List<Element> ancestorPath = query.getAncestor().getPath().elements();
            predicates.add(new Predicate<EntityProto>() {
                public boolean apply(EntityProto entity) {
                    List<Element> path = entity.getKey().getPath().elements();
                    return (path.size() >= ancestorPath.size())
                            && (path.subList(0, ancestorPath.size()).equals(ancestorPath));
                }
            });
        }

        final boolean hasNamespace = query.hasNameSpace();
        final String namespace = query.getNameSpace();
        predicates.add(new Predicate<EntityProto>() {
            public boolean apply(EntityProto entity) {
                Reference ref = entity.getKey();
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
        final EntityProtoComparator entityComparator = new EntityProtoComparator(validatedQuery.getQuery().orders(),
                validatedQuery.getQuery().filters());
        predicates.add(new Predicate<EntityProto>() {
            public boolean apply(EntityProto entity) {
                return entityComparator.matches(entity);
            }
        });

        // filter
        Iterators.removeIf(queryEntities.iterator(), Predicates.not(Predicates.and(predicates)));
        // sort
        Collections.sort(queryEntities, entityComparator);

        LiveQuery liveQuery = new LiveQuery(queryEntities, query, entityComparator, this.clock);
        // indexing is done by back end
        // AccessController.doPrivileged(new PrivilegedAction<Object>() {
        // public Object run() {
        // LocalCompositeIndexManager.getInstance().processQuery(validatedQuery.getQuery());
        // return null;
        // }
        // });

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

        QueryResult result = nextImpl(liveQuery, query.getOffset(), count, query.isCompile());
        if (query.isCompile()) {
            result.setCompiledQuery(liveQuery.compileQuery());
        }
        if (result.isMoreResults()) {
            long cursor = this.queryId.getAndIncrement();
            live_queries.put(cursor, liveQuery);
            result.getMutableCursor().setApp(query.getApp()).setCursor(cursor);
        }

        //logger.log(Level.INFO, "Run Query Result: " + result.toFlatString());

        return result;
    }

    public QueryResult next(LocalRpcService.Status status, NextRequest request) {
        //logger.log(Level.INFO, "Next Request: " + request.toFlatString());

        LiveQuery liveQuery = this.live_queries.get(request.getCursor().getCursor());

        int count = request.hasCount() ? request.getCount() : 20;
        QueryResult result = nextImpl(liveQuery, request.getOffset(), count, request.isCompile());

        if (result.isMoreResults())
            result.setCursor(request.getCursor());
        else {
            live_queries.remove(request.getCursor().getCursor());
        }
        //logger.log(Level.INFO, "Next Response: " + result.toFlatString());

        return result;
    }

    private DatastorePb.QueryResult nextImpl(LiveQuery liveQuery, int offset, int count, boolean compile) {
        QueryResult result = new QueryResult();
        if (offset > 0) {
            result.setSkippedResults(liveQuery.offsetResults(offset));
        }

        if (offset == result.getSkippedResults()) {
            int end = Math.min(1000, count);
            for (EntityProto proto : liveQuery.nextResults(end)) {
                EntityProto clone = proto.clone();
                // special entity is not supported
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

    public Integer64Proto count(LocalRpcService.Status status, Query request) {
        //logger.log(Level.INFO, "Count Request: " + request.toFlatString());

        LocalRpcService.Status queryStatus = new LocalRpcService.Status();
        QueryResult queryResult = runQuery(queryStatus, request);
        long cursor = queryResult.getCursor().getCursor();
        int sizeRemaining = this.live_queries.get(cursor).entitiesRemaining().size();
        this.live_queries.remove(cursor);
        Integer64Proto results = new Integer64Proto();
        results.setValue(sizeRemaining + queryResult.resultSize());
        //logger.log(Level.INFO, "Count Response: " + results.toFlatString());

        return results;
    }

    public VoidProto deleteCursor(LocalRpcService.Status status, Cursor request) {
        //logger.log(Level.INFO, "Delete Cursor Request: " + request.toFlatString());
        this.live_queries.remove(request.getCursor());
        //logger.log(Level.INFO, "Delete Cursor Response: void");
        return new VoidProto();
    }

    public Transaction beginTransaction(LocalRpcService.Status status, BeginTransactionRequest req) {
        //logger.log(Level.INFO, "Begin Transaction Request: " + req.toFlatString());
        Transaction txn = new Transaction();
        proxy.doPost(req.getApp(), "BeginTransaction", req, txn);
        //logger.log(Level.INFO, "Begin Transaction Response: " + txn.toFlatString());
        return txn;
    }

    public CommitResponse commit(LocalRpcService.Status status, final Transaction req) {
        //logger.log(Level.INFO, "Commit Request: " + req.toFlatString());
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

    public VoidProto rollback(LocalRpcService.Status status, Transaction req) {
        // TODO req.setApp?
        //logger.log(Level.INFO, "Rollback Request: " + req.toFlatString());
        VoidProto response = new VoidProto();
        proxy.doPost(req.getApp(), "Rollback", req, response);
        //logger.log(Level.INFO, "Rollback Response: " + response.toFlatString());
        return response;
    }

    // TODO need support from back end
    public Schema getSchema(LocalRpcService.Status status, GetSchemaRequest req) {
        //logger.log(Level.INFO, "Calling getSchema, not implemented.");

        throw new UnsupportedOperationException("Not yet implemented.");
    }

    // TODO java sdk doesen't support this yet
    public Integer64Proto createIndex(LocalRpcService.Status status, CompositeIndex req) {
        //logger.log(Level.INFO, "createIndex request: " + req.toFlatString());

        Integer64Proto response = new Integer64Proto();
        if (req.getId() != 0) {
            throw new IllegalArgumentException("New index id must be 0.");
        }
        proxy.doPost(req.getAppId(), "CreateIndex", req, response);
        //logger.log(Level.INFO, "createIndex response: " + response.toFlatString());
        return response;

        // throw new UnsupportedOperationException("Not yet implemented.");
    }

    public VoidProto updateIndex(LocalRpcService.Status status, CompositeIndex req) {
        //logger.log(Level.INFO, "Calling updateIndex, not implemented.");
        throw new UnsupportedOperationException("Not yet implemented.");
    }

    public CompositeIndices getIndices(LocalRpcService.Status status, StringProto req) {
        //logger.log(Level.INFO, "Calling getIndices, not implemented.");
        throw new UnsupportedOperationException("Not yet implemented.");
    }

    public VoidProto deleteIndex(LocalRpcService.Status status, CompositeIndex req) {
        //logger.log(Level.INFO, "Calling deleteIndex, not implemented.");
        throw new UnsupportedOperationException("Not yet implemented.");
    }

    public AllocateIdsResponse allocateIds(LocalRpcService.Status status, AllocateIdsRequest req) {
        //logger.log(Level.INFO, "allocateId request: " + req.toFlatString());

        if (req.hasSize() && req.getSize() > MAX_BATCH_GET_KEYS) {
            throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
                    "cannot get more than 1000000000 keys in a single call");
        }

        DatastorePb.AllocateIdsResponse response = new DatastorePb.AllocateIdsResponse();
        proxy.doPost("appId", "AllocateIds", req, response);
        //logger.log(Level.INFO, "allocateId response: " + response.toFlatString());
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
            Map.Entry<Long, HasCreationTime> entry = (Entry<Long, HasCreationTime>) queryIt.next();
            HasCreationTime query = (HasCreationTime) entry.getValue();
            if (query.getCreationTime() < deadline)
                queryIt.remove();
        }
    }

    static class LiveQuery extends LocalDatastoreService.HasCreationTime {
        private final Set<String> orderProperties;
        private final DatastorePb.Query query;
        private List<EntityProto> entities;
        private EntityProto lastResult = null;

        public LiveQuery(List<EntityProto> entities, DatastorePb.Query query, EntityProtoComparator entityComparator,
                Clock clock) {
            super(System.currentTimeMillis());
            if (entities == null) {
                throw new NullPointerException("entities cannot be null");
            }

            this.query = query;
            this.entities = entities;

            this.orderProperties = new HashSet<String>();
            for (Query.Order order : entityComparator.getAdjustedOrders()) {
                this.orderProperties.add(order.getProperty());
            }

            applyCursors(entityComparator);
            applyLimit();
            entities = Lists.newArrayList(entities);
        }

        private void applyCursors(EntityProtoComparator entityComparator) {
            DecompiledCursor startCursor = new DecompiledCursor(this.query.getCompiledCursor());
            this.lastResult = startCursor.getCursorEntity();
            int endCursorPos = new DecompiledCursor(this.query.getEndCompiledCursor()).getPosition(entityComparator,
                    this.entities.size());

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

        public List<EntityProto> entitiesRemaining() {
            return this.entities;
        }

        public int offsetResults(int offset) {
            int real_offset = Math.min(Math.min(offset, this.entities.size()), 1000);
            if (real_offset > 0) {
                this.lastResult = ((EntityProto) this.entities.get(real_offset - 1));
                this.entities = this.entities.subList(real_offset, this.entities.size());
            }
            return real_offset;
        }

        public List<EntityProto> nextResults(int end) {
            List<EntityProto> subList = this.entities.subList(0, Math.min(end, this.entities.size()));

            if (subList.size() > 0) {
                this.lastResult = (subList.get(subList.size() - 1));
            }
            List<EntityProto> result;
            if (this.query.isKeysOnly()) {
                result = new ArrayList<EntityProto>();
                for (EntityProto entity : subList) {
                    result.add((entity.clone()).clearOwner().clearProperty().clearRawProperty());
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
                this.lastResult = (this.entities.get(fromIndex - 1));
            }

            if ((fromIndex != 0) || (toIndex != this.entities.size()))
                this.entities = new ArrayList<EntityProto>(this.entities.subList(fromIndex, toIndex));
        }

        public boolean isKeysOnly() {
            return this.query.isKeysOnly();
        }

        public EntityProto decompilePosition(DatastorePb.CompiledCursor.Position position) {
            EntityProto result = new EntityProto();
            result.mergeFrom(position.getStartKeyAsBytes());

            Query relevantInfo = new Query();
            relevantInfo.mergeFrom(result.getKey().getPath().getElement(0).getTypeAsBytes());
            if (!validateQuery(relevantInfo)) {
                throw new ApiProxy.ApplicationException(DatastorePb.Error.ErrorCode.BAD_REQUEST.getValue(),
                        "Cursor does not match query.");
            }

            result.getKey().getPath().removeElement(0);
            return result;
        }

        private Query getValidationInfo() {
            Query relevantInfo = new Query();
            for (Query.Filter filter : this.query.filters()) {
                relevantInfo.addFilter(filter);
            }
            for (Query.Order order : this.query.orders()) {
                relevantInfo.addOrder(order);
            }
            if (this.query.hasAncestor()) {
                relevantInfo.setAncestor(this.query.getAncestor());
            }
            if (this.query.hasKind()) {
                relevantInfo.setKind(this.query.getKind());
            }
            if (this.query.hasSearchQuery()) {
                relevantInfo.setSearchQuery(this.query.getSearchQuery());
            }
            return relevantInfo;
        }

        private boolean validateQuery(Query relevantInfo) {
            if (!relevantInfo.filters().equals(this.query.filters())) {
                return false;
            }

            if (!relevantInfo.orders().equals(this.query.orders())) {
                return false;
            }

            if (relevantInfo.hasAncestor()) {
                if ((!this.query.hasAncestor()) || (!relevantInfo.getAncestor().equals(this.query.getAncestor())))
                    return false;
            } else if (this.query.hasAncestor()) {
                return false;
            }

            if (relevantInfo.hasKind()) {
                if ((!this.query.hasKind()) || (!relevantInfo.getKind().equals(this.query.getKind())))
                    return false;
            } else if (this.query.hasKind()) {
                return false;
            }

            if (relevantInfo.hasSearchQuery()) {
                if ((!this.query.hasSearchQuery())
                        || (!relevantInfo.getSearchQuery().equals(this.query.getSearchQuery()))) {
                    return false;
                }
            } else if (this.query.hasSearchQuery()) {
                return false;
            }

            return true;
        }

        public Position compilePosition() {
            Position position = new Position();

            if (this.lastResult != null) {
                EntityProto savedEntity = new EntityProto();

                savedEntity.setKey(this.lastResult.getKey().clone());

                savedEntity.getKey().getPath().insertElement(0,
                        new Path.Element().setTypeAsBytes(getValidationInfo().toByteArray()));

                for (Property prop : this.lastResult.propertys()) {
                    if (this.orderProperties.contains(prop.getName())) {
                        savedEntity.addProperty(prop.clone());
                    }
                }
                position.setStartKeyAsBytes(savedEntity.toByteArray());
                position.setStartInclusive(false);
            }
            return position;
        }

        public CompiledQuery compileQuery() {
            CompiledQuery result = new CompiledQuery();
            CompiledQuery.PrimaryScan scan = result.getMutablePrimaryScan();
            scan.setIndexNameAsBytes(this.query.toByteArray());
            return result;
        }

        class DecompiledCursor {
            final EntityProto cursorEntity;
            final boolean inclusive;

            public DecompiledCursor(CompiledCursor compiledCursor) {
                if ((compiledCursor == null) || (compiledCursor.positionSize() == 0)) {
                    this.cursorEntity = null;
                    this.inclusive = false;
                    return;
                }

                Position position = compiledCursor.getPosition(0);
                if (!position.hasStartKey()) {
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

                int loc = Collections.binarySearch(LocalDatastoreService.LiveQuery.this.entities, this.cursorEntity,
                        entityComparator);
                if (loc < 0) {
                    return -(loc + 1);
                }
                return this.inclusive ? loc : loc + 1;
            }

            public EntityProto getCursorEntity() {
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

    private class RemoveStaleQueries implements Runnable {
        private RemoveStaleQueries() {
        }

        public void run() {

            LocalDatastoreService.pruneHasCreationTimeMap(LocalDatastoreService.this.clock.getCurrentTime(),
                    LocalDatastoreService.this.maxQueryLifetimeMs, live_queries);
        }
    }
}
