import sys
import time
sys.path.append("..")

import appscale_datastore

db = appscale_datastore.Datastore("scalaris")
user_schema = db.get_schema("USERS__")
print user_schema
app_schema = db.get_schema("APPS__")
print app_schema

#time.sleep(100)
