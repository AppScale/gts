package com.google.appengine.tools.resources;


public class ResourceLoader
{

    private static ResourceLoader res                       = null;
    private final int             PROTOCOL_BUFFER_PORT      = 8888;
    private final String          DB_LOCATION_PROPERTY      = "DB_LOCATION";
    private static String         apphome                   = "/etc/appscale";
    private final String          HADOOP_PATH               = "/AppDB/hadoop-0.20.0";
    private final String          MEMCACHE_SERVER_IP_PATH   = "/memcache_ips";
    private final boolean         IS_SSL                    = false;
    private final String          TMP_LOCATION              = "/tmp";
    private final String          NUM_NODES_LOCATION        = "/num_of_nodes";

    public static ResourceLoader getResourceLoader()
    {
        if (res == null) res = new ResourceLoader();
        System.out.println("appscale home is: " + apphome);
        return res;
    }

    public boolean getDatastoreSecurityMode()
    {
        // true means SSL(https), otherwise normal http
        return IS_SSL;
    }

    public int getPbServerPort()
    {
        return PROTOCOL_BUFFER_PORT;
    }

    public String getPbServerIp()
    {
        String dbLocation = System.getProperty(DB_LOCATION_PROPERTY);
        if (dbLocation != null) return dbLocation;
        return null;
    }

    public String getMemcachedServerIp()
    {
        return apphome + MEMCACHE_SERVER_IP_PATH;
    }

    public String getNumOfNode()
    {
        return apphome + NUM_NODES_LOCATION;
    }

    public String getHadoopHome()
    {
        return apphome + HADOOP_PATH;
    }

    public String getMrTmpLocation()
    {
        return TMP_LOCATION;
    }
}
