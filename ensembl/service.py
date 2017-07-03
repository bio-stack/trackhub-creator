#
# Author    : Manuel Bernal Llinares
# Project   : trackhub-creator
# Timestamp : 28-06-2017 10:13
# ---
# © 2017 Manuel Bernal Llinares <mbdebian@gmail.com>
# All rights reserved.
#

"""
This module models an Ensembl service
"""

import requests
# App imports
import config_manager
import rest_toolbox
from exceptions import ConfigManagerException


# Ensembl Service is going to be a Singleton, unique for the running session
__configuration_file = None
__service_instance = None


# Ensembl Service configuration manager
class ConfigurationManager(config_manager.ConfigurationManager):
    # Configuration Keys
    _CONFIG_KEY_SERVICE = 'service'
    _CONFIG_KEY_ENSEMBL_API = 'ensembl_api'
    _CONFIG_KEY_SERVER = 'server'

    def __init__(self, configuration_object, configuration_file):
        super(ConfigurationManager, self).__init__(configuration_object, configuration_file)
        self.__logger = config_manager.get_app_config_manager().get_logger_for(__name__)

    def _get_logger(self):
        return self.__logger

    def get_api_server(self):
        self._get_logger().debug("get_api_server, from configuration object '{}'".format(self._get_configuration_object()))
        try:
            return self._get_configuration_object()[self._CONFIG_KEY_SERVICE][self._CONFIG_KEY_ENSEMBL_API][
                self._CONFIG_KEY_SERVER]
        except Exception as e:
            raise ConfigManagerException(
                "MISSING information about Ensembl '{}.{}.{}' API server in configuration file '{}'".format(
                self._CONFIG_KEY_SERVICE,
                self._CONFIG_KEY_ENSEMBL_API,
                self._CONFIG_KEY_SERVER,
                self._get_configuration_file()))


# Ensembl Service model
class Service:
    def __init__(self, configuration_object, configuration_file):
        self.__logger = config_manager.get_app_config_manager().get_logger_for(__name__)
        self._get_logger().debug("Using configuration file '{}'".format(configuration_file))
        self.__config_manager = ConfigurationManager(configuration_object, configuration_file)
        # Ensembl Release Number
        self.__release_number = None

    def _get_config_manager(self):
        return self.__config_manager

    def __request_release_number(self):
        request_url = self._get_config_manager().get_api_server() + "/info/data/?"
        current_release_data = rest_toolbox.make_rest_request(request_url)
        self._get_logger().debug("Request Release Number response from Ensembl - '{}'".format(current_release_data))
        self._get_logger().info("This session is working with Ensembl Release {}".format(current_release_data['releases'][0]))
        return current_release_data['releases'][0]

    def get_release_number(self):
        """
        Get current Ensembl Release Number
        :return: current Ensembl Release Number
        """
        if self.__release_number is None:
            self.__release_number = self.__request_release_number()
        return self.__release_number

    def _get_logger(self):
        return self.__logger


if __name__ == '__main__':
    print("ERROR: This script is part of a pipeline collection and it is not met to be run in stand alone mode")
