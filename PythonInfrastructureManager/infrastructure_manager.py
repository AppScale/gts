from agents.factory import InfrastructureAgentFactory
from utils import utils
from utils.utils import has_parameter

__author__ = 'hiranya'

# Default reasons which might be returned by this module
REASON_BAD_SECRET               = 'bad secret'
REASON_RESERVATION_NOT_FOUND    = 'reservation_id not found'
REASON_NONE                     = 'none'

PARAM_RESERVATION_ID    = 'reservation_id'
PARAM_INFRASTRUCTURE    = 'infrastructure'
PARAM_NUM_VMS           = 'num_vms'

# A list of the parameters required to query the InfrastructureManager about
# the state of a run_instances request.
DESCRIBE_INSTANCES_REQUIRED_PARAMS = ( PARAM_RESERVATION_ID, )

RUN_INSTANCES_REQUIRED_PARAMS = (
    PARAM_INFRASTRUCTURE,
    PARAM_NUM_VMS
)

class InfrastructureManager:

    def __init__(self):
        self.secret = utils.get_secret()
        self.reservations = { }
        self.agent_factory = InfrastructureAgentFactory()

    def describe_instances(self, parameters, secret):
        if self.secret != secret:
            return self.__generate_response(False, REASON_BAD_SECRET)

        for param in DESCRIBE_INSTANCES_REQUIRED_PARAMS:
            if not has_parameter(param, parameters):
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
            if not has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        num_vms = parameters[PARAM_NUM_VMS]
        infrastructure = parameters[PARAM_INFRASTRUCTURE]
        agent = self.agent_factory.create_agent(infrastructure)
        status, reason = agent.has_required_parameters(parameters)
        if not status:
            return self.__generate_response(False, reason)

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

    def __spawn_vms(self, agent, num_vms, parameters):
        if num_vms < 0:
            return [], [], []
        agent.configure_instance_security(parameters)
        agent.run_instances(num_vms, parameters)

    def __generate_response(self, status, msg, extra = None):
        response = { 'success' : status, 'reason' : msg }
        if extra is not None:
            for key, value in extra.items():
                response[key] = value
        return response