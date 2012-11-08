__author__ = 'hiranya'

class BaseAgent:

    OPERATION_RUN = 'run'
    OPERATION_TERMINATE = 'terminate'

    def set_environment_variables(self, parameters, cloud_num):
        pass

    def configure_instance_security(self, parameters):
        raise NotImplementedError

    def describe_instances(self, parameters):
        raise NotImplementedError

    def run_instances(self, count, parameters, security_configured):
        raise NotImplementedError

    def terminate_instances(self, parameters):
        raise NotImplementedError

    def has_required_parameters(self, parameters, operation):
        return True, 'none'