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




"""Service configuration for remote API.

This module is shared by both the remote_api_stub and the handler.
"""

import sys

from google.appengine.api import api_base_pb
from google.appengine.api.channel import channel_service_pb
from google.appengine.api import mail_service_pb
from google.appengine.api import urlfetch_service_pb
from google.appengine.api import user_service_pb
from google.appengine.api.blobstore import blobstore_service_pb
from google.appengine.api.capabilities import capability_service_pb
from google.appengine.api.conversion import conversion_service_pb
from google.appengine.api.files import file_service_pb
from google.appengine.api.images import images_service_pb
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.memcache import memcache_service_pb
from google.appengine.api.system import system_service_pb
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.api.xmpp import xmpp_service_pb
from google.appengine.datastore import datastore_pb
from google.appengine.ext.remote_api import remote_api_pb


SERVICE_PB_MAP = {
    'blobstore': {
        'CreateUploadURL': (blobstore_service_pb.CreateUploadURLRequest,
                            blobstore_service_pb.CreateUploadURLResponse),
        'DeleteBlob':      (blobstore_service_pb.DeleteBlobRequest,
                            api_base_pb.VoidProto),
        'FetchData':       (blobstore_service_pb.FetchDataRequest,
                            blobstore_service_pb.FetchDataResponse),
    },
    'capability_service': {
        'IsEnabled': (capability_service_pb.IsEnabledRequest,
                      capability_service_pb.IsEnabledResponse),
    },
    'channel': {
        'CreateChannel': (channel_service_pb.CreateChannelRequest,
                          channel_service_pb.CreateChannelResponse),
        'SendChannelMessage': (channel_service_pb.SendMessageRequest,
                               api_base_pb.VoidProto),
    },
    'conversion': {
        'Convert': (conversion_service_pb.ConversionRequest,
                    conversion_service_pb.ConversionResponse),
    },
    'datastore_v3': {
        'Get':        (datastore_pb.GetRequest, datastore_pb.GetResponse),
        'Put':        (datastore_pb.PutRequest, datastore_pb.PutResponse),
        'Delete':     (datastore_pb.DeleteRequest, datastore_pb.DeleteResponse),
        'Count':      (datastore_pb.Query, api_base_pb.Integer64Proto),
        'GetIndices': (api_base_pb.StringProto, datastore_pb.CompositeIndices),
        'AllocateIds':(datastore_pb.AllocateIdsRequest,
                       datastore_pb.AllocateIdsResponse),
        'RunQuery':   (datastore_pb.Query,
                       datastore_pb.QueryResult),
        'RunCompiledQuery':(datastore_pb.RunCompiledQueryRequest,
                            datastore_pb.QueryResult),
        'Next':       (datastore_pb.NextRequest, datastore_pb.QueryResult),
        'BeginTransaction':(datastore_pb.BeginTransactionRequest,
                            datastore_pb.Transaction),
        'Commit':          (datastore_pb.Transaction,
                            datastore_pb.CommitResponse),
        'Rollback':        (datastore_pb.Transaction,
                            api_base_pb.VoidProto),
    },
    'file': {
        'Create': (file_service_pb.CreateRequest,
                   file_service_pb.CreateResponse),
        'Open': (file_service_pb.OpenRequest,
                 file_service_pb.OpenResponse),
        'Close': (file_service_pb.CloseRequest,
                  file_service_pb.CloseResponse),
        'Append': (file_service_pb.AppendRequest,
                   file_service_pb.AppendResponse),
        'Stat': (file_service_pb.StatRequest,
                 file_service_pb.StatResponse),
        'Delete': (file_service_pb.DeleteRequest,
                   file_service_pb.DeleteResponse),
        'Read': (file_service_pb.ReadRequest,
                 file_service_pb.ReadResponse),
        'ReadKeyValue': (file_service_pb.ReadKeyValueRequest,
                         file_service_pb.ReadKeyValueResponse),
        'Shuffle': (file_service_pb.ShuffleRequest,
                    file_service_pb.ShuffleResponse),
        'GetShuffleStatus': (file_service_pb.GetShuffleStatusRequest,
                             file_service_pb.GetShuffleStatusResponse),
    },
    'images': {
        'Transform': (images_service_pb.ImagesTransformRequest,
                      images_service_pb.ImagesTransformResponse),
        'Composite': (images_service_pb.ImagesCompositeRequest,
                      images_service_pb.ImagesCompositeResponse),
        'Histogram': (images_service_pb.ImagesHistogramRequest,
                      images_service_pb.ImagesHistogramResponse),
    },
    'logservice': {
        'Read': (log_service_pb.LogReadRequest, log_service_pb.LogReadResponse),
    },
    'mail': {
        'Send':         (mail_service_pb.MailMessage, api_base_pb.VoidProto),
        'SendToAdmins': (mail_service_pb.MailMessage, api_base_pb.VoidProto),
    },
    'memcache': {
        'Get':       (memcache_service_pb.MemcacheGetRequest,
                      memcache_service_pb.MemcacheGetResponse),
        'Set':       (memcache_service_pb.MemcacheSetRequest,
                      memcache_service_pb.MemcacheSetResponse),
        'Delete':    (memcache_service_pb.MemcacheDeleteRequest,
                      memcache_service_pb.MemcacheDeleteResponse),
        'Increment': (memcache_service_pb.MemcacheIncrementRequest,
                      memcache_service_pb.MemcacheIncrementResponse),
        'FlushAll':  (memcache_service_pb.MemcacheFlushRequest,
                      memcache_service_pb.MemcacheFlushResponse),
        'Stats':     (memcache_service_pb.MemcacheStatsRequest,
                      memcache_service_pb.MemcacheStatsResponse),
    },
    'remote_datastore': {
        'RunQuery':    (datastore_pb.Query, datastore_pb.QueryResult),
        'Transaction': (remote_api_pb.TransactionRequest,
                        datastore_pb.PutResponse),
        'GetIDs':      (datastore_pb.PutRequest, datastore_pb.PutResponse),
    },
    'system': {
        'GetSystemStats': (system_service_pb.GetSystemStatsRequest,
                           system_service_pb.GetSystemStatsResponse),
    },
    'taskqueue': {
        'Add': (taskqueue_service_pb.TaskQueueAddRequest,
                taskqueue_service_pb.TaskQueueAddResponse),
        'BulkAdd': (taskqueue_service_pb.TaskQueueBulkAddRequest,
                    taskqueue_service_pb.TaskQueueBulkAddResponse),
        'UpdateQueue': (taskqueue_service_pb.TaskQueueUpdateQueueRequest,
                        taskqueue_service_pb.TaskQueueUpdateQueueResponse),
        'FetchQueues': (taskqueue_service_pb.TaskQueueFetchQueuesRequest,
                        taskqueue_service_pb.TaskQueueFetchQueuesResponse),
        'FetchQueueStats': (
            taskqueue_service_pb.TaskQueueFetchQueueStatsRequest,
            taskqueue_service_pb.TaskQueueFetchQueueStatsResponse),
        'Delete': (taskqueue_service_pb.TaskQueueDeleteRequest,
                   taskqueue_service_pb.TaskQueueDeleteResponse),
        'PurgeQueue': (taskqueue_service_pb.TaskQueuePurgeQueueRequest,
                       taskqueue_service_pb.TaskQueuePurgeQueueResponse),
        'QueryTasks': (taskqueue_service_pb.TaskQueueQueryTasksRequest,
                       taskqueue_service_pb.TaskQueueQueryTasksResponse),
        'QueryAndOwnTasks': (
            taskqueue_service_pb.TaskQueueQueryAndOwnTasksRequest,
            taskqueue_service_pb.TaskQueueQueryAndOwnTasksResponse),
        'ModifyTaskLease': (
            taskqueue_service_pb.TaskQueueModifyTaskLeaseRequest,
            taskqueue_service_pb.TaskQueueModifyTaskLeaseResponse),
    },
    'urlfetch': {
        'Fetch': (urlfetch_service_pb.URLFetchRequest,
                  urlfetch_service_pb.URLFetchResponse),
    },
    'user': {
        'CreateLoginURL': (user_service_pb.CreateLoginURLRequest,
                           user_service_pb.CreateLoginURLResponse),
        'CreateLogoutURL': (user_service_pb.CreateLogoutURLRequest,
                            user_service_pb.CreateLogoutURLResponse),
    },
    'xmpp': {
        'GetPresence': (xmpp_service_pb.PresenceRequest,
                        xmpp_service_pb.PresenceResponse),
        'SendMessage': (xmpp_service_pb.XmppMessageRequest,
                        xmpp_service_pb.XmppMessageResponse),
        'SendInvite':  (xmpp_service_pb.XmppInviteRequest,
                        xmpp_service_pb.XmppInviteResponse),
        'SendPresence':  (xmpp_service_pb.XmppSendPresenceRequest,
                        xmpp_service_pb.XmppSendPresenceResponse),
    },
}
