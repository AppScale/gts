

class AppScaleStatusHelper:
  """ Helper class to get info from AppScale. """
  @classmethod
  def get_status_information(cls):
    #TODO get this data with SOAP
    return [{"ip":"192.168.33.168",
             "cpu":5.7,
             "memory":"92.07",
             "disk":8,
             "roles":["load_balancer","shadow","db_master","zookeeper",
                      "login","memcache","taskqueue_master","appengine"],
             "db_location":"192.168.33.168",
             "cloud":"cloud1",
             "state":"Done starting up AppScale, now in heartbeat mode"}
           ]


  @classmethod
  def get_head_node_ip(cls):
    #TODO get this data with SOAP
    return '192.168.33.168'

  @classmethod
  def get_monitoring_url(cls):
    return "http://"+cls.get_head_node_ip()+":8050"

  @classmethod
  def get_application_information(cls):
    #TODO get this data with SOAP
    return [["guestbook", True]]
 
  @classmethod
  def get_database_information(cls):
    #TODO get this data with SOAP
    return {'database': 'cassandra',
            'replication': "1",
            'keyname':'appscale'}

  @classmethod
  def get_service_info(cls):
    #TODO get this data with SOAP
    return {"memcache":"running",
            "datastore_write":"running",
            "urlfetch":"running",
            "images":"running",
            "users":"running",
            "xmpp":"running",
            "taskqueue":"running",
            "datastore":"running",
            "blobstore":"running"}

