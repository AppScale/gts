import sys
import os

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  exit(1)

sys.path.append(APPSCALE_HOME  + "AppDB/hypertable")
import py_hypertable
import xml_parser
import string, cgi
USER_TABLE = "USERS__"
HYPERTABLE_XML_TAG = "Name"


schema = xml_parser.getListFromXMLSchema(USER_TABLE, HYPERTABLE_XML_TAG)
print schema
#table = USER_TABLE
#schema = py_hypertable.get_schema(table)
#print schema
