# 
# Author    : Manuel Bernal Llinares
# Project   : trackhub-creator
# Timestamp : 03-07-2017 10:38
# ---
# © 2017 Manuel Bernal Llinares <mbdebian@gmail.com>
# All rights reserved.
# 

"""
This module implements en Ensembl data grabber for a given Ensembl Service instance
"""

# App imports
import config_manager
from exceptions import ConfigManagerException
from ensembl.service import Service as EnsemblService

# Common configuration for all instances of the download manager
__configuration_file = None
__data_download_service = None


def set_configuration_file(config_file):
    global __configuration_file
    if __configuration_file is None:
        __configuration_file = config_file
    return __configuration_file


def get_data_download_service():
    global __data_download_service
    if __data_download_service is None:
        __data_download_service = DataDownloadService(config_manager.read_config_from_file(__configuration_file),
                                                      __configuration_file)
    return __data_download_service


# Ensembl Data Grabbing Service configuration manager
class ConfigurationManager(config_manager.ConfigurationManager):
    # Configuration keys
    __CONFIG_KEY_DATA_DOWNLOADER = 'data_downloader'
    __CONFIG_KEY_ENSEMBL_FTP = 'ensembl_ftp'
    __CONFIG_KEY_BASE_URL = 'base_url'
    

    def __init__(self, configuration_object, configuration_file):
        super(ConfigurationManager, self).__init__(configuration_object, configuration_file)
        self.__logger = config_manager.get_app_config_manager().get_logger_for(__name__)

    def _get_logger(self):
        return self.__logger


class DataDownloadService:
    """
    This Service is in charge of grabbing data (download) from Ensembl to a local repository
    """

    def __init__(self, configuration_object, configuration_file):
        self.__logger = config_manager.get_app_config_manager().get_logger_for(__name__)
        self._get_logger().debug("Using configuration file '{}'".format(configuration_file))
        self.__config_manager = ConfigurationManager(configuration_object, configuration_file)
        # Name for the current release folder, we'll use the same for both the FTP and the local storage
        self.__folder_name_release = None
        # Name for the subfolder that contains per species fasta files
        self.__folder_name_fasta = None
        # Name for the subfolder of species folder that contains protein sequences files
        self.__folder_name_protein_sequences = None


    def _get_logger(self):
        return self.__logger


if __name__ == '__main__':
    print("ERROR: This script is part of a pipeline collection and it is not meant to be run in stand alone mode")
