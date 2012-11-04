from os import environ

__author__ = 'hiranya'

class InfrastructureAgent:

    def set_environment_variables(self, variables, cloud_num):
        prefix = 'CLOUD' + str(cloud_num) + '_'
        for key, value in variables.items():
            if key.startswith(prefix):
                environ[key[len(prefix):]] = value

    def spawn_vms(self, parameters):
        raise NotImplementedError