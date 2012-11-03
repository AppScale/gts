from os import environ
from utils import utils

__author__ = 'hiranya'

# Default reasons which might be returned by this module
REASON_BAD_SECRET               = 'bad secret'
REASON_RESERVATION_NOT_FOUND    = 'reservation_id not found'
REASON_NONE                     = 'none'

PARAM_RESERVATION_ID    = 'reservation_id'
PARAM_CREDENTIALS       = 'credentials'
PARAM_GROUP             = 'group'
PARAM_IMAGE_ID          = 'image_id'
PARAM_INFRASTRUCTURE    = 'infrastructure'
PARAM_INSTANCE_TYPE     = 'instance_type'
PARAM_KEYNAME           = 'keyname'
PARAM_NUM_VMS           = 'num_vms'

# A list of the parameters required to query the InfrastructureManager about
# the state of a run_instances request.
DESCRIBE_INSTANCES_REQUIRED_PARAMS = ( PARAM_RESERVATION_ID, )

# A list of the parameters required to query the InfrastructureManager about
# the state of a run_instances request.
RUN_INSTANCES_REQUIRED_PARAMS = (
    PARAM_CREDENTIALS,
    PARAM_GROUP,
    PARAM_IMAGE_ID,
    PARAM_INFRASTRUCTURE,
    PARAM_INSTANCE_TYPE,
    PARAM_KEYNAME,
    PARAM_NUM_VMS
)

class InfrastructureManager:

    def __init__(self):
        self.secret = utils.get_secret()
        self.reservations = { }

    def describe_instances(self, parameters, secret):
        if self.secret != secret:
            return self.__generate_response(False, REASON_BAD_SECRET)

        for param in DESCRIBE_INSTANCES_REQUIRED_PARAMS:
            if not self.__has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        reservation_id = parameters[PARAM_RESERVATION_ID]
        if self.reservations.has_key(reservation_id):
            return self.reservations[reservation_id]
        else:
            return self.__generate_response(False, REASON_RESERVATION_NOT_FOUND)

    # Acquires machines via a cloud infrastructure. As this process could take
    # longer than the timeout for SOAP calls, we return to the user a reservation
    # ID that can be passed to describe_instances to poll for the state of the
    # new machines.
    def run_instances(self, parameters, secret):
        print 'Received a request to run instances.'

        if self.secret != secret:
            print 'Incoming secret', secret, 'does not match the current secret', \
                self.secret, '- Rejecting request.'
            return self.__generate_response(False, REASON_BAD_SECRET)

        print 'Request parameters are', str(parameters)
        for param in RUN_INSTANCES_REQUIRED_PARAMS:
            if not self.__has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        reservation_id = utils.get_random_alphanumeric()
        self.reservations[reservation_id] = {
            'success' : True,
            'reason' : 'received run request',
            'state' : 'pending',
            'vm_info' : None
        }
        print 'Generated reservation id', reservation_id, 'for this request.'
        # TODO: Start deployment on separate thread
        print 'Successfully started request',  reservation_id, '.'
        return self.__generate_response(True, REASON_NONE, { 'reservation_id' : reservation_id })

    def __has_parameter(self, p, params):
        return params.has_key(p) and params[p] is not None and len(params[p]) > 0

    def __generate_response(self, status, msg, extra = None):
        response = { 'success' : status, 'reason' : msg }
        if extra is not None:
            for key, value in extra.items():
                response[key] = value
        return response

class IaaSAgent:
    def set_environment_variables(self, variables, cloud_num):
        prefix = 'CLOUD' + str(cloud_num) + '_'
        for key, value in variables.items():
            if key.startswith(prefix):
                environ[key[len(prefix):]] = value

    def spawn_vms(self, parameters):
        raise NotImplementedError