import thread
from agents.base_agent import BaseAgent
from agents.factory import InfrastructureAgentFactory
from utils import utils

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

TERMINATE_INSTANCES_REQUIRED_PARAMS = (
    PARAM_INFRASTRUCTURE,
)

class InfrastructureManager:
    """
    InfrastructureManager class is the main entry point to the AppScale
    Infrastructure Manager implementation. An instance of this class can
    be used to start new virtual machines in a specified cloud environment
    and terminate virtual machines when they are no longer required. Instances
    of this class also keep track of the virtual machines spawned by them
    and hence each InfrastructureManager instance can be queried to obtain
    information about any virtual machines spawned by each of them in the
    past.

    This implementation is completely cloud infrastructure agnostic
    and hence can be used to spawn/terminate instances on a wide range of
    cloud (IaaS) environments. All the cloud environment specific operations
    are delegated to a separate cloud agent and the InfrastructureManager
    initializes cloud agents on demand by looking at the 'infrastructure'
    parameter passed into the methods of this class.
    """

    def __init__(self):
        """
        Create a new InfrastructureManager instance. This constructor
        does not accept any arguments.
        """
        self.secret = utils.get_secret()
        self.reservations = { }
        self.agent_factory = InfrastructureAgentFactory()

    def describe_instances(self, parameters, secret):
        """
        Query the InfrastructureManager instance for details regarding
        a set of virtual machines spawned in the past. This method accepts
        a dictionary of parameters and a secret for authentication purposes.
        The dictionary of parameters must include a 'reservation_id' parameter
        which is used to reference past virtual machine deployments.

        Arguments:
            - parameters    A dictionary of parameters which contain a valid
                            'reservation_id' parameter. A valid 'reservation_id'
                            is an ID issues by the run_instances method of the
                            same InfrastructureManager object instance.
            - secret        A previously established secret

        Returns:
            If the provided secret key is valid and the parameters map contains
            a valid 'reservation_id' parameter, this method will return a
            dictionary containing information regarding the requested past
            virtual machine deployment. This returned map contains several
            keys including 'success', 'state', 'reason' and 'vm_info'. The value
            of 'success' could be True of False depending on the outcome of the
            virtual machine deployment process. If the value of 'success' happens
            to be False, the 'reason' key would contain more details as to what
            caused the deployment to fail. The 'state' key could contain a 'pending'
            value or a 'running' value depending on the current state of the
            virtual machine deployment. And finally the 'vm_info' key would point
            to a another dictionary containing the IP addresses of the spawned virtual
            machines. If the virtual machine deployment had failed or still in the
            'pending' state, this key would contain the value None.

            If this method receives an invalid key or an invalid 'reservation_id'
            parameter, it will return a dictionary containing the keys 'success'
            and 'reason' where 'success' would be set to False, and 'reason' is
            set to a simple error message describing the cause of the error.
        """
        if self.secret != secret:
            return self.__generate_response(False, REASON_BAD_SECRET)

        for param in DESCRIBE_INSTANCES_REQUIRED_PARAMS:
            if not utils.has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        reservation_id = parameters[PARAM_RESERVATION_ID]
        if self.reservations.has_key(reservation_id):
            return self.reservations[reservation_id]
        else:
            return self.__generate_response(False, REASON_RESERVATION_NOT_FOUND)

    def run_instances(self, parameters, secret):
        """
        Start a new virtual machine deployment using the provided parameters. The
        input parameter set must include an 'infrastructure' parameter which indicates
        the exact cloud environment to use. Value of this parameter will be used to
        instantiate a cloud environment specific agent which knows how to interact
        with the specified cloud platform. The parameters map must also contain a
        'num_vms' parameter which indicates the number of virtual machines that should
        be spawned. In addition to that any parameters required to spawn VMs in the
        specified cloud environment must be included in the parameters map.

        A typical VM deployment could take a fairly long time. Therefore this method
        simply initiates the VM deployment process and returns a 'reservation_id'
        value, without waiting for the VMs to start up. The returned 'reservation_id'
        can be passed into the describe_instances method of this class to check
        the status of the deployment process.

        Arguments:
            - parameters    A parameter map containing the keys 'infrastructure',
                            'num_vms' and any other cloud platform specific
                            parameters.
            - secret        A previously established secret

        Returns:
            If the secret is valid and all the required parameters are available in
            the input parameter map, this method will return a dictionary containing
            a special 'reservation_id' key. If tje secret is invalid or a required
            parameter is missing, this method will return a different map with the
            key 'success' set to False and 'reason' set to a simple error message.
        """
        print 'Received a request to run instances.'

        if self.secret != secret:
            print 'Incoming secret', secret, 'does not match the current secret', \
                self.secret, '- Rejecting request.'
            return self.__generate_response(False, REASON_BAD_SECRET)

        print 'Request parameters are', str(parameters)
        for param in RUN_INSTANCES_REQUIRED_PARAMS:
            if not utils.has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        num_vms = int(parameters[PARAM_NUM_VMS])
        infrastructure = parameters[PARAM_INFRASTRUCTURE]
        agent = self.agent_factory.create_agent(infrastructure)
        status, reason = agent.has_required_parameters(parameters, BaseAgent.OPERATION_RUN)
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
        thread.start_new_thread(self.__spawn_vms, (agent, num_vms, parameters, reservation_id))
        print 'Successfully started request',  reservation_id, '.'
        return self.__generate_response(True, REASON_NONE, { 'reservation_id' : reservation_id })

    def terminate_instances(self, parameters, secret):
        if self.secret != secret:
            return self.__generate_response(False, REASON_BAD_SECRET)

        for param in TERMINATE_INSTANCES_REQUIRED_PARAMS:
            if not utils.has_parameter(param, parameters):
                return self.__generate_response(False, 'no ' + param)

        infrastructure = parameters[PARAM_INFRASTRUCTURE]
        agent = self.agent_factory.create_agent(infrastructure)
        status, reason = agent.has_required_parameters(parameters, BaseAgent.OPERATION_TERMINATE)
        if not status:
            return self.__generate_response(False, reason)

        thread.start_new_thread(self.__kill_vms, (agent, parameters))
        return self.__generate_response(True, REASON_NONE)

    def __spawn_vms(self, agent, num_vms, parameters, reservation_id):
        if num_vms < 0:
            return [], [], []
        agent.set_environment_variables(parameters, '1')
        security_configured = agent.configure_instance_security(parameters)
        ids, public_ips, private_ips = agent.run_instances(num_vms, parameters, security_configured)
        self.reservations[reservation_id]["state"] = "running"
        self.reservations[reservation_id]["vm_info"] = {
            "public_ips" : public_ips,
            "private_ips" : private_ips,
            "instance_ids" : ids
        }
        print "Successfully finished request {0}.".format(reservation_id)

    def __kill_vms(self, agent, parameters):
        agent.set_environment_variables(parameters, '1')
        agent.terminate_instances(parameters)

    def __generate_response(self, status, msg, extra = None):
        response = { 'success' : status, 'reason' : msg }
        if extra is not None:
            for key, value in extra.items():
                response[key] = value
        return response