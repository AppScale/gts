#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Loading appstats data from and to various sources like file, memcache etc.

The file currently has modules to read data from memcache, to write appstats
data to a file in pickled format, and to read records from a file after
unpickling. The script is envisioned to be extensible in the future to allow
reading/writing to/from datastore, storing data in alternate file formats such
as SQLLite etc.
"""


import cPickle as pickle
import logging
import time
from google.appengine.ext.appstats import datamodel_pb
from google.appengine.ext.appstats import recording


def FromMemcache(filter_timestamp=0, java_application=False):
  """Reads appstats data from memcache.

  Get all appstats full records from memcache which
  correspond to requests with a greater timestamp
  than filter_timestamp

  Args:
    filter_timestamp: only retrieve records with timestamp
      (in milliseconds) higher than this value. If 0, all
      records are retrieved.
    java_application: Boolean. If true, this function is being
      called by the download_appstats tool for a Java
      application.

  Returns:
    List of RequestStatProto protobufs.
  """
  records = []
  logging.info('Loading appstats summaries...')
  summaries = recording.load_summary_protos(java_application)
  logging.info('Loaded %d summaries. Loading full records...',
               len(summaries))
  start_time = time.time()
  missing_full_records = 0
  failed_requests = 0
  for count, summary in enumerate(summaries):
    time_key = summary.start_timestamp_milliseconds()
    if time_key <= filter_timestamp:




      logging.info('Only %d records with newer timestamp.'
                   ' Skipping rest.', count)
      break
    timestamp = int(time_key) * 0.001
    record = recording.load_full_proto(timestamp, java_application)
    if not record:
      missing_full_records += 1
      continue
    httpstatus = int(record.http_status())
    if httpstatus >= 400:
      failed_requests += 1
      continue
    records.append(record)
    if len(records) % 10 == 0:
      logging.info('Download in progress..completed %d..', len(records))
  if not records:
    logging.info('No full records present in memcache for succesful requests.')
  else:
    end_time = time.time()
    elapsed = max(end_time - start_time, 0)
    time_per_record = elapsed/len(records)
    logging.info('Done. %d full records downloaded in %.2f secs '
                 '[%.2f secs per full record]',
                 len(records), elapsed, time_per_record)
    if missing_full_records:
      logging.info('Skipped %d summaries with missing full records',
                   missing_full_records)
    if failed_requests:
      logging.info('Skipped %d summaries corresponding to failed requests',
                   failed_requests)
  return records


def PickleToFile(records, outfile):
  """Writes appstats data to file.

  Args:
    records: list of RequestStatProto protobufs
    outfile: file object to write appstats data to

  Returns:
    None.

  File format is a pickled list of protobufs encoded as
  binary strings.
  """
  encoded_records = []
  for record in records:
    encoded = record.Encode()
    encoded_records.append(encoded)



  pickle.dump(encoded_records, outfile, protocol=pickle.HIGHEST_PROTOCOL)


def UnpickleFromFile(datafile):
  """Reads appstats data from file.

  Args:
    datafile: file object to read appstats data from.  File format is a
      pickled list of protobufs encoded as binary strings.

  Returns:
    List of RequestStatProto protobufs.
  """
  encoded_records = pickle.load(datafile)
  records = []
  for encoded_record in encoded_records:
    record = datamodel_pb.RequestStatProto(encoded_record)
    records.append(record)
    datafile.close()
  return records
