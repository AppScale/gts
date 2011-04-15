package com.google.appengine.api.datastore.dev;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.Writer;
import java.text.SimpleDateFormat;
import java.util.Collections;
import java.util.Date;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.mortbay.xml.XmlParser;
import org.xml.sax.SAXException;

import com.google.appengine.api.datastore.CompositeIndexManager;
import com.google.appengine.api.datastore.DatastoreNeedIndexException;
import com.google.appengine.repackaged.com.google.common.base.Preconditions;
import com.google.appengine.repackaged.com.google.common.base.Predicate;
import com.google.appengine.repackaged.com.google.common.base.Predicates;
import com.google.appengine.repackaged.com.google.common.collect.Lists;
import com.google.appengine.repackaged.com.google.common.collect.Maps;
import com.google.appengine.repackaged.com.google.common.collect.Sets;
import com.google.appengine.tools.development.Clock;
import com.google.apphosting.api.DatastorePb;
import com.google.apphosting.utils.config.AppEngineConfigException;
import com.google.apphosting.utils.config.GenerationDirectory;
import com.google.storage.onestore.v3.OnestoreEntity;
import com.google.storage.onestore.v3.OnestoreEntity.Index;

class LocalCompositeIndexManager extends CompositeIndexManager
{
  private static final String DATASTORE_INDEXES_ELEMENT_FORMAT = "<datastore-indexes%s>\n\n";
  private static final String DATASTORE_INDEXES_ELEMENT_EMPTY = String.format("<datastore-indexes%s>\n\n", new Object[] { "/" });

  private static final String DATASTORE_INDEXES_ELEMENT_NOT_EMPTY = String.format("<datastore-indexes%s>\n\n", new Object[] { "" });
  private static final String DATASTORE_INDEXES_ELEMENT_CLOSE = "</datastore-indexes>\n";
  private static final String FREQUENCY_XML_COMMENT_FORMAT = "    <!-- Used %d time%s in query history -->\n";
  private static final String TIMESTAMP_XML_COMMENT_FORMAT = "<!-- Indices written at %s -->\n\n";
  private static final Predicate<XmlParser.Node> MANUAL_INDEX_ONLY = new Predicate<XmlParser.Node>() {
    public boolean apply(XmlParser.Node node) {
      String sourceStr = node.getAttribute("source");

      return ((sourceStr == null) || (CompositeIndexManager.IndexSource.valueOf(LocalCompositeIndexManager.trim(sourceStr)) == CompositeIndexManager.IndexSource.manual)); }  } ;

  private static final Logger logger = Logger.getLogger(LocalCompositeIndexManager.class.getName());

  private static final LocalCompositeIndexManager INSTANCE = new LocalCompositeIndexManager();

  private final Map<IndexComponentsOnlyQuery, AtomicInteger> queryHistory = Collections.synchronizedMap(new LinkedHashMap<IndexComponentsOnlyQuery, AtomicInteger>());

  private final IndexCache indexCache = new IndexCache();
  private File appDir;
  private Clock clock;
  private boolean noIndexAutoGen;

  public static LocalCompositeIndexManager getInstance() { return INSTANCE;
  }

  public void processQuery(DatastorePb.Query query)
  {
    IndexComponentsOnlyQuery indexOnlyQuery = new IndexComponentsOnlyQuery(query);
    boolean isNewQuery = updateQueryHistory(indexOnlyQuery);
    if (isNewQuery)
      manageIndexFile(indexOnlyQuery);
  }

  private boolean updateQueryHistory(IndexComponentsOnlyQuery query)
  {
    boolean newQuery = false;
    AtomicInteger count = (AtomicInteger)this.queryHistory.get(query);
    if (count == null)
    {
      count = newAtomicInteger(0);
      AtomicInteger overwrittenCount = (AtomicInteger)this.queryHistory.put(query, count);

      if (overwrittenCount != null) {
        count.addAndGet(overwrittenCount.intValue());
      }
      else {
        newQuery = true;
      }
    }
    count.incrementAndGet();
    return newQuery;
  }

  void clearQueryHistory() {
    this.queryHistory.clear();
  }

  AtomicInteger newAtomicInteger(int i)
  {
    return new AtomicInteger(i);
  }

  Map<IndexComponentsOnlyQuery, AtomicInteger> getQueryHistory()
  {
    return this.queryHistory;
  }

  void manageIndexFile(IndexComponentsOnlyQuery query)
  {
    XmlParser.Node node = getCompositeIndicesNode();
    try {
      if ((node != null) && (autoGenIsDisabled(node))) {
        this.indexCache.verifyIndexExistsForQuery(query, node);
        logger.fine("Skipping index file update because auto gen is disabled.");
        return;
      }
    } catch (SAXException e) {
      String msg = "Received SAXException parsing the input stream.";
      logger.log(Level.SEVERE, msg, e);
      throw new AppEngineConfigException(msg, e);
    }

    if (this.noIndexAutoGen) {
      return;
    }
    updateIndexFile(node);
  }

  private void updateIndexFile(XmlParser.Node node)
  {
    synchronized (this.queryHistory) {
      List<Index> manuallyAddedIndices = extractIndices(node, MANUAL_INDEX_ONLY);
      Map<Index, Integer> indexMap = buildIndexMapFromQueryHistory();

      for (OnestoreEntity.Index manuallyAddedIndex : manuallyAddedIndices) {
        indexMap.remove(manuallyAddedIndex);
      }

      try
      {
        writeIndexFile(indexMap);
      } catch (IOException e) {
        logger.log(Level.SEVERE, "Unable to write " + getIndexFilename(), e);
      }
    }
  }

  List<OnestoreEntity.Index> extractIndices(XmlParser.Node node, Predicate<XmlParser.Node> indexPred)
  {
    if (node == null) {
      return Collections.emptyList();
    }
    List indices = Lists.newArrayList();

    Iterator indexIter = node.iterator("datastore-index");

    while (indexIter.hasNext()) {
      XmlParser.Node indexNode = (XmlParser.Node)indexIter.next();

      if (indexPred.apply(indexNode)) {
        OnestoreEntity.Index index = new OnestoreEntity.Index();
        indices.add(index);

        index.setEntityType(trim(indexNode.getAttribute("kind")));
        index.setAncestor(Boolean.valueOf(trim(indexNode.getAttribute("ancestor"))).booleanValue());

        Iterator propertyIter = indexNode.iterator("property");

        while (propertyIter.hasNext()) {
          XmlParser.Node propertyNode = (XmlParser.Node)propertyIter.next();
          OnestoreEntity.Index.Property prop = index.addProperty();
          prop.setName(trim(propertyNode.getAttribute("name")));
          XmlDirection dir = XmlDirection.valueOf(trim(propertyNode.getAttribute("direction")));
          prop.setDirection(dir.getDirection());
        }
      }
    }
    return indices;
  }

  private boolean autoGenIsDisabled(XmlParser.Node node) throws SAXException {
    String val = node.getAttribute("autoGenerate");
    if ((val == null) || ((!("true".equals(val))) && (!("false".equals(val))))) {
      throw new SAXException("autoGenerate=true|false is required in datastore-indexes.xml");
    }

    return (!(Boolean.valueOf(trim(val)).booleanValue()));
  }

  private static String trim(String attribute)
  {
    return ((attribute == null) ? null : attribute.trim());
  }

  InputStream getIndexFileInputStream() throws FileNotFoundException {
    return new FileInputStream(getIndexFile());
  }

  InputStream getGeneratedIndexFileInputStream() throws FileNotFoundException {
    File outfile = getGeneratedIndexFile();
    if (!(outfile.exists())) {
      return null;
    }
    return new FileInputStream(outfile);
  }

  synchronized XmlParser.Node getCompositeIndicesNode()
  {
    try
    {
      InputStream is = getIndexFileInputStream();
      XmlParser xmlParser = new XmlParser();
      try {
        XmlParser.Node manual = xmlParser.parse(is);
        is = getGeneratedIndexFileInputStream();
        if (is != null) {
          try {
            XmlParser.Node auto = xmlParser.parse(is);
            manual.addAll(auto);
          } catch (IOException e) {
            String msg = "Received IOException parsing the generated input stream.";
            throw new AppEngineConfigException(msg, e);
          } catch (SAXException e) {
            String msg = "Received SAXException parsing the generated input stream.";
            throw new AppEngineConfigException(msg, e);
          }
        }
        return manual;
      } catch (IOException e) {
        String msg = "Received IOException parsing the input stream.";
        logger.log(Level.SEVERE, msg, e);
        throw new AppEngineConfigException(msg, e);
      } catch (SAXException e) {
        String msg = "Received SAXException parsing the input stream.";
        logger.log(Level.SEVERE, msg, e);
        throw new AppEngineConfigException(msg, e);
      }
    } catch (FileNotFoundException e) {
    }
    return null;
  }

  void writeIndexFile(Map<OnestoreEntity.Index, Integer> autoUpdateIndexMap)
    throws IOException
  {
    SimpleDateFormat format = new SimpleDateFormat("EEE, d MMM yyyy HH:mm:ss z", Locale.US);

    Writer fw = newWriter();
    BufferedWriter out = null;
    try {
      out = new BufferedWriter(fw);
      out.append(String.format("<!-- Indices written at %s -->\n\n", new Object[] { format.format(new Date(this.clock.getCurrentTime())) }));

      if (autoUpdateIndexMap.isEmpty()) {
        out.append(DATASTORE_INDEXES_ELEMENT_EMPTY);
      } else {
        out.append(DATASTORE_INDEXES_ELEMENT_NOT_EMPTY);
        for (Map.Entry entry : autoUpdateIndexMap.entrySet()) {
          int count = ((Integer)entry.getValue()).intValue();

          out.append(String.format("    <!-- Used %d time%s in query history -->\n", new Object[] { Integer.valueOf(count), (count == 1) ? "" : "s" }));
          String xml = generateXmlForIndex((OnestoreEntity.Index)entry.getKey(), CompositeIndexManager.IndexSource.auto);
          out.append(xml);
        }
        out.append("</datastore-indexes>\n");
      }
    } finally {
      if (out != null)
        out.close();
    }
  }

  Map<OnestoreEntity.Index, Integer> buildIndexMapFromQueryHistory()
  {
    Map indexMap = Maps.newLinkedHashMap();

    Preconditions.checkState(Thread.holdsLock(this.queryHistory), "Current thread does not have a lock on queryHistory!");

    for (Map.Entry entry : this.queryHistory.entrySet()) {
      OnestoreEntity.Index index = compositeIndexForQuery((IndexComponentsOnlyQuery)entry.getKey());
      if (index == null) {
        continue;
      }

      Integer count = (Integer)indexMap.get(index);
      if (count == null) {
        count = Integer.valueOf(0);
      }
      count = Integer.valueOf(count.intValue() + ((AtomicInteger)entry.getValue()).intValue());
      indexMap.put(index, count);
    }
    return indexMap;
  }

  Writer newWriter()
    throws IOException
  {
    File output = getGeneratedIndexFile();
    output.getParentFile().mkdirs();
    return new FileWriter(output);
  }

  File getGeneratedIndexFile() {
    File dir = GenerationDirectory.getGenerationDirectory(this.appDir);
    return new File(dir, "datastore-indexes-auto.xml");
  }

  File getIndexFile() {
    return new File(new File(this.appDir, "WEB-INF"), "datastore-indexes.xml");
  }

  String getIndexFilename() {
    return getIndexFile().getPath();
  }

  public void setAppDir(File appDir)
  {
    this.appDir = appDir;
  }

  public void setClock(Clock clock) {
    this.clock = clock;
  }

  public void setNoIndexAutoGen(boolean noIndexAutoGen) {
    this.noIndexAutoGen = noIndexAutoGen;
  }

  protected OnestoreEntity.Index compositeIndexForQuery(IndexComponentsOnlyQuery indexOnlyQuery)
  {
    return super.compositeIndexForQuery(indexOnlyQuery);
  }

  protected static class IndexComponentsOnlyQuery extends CompositeIndexManager.IndexComponentsOnlyQuery
  {
    protected IndexComponentsOnlyQuery(DatastorePb.Query query)
    {
      super(query);
    }
  }

  protected static class ValidatedQuery extends CompositeIndexManager.ValidatedQuery
  {
    protected ValidatedQuery(DatastorePb.Query query)
    {
      super(query);
    }
  }

  private final class IndexCache
  {
    private Set<OnestoreEntity.Index> indexCache;

    private IndexCache()
    {
      this.indexCache = null;
    }

    private synchronized void verifyIndexExistsForQuery(LocalCompositeIndexManager.IndexComponentsOnlyQuery query, XmlParser.Node node)
    {
      if (this.indexCache == null)
      {
    	  Predicate<XmlParser.Node> a = Predicates.alwaysFalse();
        this.indexCache = Sets.newHashSet(LocalCompositeIndexManager.this.extractIndices(node, a));
      }

      OnestoreEntity.Index index = LocalCompositeIndexManager.this.compositeIndexForQuery(query);
      if ((index == null) || (this.indexCache.contains(index)))
      {
        return;
      }

      throw new DatastoreNeedIndexException("Query " + query + " requires the following index:\n" + LocalCompositeIndexManager.this.generateXmlForIndex(index, CompositeIndexManager.IndexSource.manual) + "\nPlease add this to " + LocalCompositeIndexManager.this.getIndexFilename() + " or enable autoGenerate to have it " + "automatically added.");
    }
  }

  static enum XmlDirection
  {
    asc{
		@Override
		OnestoreEntity.Index.Property.Direction getDirection() {
			return OnestoreEntity.Index.Property.Direction.ASCENDING;
		}
    },
		desc{
			@Override
			OnestoreEntity.Index.Property.Direction getDirection() {
				return OnestoreEntity.Index.Property.Direction.DESCENDING;
			}
		};

    abstract OnestoreEntity.Index.Property.Direction getDirection();
  }
}