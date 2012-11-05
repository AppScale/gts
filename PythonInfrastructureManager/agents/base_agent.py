from os import environ

__author__ = 'hiranya'

class BaseAgent:

    def set_environment_variables(self, variables, cloud_num):
        prefix = 'CLOUD' + str(cloud_num) + '_'
        for key, value in variables.items():
            if key.startswith(prefix):
                environ[key[len(prefix):]] = value

    def configure_instance_security(self, parameters):
        raise NotImplementedError

    def describe_instances(self, parameters):
        raise NotImplementedError

    def run_instances(self, count, parameters):
        raise NotImplementedError

    def terminate_instances(self, parameters):
        raise NotImplementedError

    def has_required_parameters(self, parameters):
        return True, 'none'