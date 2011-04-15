#Navraj Chohan
# Parse Schema from HTable and HBase
# Return it as a string array

import string
import os
import py_hypertable
import cgi
from xml.sax import make_parser
import xml
from xml.sax import parseString
from xml.sax.handler import feature_namespaces
from xml.sax import ContentHandler
from xml.sax import saxutils
from xml.sax.handler import ContentHandler

class xmlSchemaParser(ContentHandler):
  attributes = []
  def __init__(self, tag_name):
    self.tag_name = tag_name
    self.isName = 0
 
  def clear_attributes(self):
    xmlSchemaParser.attributes = []
 
  def startElement(self, name, attrs):
    if name == self.tag_name:
      self.isName = 1
   
  def endElement(self, name):
    if name == self.tag_name:
      self.isName = 0
   
  def characters(self, ch):
    if self.isName == 1:
      xmlSchemaParser.attributes.append(ch) 

# tag is the xml tag which holds the schema attributes 
def getListFromXMLSchema(table, tag):
  dh = xmlSchemaParser(tag)
  dh.clear_attributes()
  parser = make_parser()

  #parser = setFeature(feature_namespaces, 0)
  dh = xmlSchemaParser(tag)
  parser.setContentHandler(dh)
  schema = py_hypertable.get_schema(table)
  #print schema
  #print schema[1]
  xml.sax.parseString(schema[1], dh)
  # items are not strings, need to convert them
  for ii in range(0, len(xmlSchemaParser.attributes)):
    xmlSchemaParser.attributes[ii] = str(xmlSchemaParser.attributes[ii])
  #print xmlSchemaParser.attributes
  return xmlSchemaParser.attributes 
