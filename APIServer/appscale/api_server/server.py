""" A server that handles API requests from runtime instances. """

import argparse
import logging
import os
import pickle

from kazoo.client import KazooClient
from tornado import web
from tornado.ioloop import IOLoop

from appscale.api_server import remote_api_pb2
from appscale.api_server.app_identity import AppIdentityService
from appscale.api_server.base_service import BaseService
from appscale.api_server.constants import ApplicationError
from appscale.common.constants import LOG_FORMAT
from appscale.common.constants import VAR_DIR
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS

logger = logging.getLogger('appscale-api-server')


class MainHandler(web.RequestHandler):
    """ Handles API requests. """
    def initialize(self, service_map):
        """ Defines resources required to handle requests.

        Args:
            service_map: A dictionary containing API service implementations.
        """
        self.service_map = service_map

    def post(self):
        """ Handles API requests. """
        api_request = remote_api_pb2.Request()
        api_request.ParseFromString(self.request.body)
        api_response = remote_api_pb2.Response()

        service = self.service_map.get(api_request.service_name,
                                       BaseService(api_request.service_name))
        try:
            api_response.response = service.make_call(api_request.method,
                                                      api_request.request)
        except ApplicationError as error:
            api_response.application_error.code = error.code
            api_response.application_error.detail = error.detail
        except Exception as error:
            # Unexpected exceptions from the API Proxy server itself will not
            # be parsed in a friendly way by the runtime. Python runtimes will
            # at least be able to re-raise a RuntimeError.
            logger.exception('Unknown error')
            response_exception = RuntimeError(repr(error))
            api_response.exception = pickle.dumps(response_exception)

        self.write(api_response.SerializeToString())


def main():
    """ A server that handles API requests from runtime instances. """
    logging.basicConfig(format=LOG_FORMAT)

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True,
                        help='The port to serve requests from')
    parser.add_argument('--project-id', required=True,
                        help='The project to handle requests for')
    parser.add_argument('--zookeeper-locations', required=True, nargs='+',
                        help='A list of ZooKeeper locations')
    args = parser.parse_args()

    pidfile_location = os.path.join(
        VAR_DIR, 'api-server_{}-{}.pid'.format(args.project_id, args.port))
    with open(pidfile_location, 'w') as pidfile:
        pidfile.write(str(os.getpid()))

    logger.setLevel(logging.INFO)

    zk_client = KazooClient(hosts=','.join(args.zookeeper_locations),
                            connection_retry=ZK_PERSISTENT_RECONNECTS)
    zk_client.start()

    service_map = {
        'app_identity_service': AppIdentityService(args.project_id, zk_client)
    }

    app = web.Application([
        ('/', MainHandler, {'service_map': service_map})
    ])
    logger.info('Starting API server for {} on {}'.format(args.project_id,
                                                          args.port))
    app.listen(args.port)
    IOLoop.current().start()
