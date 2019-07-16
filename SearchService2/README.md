# AppScale SearchService

A server that handles Search API requests from GAE application.

### How to set up

1. [Install a protocol buffer compiler](https://github.com/google/protobuf)
2. Compile protocol buffer `*.proto` file, compile antlr4 query parser,
   install appscale-common and appscale-search2 packages using a script:

   `SearchService2/build-scripts/ensure_searchservice2.sh <your-venv>/bin/pip`

3. Ensure Zookeeper cluster is started and its locations are saved to
  `/etc/appscale/zookeeper_locations`.
   
4. Ensure SolrCloud cluster is started, connected to Zookeeper and
   `appscale-search-api-config` config-set is created in SolrCloud:
   
   `SearchService2/solr-management/ensure_solr_running.sh`
   
5. Start the server with 
   ```
   appscale-search2 --verbose --host <PRIVATE_IP> --port <PORT> 
                    --zk-locations <ZK1> <ZK2> <ZK3>
   ```


### Known issues

 - HTML field type is not supported.
 - The service doesn't support geo queries. Query grammar, parser and converter
   need to be updated, but all needed data is already properly indexed to Solr.
 - Search query `foo bar` won't search atom fields for `"foo bar"`, but will
   search for `"foo"` and `"bar"` separately. According 
 - There might be number of differences between GAE and our text fields
   analysers. We may need to go through 
   [GAE docs](https://cloud.google.com/appengine/docs/standard/python/search/#special-treatment)
   to build own text analyser which would behave more closely to GAE.
 - Sort expressions are not fully implemented yet.
 - Field expressions are not implemented yet.
 - `_rank` in query should be interpreted as a reference to `rank` of document.
 - It doesn't seem that we can easily implement document scores in results.
 