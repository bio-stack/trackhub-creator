# 
# Author    : Manuel Bernal Llinares
# Project   : trackhub-creator
# Timestamp : 01-07-2017 23:11
# ---
# © 2017 Manuel Bernal Llinares <mbdebian@gmail.com>
# All rights reserved.
# 

"""
This module implements the pipeline for exporting PRIDE Cluster to files using cluster-file-exporter, it will include
PoGo formatted files for its later use
"""

# TODO - Refactor-out the part that runs pogo for a .pogo file for the given parameters

import os
import time
import subprocess
# App imports
import config_manager
import ensembl.service
import ensembl.data_downloader
import trackhub.models as trackhubs
import trackhub.registry as trackhub_registry
from pogo.models import PogoRunResult
from toolbox import general as general_toolbox
from . import exceptions as pipeline_exceptions
from pipelines.template_pipeline import PogoBasedPipelineDirector, DirectorConfigurationManager

# Globals
__configuration_file = None
__pipeline_arguments = None
__pipeline_director = None


def set_configuration_file(config_file):
    global __configuration_file
    if __configuration_file is None:
        __configuration_file = config_file
    return __configuration_file


def set_pipeline_arguments(pipeline_arguments):
    global __pipeline_arguments
    if __pipeline_arguments is None:
        __pipeline_arguments = pipeline_arguments
    return __pipeline_arguments


def get_pipeline_director():
    global __pipeline_director
    if __pipeline_director is None:
        __pipeline_director = PrideClusterExporter(config_manager.read_config_from_file(__configuration_file),
                                                   __configuration_file,
                                                   __pipeline_arguments)
    return __pipeline_director


def get_pipeline_arguments():
    return __pipeline_arguments


class ConfigManager(DirectorConfigurationManager):
    # Command line arguments for this pipeline look like
    #   # Root folder for all versions of pride cluster trackhubs, where this pipeline will build the new one
    #   folder_pride_cluster_trackhubs=/wherever/path
    #   # External URL where to build the final URL to the newly built trackhub
    #   url_pride_cluster_trackhubs=http://whatever.co.uk/.../path
    #   # Trackhub registry URL, if not specified, the default URL from the trackhub service will be used
    #   trackhub_registry_url=https://www.trackhubregistry.org
    #   # Trackhub registry credentials
    #   trackhub_registry_username=username
    #   trackhub_registry_password=password
    #   # Testing mode flag
    #   running_mode=test
    #   # Name of the script to use for synchronization of the file system
    #   script_name_filesystem_sync=sync_data.sh
    #   # Boolean to tell the pipeline whether running the synchronization or not (default: yes). Values: yes/no
    #   do_sync=yes
    #   # Boolean to tell the pipeline whether tu publish the trackhub or not (default: yes). Values: yes/no
    #   do_register_trackhub=yes

    # Configuration keys for cluster-file-exporter
    _CONFIG_CLUSTER_FILE_EXPORTER_WORKING_SUBDIR = "cluster-file-exporter"
    _CONFIG_CLUSTER_FILE_EXPORTER_BIN_SUBFOLDER = "cluster-file-exporter"
    _CONFIG_CLUSTER_FILE_EXPORTER_JAR_FILE_NAME = "cluster-file-exporter.jar"
    # Command line arguments
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_FOLDER_PRIDE_CLUSTER_TRACKHUBS = 'folder_pride_cluster_trackhubs'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_URL_PRIDE_CLUSTER_TRACKHUBS = 'url_pride_cluster_trackhubs'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_URL = 'trackhub_registry_url'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_USERNAME = 'trackhub_registry_username'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_PASSWORD = 'trackhub_registry_password'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_RUNNING_MODE = 'running_mode'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_SCRIPT_NAME_FILESYSTEM_SYNC = 'script_name_filesystem_sync'
    _CONFIG_COMMAND_LINE_ARGUMENT_DEFAULT_VALUE_SCRIPT_NAME_FILESYSTEM_SYNC = 'filsystem_sync.sh'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_SYNC = 'do_sync'
    _CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_REGISTER_TRACKHUB = 'do_register_trackhub'
    # Running modes
    RUNNING_MODE_TEST = 'test'
    RUNNING_MODE_DEFAULT = 'default_running_mode'
    # Pipeline subfolders
    _CONFIG_PIPELINE_SUBFOLDER_SCRIPTS = 'pride-cluster-export'

    def __init__(self, configuration_object, configuration_file, pipeline_arguments):
        super(ConfigManager, self).__init__(configuration_object, configuration_file, pipeline_arguments)
        # Lazy Process command line arguments (e.g. pride cluster default trackhub root folder)
        self.__running_mode = None

    def __get_path_pipeline_scripts_folder(self):
        return os.path.join(config_manager.get_app_config_manager().get_folder_scripts(),
                            self._CONFIG_PIPELINE_SUBFOLDER_SCRIPTS)

    def _get_allowed_configuration_keys(self):
        return {self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_FOLDER_PRIDE_CLUSTER_TRACKHUBS,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_URL_PRIDE_CLUSTER_TRACKHUBS,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_URL,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_USERNAME,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_PASSWORD,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_RUNNING_MODE,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_SCRIPT_NAME_FILESYSTEM_SYNC,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_SYNC,
                self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_REGISTER_TRACKHUB}

    def get_folder_pride_cluster_trackhubs(self):
        return self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_FOLDER_PRIDE_CLUSTER_TRACKHUBS)

    def get_url_pride_cluster_trackhubs(self):
        return self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_URL_PRIDE_CLUSTER_TRACKHUBS)

    def get_trackhub_registry_url(self):
        return self._get_value_for_pipeline_argument_key(self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_URL)

    def get_trackhub_registry_username(self):
        return self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_USERNAME)

    def get_trackhub_registry_password(self):
        return self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_TRACKHUB_REGISTRY_PASSWORD)

    def get_running_mode(self):
        if not self.__running_mode:
            if self._get_value_for_pipeline_argument_key(
                    self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_RUNNING_MODE) == self.RUNNING_MODE_TEST:
                self.__running_mode = self.RUNNING_MODE_TEST
                self._logger.info("This pipeline is RUNNING IN 'TEST' MODE")
            else:
                self._logger.info("This pipeline IS RUNNING IN 'DEFAULT' MODE - provided '{}' as parameter".format(
                    self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_RUNNING_MODE))
                self.__running_mode = self.RUNNING_MODE_DEFAULT
        return self.__running_mode

    def get_path_script_filesystem_sync(self):
        script_name = self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_SCRIPT_NAME_FILESYSTEM_SYNC,
            default=self._CONFIG_COMMAND_LINE_ARGUMENT_DEFAULT_VALUE_SCRIPT_NAME_FILESYSTEM_SYNC)
        return os.path.join(self.__get_path_pipeline_scripts_folder(),
                            script_name)

    def is_do_sync(self):
        return (self._get_value_for_pipeline_argument_key(self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_SYNC, 'yes')
                == 'yes')

    def is_do_register_trackhub(self):
        return (self._get_value_for_pipeline_argument_key(
            self._CONFIG_COMMAND_LINE_ARGUMENT_KEY_DO_REGISTER_TRACKHUB, 'yes') == 'yes')

    def get_cluster_file_exporter_version_parameter(self):
        """
        This method computes the 'version' parameter value for running pride cluster-file-exporter software, it usually
        looks like '2016-05'.

        This value is being computed here in case I want to make it either a configuration parameter or a command line
        argument
        :return: the 'version' parameter value to use for running pride cluster-file-exporter
        """
        return "{}-{:02}".format(time.gmtime().tm_year, time.gmtime().tm_mon)

    def get_cluster_file_exporter_destination_folder(self):
        """
        Get the destination folder for the cluster file exporter result files, it will typically be a subfolder of the
        current running session working directory.

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: destination folder for pride cluster-file-exporter result files
        """
        destination_folder = os.path.join(config_manager.get_app_config_manager().get_session_working_dir(),
                                          self._CONFIG_CLUSTER_FILE_EXPORTER_WORKING_SUBDIR)
        # Make sure the folder is there
        general_toolbox.check_create_folders([destination_folder])
        return destination_folder

    def get_cluster_file_exporter_quality_parameter(self):
        """
        Get the value for the 'quality' parameter of 'cluster-file-exporter'

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: 'quality' parameter value for running pride cluster-file-exporter
        """
        return '2'

    def get_cluster_file_exporter_java_max_memory(self):
        """
        Get the maximum amount of memory we want Java to use for running pride cluster-file-exporter

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: maximum amount of memory to append to -Xmx java parameter
        """
        return '12G'

    def get_cluster_file_exporter_jar_path(self):
        """
        Get the path to cluster-file-exporter jar file for running the software

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: cluster-file-exporter jar file path
        """
        return os.path.join(config_manager.get_app_config_manager().get_folder_bin(),
                            os.path.join(self._CONFIG_CLUSTER_FILE_EXPORTER_BIN_SUBFOLDER,
                                         self._CONFIG_CLUSTER_FILE_EXPORTER_JAR_FILE_NAME))

    def get_cluster_file_exporter_output_log_file_path(self):
        """
        Get the path to the file where all output from running cluster-file-exporter will be dumped to.

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: cluster-file-exporter output log file path
        """
        return os.path.join(self.get_cluster_file_exporter_destination_folder(),
                            "output.log")

    def get_cluster_file_exporter_run_timeout(self):
        """
        Get how much time, in seconds, to wait before considering the run of cluster-file-exporter overtimed.

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: timeout for cluster-file-exporter command
        """
        return 7200

    def get_cluster_file_exporter_result_file_name_prefix(self):
        """
        Get the prefix cluster-file-exporter uses for result file names.

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: file name prefix for cluster-file-exporter result files
        """
        return "pride_cluster_peptides_"

    def get_cluster_file_exporter_result_file_extension(self):
        """
        Get the result file extension used in the files produced by the cluster-file-exporter

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: cluster-file-exporter result file extension
        """
        return "tsv"

    def get_cluster_file_exporter_pogo_file_extension(self):
        """
        Get the file extension for the pogo files produced by the cluster-file-exporter

        This is computed here just in case I want to make it either a configuration parameter or a command line argument
        in the near future
        :return: cluster-file-exporter 'pogo' file extension
        """
        return "pogo"

    def get_filesystem_sync_run_timeout(self):
        """
        Maximum amount of time we should wait when running the Filesystem Synchronization script
        :return: time out in seconds
        """
        return 300

    def get_pride_cluster_description_url(self):
        # Default PRIDE Cluster URL
        return 'https://www.ebi.ac.uk/pride/cluster/#/'


class PrideClusterExporter(PogoBasedPipelineDirector):
    __CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_POGO_FILE_PATH = 'pogo_file_path'
    __CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_PRIDE_CLUSTER_FILE_PATH = 'pride_cluster_file_path'
    __CLUSTER_FILE_EXPORTER_TAXONOMY_KEY_ALL = 'all'

    def __init__(self, configuration_object, configuration_file, pipeline_arguments):
        runner_id = "{}-{}".format(__name__, time.time())
        super(PrideClusterExporter, self).__init__(runner_id)
        self.__config_manager = ConfigManager(configuration_object, configuration_file, pipeline_arguments)
        self.__trackhub_registry_service = None
        self.__trackhub_destination_folder = None

    def _get_configuration_manager(self):
        return self.__config_manager

    def __map_cluster_file_exporter_result_files(self):
        cluster_file_exporter_folder = self._get_configuration_manager().get_cluster_file_exporter_destination_folder()
        # Prepare empty result map
        cluster_file_exporter_result_mapping = {}
        for root, dirs, files in \
                os.walk(cluster_file_exporter_folder):
            for file in files:
                if file.startswith(
                        self._get_configuration_manager().get_cluster_file_exporter_result_file_name_prefix()):
                    self._get_logger().info("Mapping result file '{}'".format(file))
                    result_file_path = os.path.join(cluster_file_exporter_folder, file)
                    # Taxonomy corner case 'pride_cluster_peptides_ALL.tsv'
                    result_file_taxonomy = self.__CLUSTER_FILE_EXPORTER_TAXONOMY_KEY_ALL
                    if 'ALL' not in file:
                        result_file_taxonomy = \
                            file.split(self._get_configuration_manager()
                                       .get_cluster_file_exporter_result_file_name_prefix())[1].split('_')[0]
                    result_file_extension = file[file.rfind('.') + 1:]
                    # Check the taxonomy for the result map
                    if result_file_taxonomy not in cluster_file_exporter_result_mapping:
                        cluster_file_exporter_result_mapping[result_file_taxonomy] = {}
                    # Check the file extension - cluster-file-exporter result file
                    if result_file_extension == self._get_configuration_manager() \
                            .get_cluster_file_exporter_result_file_extension():
                        if self.__CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_PRIDE_CLUSTER_FILE_PATH in \
                                cluster_file_exporter_result_mapping[result_file_taxonomy]:
                            self._get_logger().error("DUPLICATED entry for file '{}'".format(file))
                            return None
                        cluster_file_exporter_result_mapping[result_file_taxonomy][
                            self.__CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_PRIDE_CLUSTER_FILE_PATH] = result_file_path
                    # Check the file extension - cluster-file-exporter PoGo file
                    if result_file_extension == self._get_configuration_manager() \
                            .get_cluster_file_exporter_pogo_file_extension():
                        if self.__CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_POGO_FILE_PATH in \
                                cluster_file_exporter_result_mapping[result_file_taxonomy]:
                            self._get_logger().error("DUPLICATED entry for file '{}'".format(file))
                            return None
                        cluster_file_exporter_result_mapping[result_file_taxonomy][
                            self.__CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_POGO_FILE_PATH] = result_file_path
                else:
                    self._get_logger().warning("Ignoring cluster-file-exporter non-result file '{}'".format(file))
        return cluster_file_exporter_result_mapping

    def __run_cluster_file_exporter(self):
        # time java -Xmx12G -jar
        #   cluster-file-exporter-1.0.0-SNAPSHOT.jar
        #   -out ~/tmp/pride-cluster/with_pogo
        #   -version 2016-05
        #   -quality 2
        #   -filter_out_multitaxonomies
        #   -include_pogo_export
        #   > output.log 2>&1 ; cd ..
        # Build cluster-file-exporter command
        cluster_file_exporter_command = \
            "time java -Xmx{} -jar {} -out {} -version {} -quality {} " \
            "-filter_out_multitaxonomies -include_pogo_export > {} 2>&1".format(
                self._get_configuration_manager().get_cluster_file_exporter_java_max_memory(),
                self._get_configuration_manager().get_cluster_file_exporter_jar_path(),
                self._get_configuration_manager().get_cluster_file_exporter_destination_folder(),
                self._get_configuration_manager().get_cluster_file_exporter_version_parameter(),
                self._get_configuration_manager().get_cluster_file_exporter_quality_parameter(),
                self._get_configuration_manager().get_cluster_file_exporter_output_log_file_path()
            )
        self._get_logger().info("cluster-file-exporter command: '{}'".format(cluster_file_exporter_command))
        # Run cluster file exporter
        cluster_file_exporter_subprocess = subprocess.Popen(cluster_file_exporter_command,
                                                            shell=True)
        try:
            stdout, stderr = \
                cluster_file_exporter_subprocess.communicate(
                    timeout=self._get_configuration_manager().get_cluster_file_exporter_run_timeout())
        except subprocess.TimeoutExpired as e:
            self._get_logger().error("TIMEOUT ({} seconds) while running cluster-file-exporter, KILLING subprocess")
            cluster_file_exporter_subprocess.kill()
            stdout, stderr = cluster_file_exporter_subprocess.communicate()
            return False
        if cluster_file_exporter_subprocess.poll() and (cluster_file_exporter_subprocess.returncode != 0):
            self._get_logger().error("An ERROR occurred while running cluster-file-exporter")
            return False
        return True

    def __runmode_test_run_cluster_file_exporter(self):
        """
        This method is a helper that I'm using for building this pipeline, it is not even clear whether this pipeline
        will have a "testing / development mode" where the most expensive parts of it are dummied, that's why I don't
        think the code will stay, thus, I'm not spending much time on getting this code fit in the software in a
        sensible way
        :return: True if success on preparing the dummy data, False otherwise
        """
        cluster_file_exporter_destination_folder = self \
            ._get_configuration_manager() \
            .get_cluster_file_exporter_destination_folder()
        rsync_source_folder = os.path.join(config_manager.get_app_config_manager().get_folder_resources(),
                                           os.path.join("tests",
                                                        "cluster-file-exporter"))
        # Rsync the dummy data into the destination folder
        rsync_command = "rsync -vah --progress --stats {}/ {}/" \
            .format(rsync_source_folder, cluster_file_exporter_destination_folder)
        rsync_subprocess = subprocess.Popen(rsync_command, shell=True)
        try:
            # TODO - WARNING - OMG! Magic number there!
            stdout, stderr = rsync_subprocess.communicate(timeout=600)
        except subprocess.TimeoutExpired as e:
            self._get_logger().error(
                "TIMEOUT error while rsyncing dummy cluster-file-exporter data, KILLING subprocess")
            rsync_subprocess.kill()
            stdout, stderr = rsync_subprocess.wait()
            return False
        return True

    def __run_pogo_on_pride_cluster_file_exporter_results(self, cluster_file_exporter_result_mapping):
        # Prepare results object, it is a map like (taxonomy_id, PogoRunResult)
        pogo_run_results = {}
        # Get an instance of the Ensembl data downloader
        ensembl_downloader_service = ensembl.data_downloader.get_data_download_service()
        for taxonomy in cluster_file_exporter_result_mapping:
            if taxonomy == self.__CLUSTER_FILE_EXPORTER_TAXONOMY_KEY_ALL:
                self._get_logger().warning("SKIPPING PoGo for taxonomy {}".format(taxonomy))
                continue
            # PoGo input file
            pogo_parameter_file_input = cluster_file_exporter_result_mapping[taxonomy][
                self.__CLUSTER_FILE_EXPORTER_RESULT_MAP_KEY_POGO_FILE_PATH]
            # PoGo parameter protein sequence file
            pogo_parameter_protein_sequence_file_path = self._get_pogo_protein_sequence_file_path_for_taxonomy(
                taxonomy)
            if not pogo_parameter_protein_sequence_file_path:
                self._get_logger().warning("SKIP TAXONOMY ID #{}, not found on Ensembl, for PoGo file '{}'"
                                           .format(taxonomy, pogo_parameter_file_input))
                continue
            # PoGo parameter GTF file
            pogo_parameter_gtf_file_path = self._get_pogo_gtf_file_path_for_taxonomy(taxonomy)
            if not pogo_parameter_gtf_file_path:
                self._get_logger().error("GTF file NOT FOUND to use with PoGo")
                return False
            # Prepare PoGo run command
            pogo_command = "time {} -species {} -fasta {} -gtf {} -in {}" \
                .format(config_manager.get_app_config_manager().get_pogo_binary_file_path(),
                        taxonomy,
                        pogo_parameter_protein_sequence_file_path,
                        pogo_parameter_gtf_file_path,
                        pogo_parameter_file_input)
            # Log how we are going to run PoGo
            self._get_logger().info("Running PoGo on input file '{}', "
                                    "with protein sequence file '{}' and GTF file '{}'. PoGo command '{}'"
                                    .format(pogo_parameter_file_input,
                                            pogo_parameter_protein_sequence_file_path,
                                            pogo_parameter_gtf_file_path,
                                            pogo_command))
            pogo_command_subprocess = subprocess.Popen(pogo_command, shell=True)
            # Run PoGo
            # TODO - This is a place for future improvement by running PoGo in parallel for all the files. Obviously,
            # TODO - I haven't done it straight away because the right way to do it, as PoGo is very memory hungry,
            # TODO - is to distribute the PoGo runs across multiple nodes, and this kind of means using our LSF
            # TODO - facilities, that means the PoGo run should be encapsulated as a 'bsub' job, and the pipeline should
            # TODO - handle the submission of the jobs and their possible outcomes and status states. A complex task for
            # TODO - a pipeline that it is not even clear yet how it's going to do many of the things it is going to do
            try:
                stdout, stderr = pogo_command_subprocess \
                    .communicate(timeout=config_manager.get_app_config_manager().get_pogo_run_timeout())
            except subprocess.TimeoutExpired as e:
                self._get_logger().error("TIMEOUT ERROR while running PoGo on input file '{}', "
                                         "with protein sequence file '{}' and GTF file '{}' ---> Command: {}"
                                         .format(pogo_parameter_file_input,
                                                 pogo_parameter_protein_sequence_file_path,
                                                 pogo_parameter_gtf_file_path,
                                                 pogo_command))
                pogo_command_subprocess.kill()
                stdout, stderr = pogo_command_subprocess.communicate()
                # TODO - How to signal this error? we just skip the file? It looks like it
                continue
            if pogo_command_subprocess.poll() and (pogo_command_subprocess.returncode != 0):
                # ERROR
                self._get_logger().error("ERROR running PoGo on input file '{}', "
                                         "with protein sequence file '{}' and GTF file '{}' ---> Command: {}"
                                         .format(pogo_parameter_file_input,
                                                 pogo_parameter_protein_sequence_file_path,
                                                 pogo_parameter_gtf_file_path,
                                                 pogo_command))
                # TODO - We skip the file?
                continue
            # TODO - Successful PoGo run
            if taxonomy in pogo_run_results:
                self._get_logger().error("DUPLICATED TAXONOMY ENTRY ERROR "
                                         "when registering successful run of PoGo on input file '{}', "
                                         "with protein sequence file '{}' and GTF file '{}' ---> Command: {}"
                                         .format(pogo_parameter_file_input,
                                                 pogo_parameter_protein_sequence_file_path,
                                                 pogo_parameter_gtf_file_path,
                                                 pogo_command))
                # TODO - Let me guess! we skip this entry then, even if it's been successful because it is a duplicated
                # TODO - taxonomy, which is a weird error that I don't think will happen
                continue
            # Build the pogo result object
            pogo_run_results_object = PogoRunResult(taxonomy,
                                                    pogo_parameter_file_input,
                                                    pogo_parameter_protein_sequence_file_path,
                                                    pogo_parameter_gtf_file_path)
            # Add the result object to the results
            pogo_run_results[taxonomy] = pogo_run_results_object
        # Return the results for running PoGo for the given cluster-file-exporter result files
        return pogo_run_results

    def __get_trackhub_builder(self, trackhub_descriptor):
        # TODO - Implement more complex logic for instantiating a trackhub builder, e.g. setting up the trackhub
        # TODO - destination folder from whatever comes in as a command line parameter
        return trackhubs.SimpleTrackHubBuilder(trackhub_descriptor)

    def __get_trackhub_descriptor(self):
        # TODO - Some of these values are hardcoded here, but they could be parameterized later if needed
        trackhub_title = "PRIDE Cluster Release {}" \
            .format(self._get_configuration_manager().get_cluster_file_exporter_version_parameter())
        trackhub_short_label = "PRIDE Cluster latest release."
        trackhub_long_label = "PRIDE Cluster clusters all MS/MS spectra submitted to the PRIDE Archive repository " \
                              "using spectrum clustering algorithms."
        trackhub_email = "pride-support@ebi.ac.uk"
        trackhub_description_url = self._get_configuration_manager().get_pride_cluster_description_url()
        # Create the trackhub descriptor
        return trackhubs.TrackHub(trackhub_title,
                                  trackhub_short_label,
                                  trackhub_long_label,
                                  trackhub_email,
                                  trackhub_description_url)

    def __populate_assemblies(self, trackhub_builder, pogo_run_results):
        for taxonomy in pogo_run_results:
            ensembl_species_entry = \
                ensembl.service.get_service().get_species_data_service().get_species_entry_for_taxonomy_id(taxonomy)
            if not ensembl_species_entry:
                # This is kind of non-sense because PoGo run results only contain results for taxonomies that are on
                # Ensembl, but just in case, if it ever happens, it will be logged
                self._get_logger().warning("Ensembl has no entry for taxonomy '{}', SKIPPING".format(taxonomy))
                continue
            genome_assembly = ensembl_species_entry.get_assembly()
            self._get_logger().info("Populating Assembly '{}' for Taxonomy '{}'".format(genome_assembly, taxonomy))
            # TODO - How are we going to annotate these tracks? We need a meeting on this

            # Main .bed track to assembly
            main_bed_file_path = pogo_run_results[taxonomy].get_pogo_result_main_bed_file_path()
            track_main_bed_file = trackhubs.BaseTrack("{}".format(ensembl_species_entry.get_display_name()),
                                                      "PRIDE Cluster Track - '{}'".format(
                                                          ensembl_species_entry.get_display_name()),
                                                      "PRIDE Cluster Track for main .bed file, species '{}'".format(
                                                          ensembl_species_entry.get_display_name()))
            track_main_bed_file.set_big_data_url(main_bed_file_path)
            track_main_bed_file.set_type(main_bed_file_path)
            self._get_logger().debug("Assembly '{}', compiling main .bed track information".format(genome_assembly))

            # Main PTM .bed track to assembly
            main_ptm_bed_file_path = pogo_run_results[taxonomy].get_pogo_result_main_ptm_bed_file_path()
            track_main_bed_with_ptm_file = trackhubs.BaseTrack(
                "{} with PTMs".format(ensembl_species_entry.get_display_name()),
                "PRIDE Cluster Track (with PTMs) - '{}'".format(
                    ensembl_species_entry.get_display_name()),
                "PRIDE Cluster Track for main .bed file with PTMs, species '{}'"
                    .format(
                    ensembl_species_entry.get_display_name()))
            track_main_bed_with_ptm_file.set_big_data_url(main_ptm_bed_file_path)
            track_main_bed_with_ptm_file.set_type(main_ptm_bed_file_path)
            self._get_logger().debug("Assembly '{}', compiling main .bed PTM track information".format(genome_assembly))
            # Add tracks
            self._get_logger().debug(
                "Assembly '{}', adding main .bed track information, main .bed file '{}'"
                    .format(genome_assembly,
                            track_main_bed_file.get_big_data_url()))
            trackhub_builder.add_track_to_assembly(genome_assembly, track_main_bed_file)

            self._get_logger().debug(
                "Assembly '{}', adding main .bed with PTM track information, main .bed with PTM file '{}'"
                    .format(genome_assembly,
                            track_main_bed_with_ptm_file.get_big_data_url()))
            trackhub_builder.add_track_to_assembly(genome_assembly, track_main_bed_with_ptm_file)
            self._get_logger().debug("Assembly '{}', tracks added to the assembly".format(genome_assembly))

        # I don't need to, but it makes sense to do it
        return trackhub_builder

    def __get_trackhub_exporter(self):
        self._get_logger().info("Default trackhub exporter - 'TrackHubExporterPrideClusterFtp'")
        return trackhubs.TrackHubExporterPrideClusterFtp()

    def __prepare_trackhub_destination_folder(self, trackhub_exporter):
        if not self.__trackhub_destination_folder:
            # Check if anything was specified
            if self._get_configuration_manager().get_folder_pride_cluster_trackhubs():
                # The destination folder will be a subfolder there
                self.__trackhub_destination_folder = os.path.join(
                    self._get_configuration_manager().get_folder_pride_cluster_trackhubs(),
                    self._get_configuration_manager().get_cluster_file_exporter_version_parameter())
            else:
                # Set the default trackhub destination folder by default
                self.__trackhub_destination_folder = os.path.join(
                    trackhub_exporter.track_hub_destination_folder,
                    self._get_configuration_manager().get_cluster_file_exporter_version_parameter())
            # Make sure the destination folder is there
            general_toolbox.check_create_folders([self.__trackhub_destination_folder])
            general_toolbox.create_latest_symlink_overwrite(self.__trackhub_destination_folder)
            # Set the destination folder for the exporter of the trackhub
            trackhub_exporter.track_hub_destination_folder = self.__trackhub_destination_folder
        self._get_logger().info("PRIDE Cluster trackhub destination folder at '{}'")
        return self.__trackhub_destination_folder

    def __export_trackhub_to_destination_folder(self, trackhub_builder, trackhub_exporter):
        self._get_logger().info("Exporting PRIDE Cluster Trackhub to destination '{}'".format(
            trackhub_exporter.track_hub_destination_folder))
        trackhub_builder.accept_exporter(trackhub_exporter)
        self._get_logger().info(
            "PRIDE Cluster Trackhub export COMPLETED, at '{}'".format(trackhub_exporter.track_hub_destination_folder))

    def __sync_filesystem(self, trackhub_exporter):
        if self._get_configuration_manager().is_do_sync():
            # Sync script parameters
            sync_script_launcher = self._get_configuration_manager().get_path_script_filesystem_sync()
            app_root_dir = config_manager.get_app_config_manager().get_application_root_folder()
            source_trackhub_container_folder = os.path.dirname(trackhub_exporter.track_hub_destination_folder)
            source_trackhub_folder = trackhub_exporter.track_hub_destination_folder
            # Build the synchronization command
            sync_command = "{} {} {} {}".format(sync_script_launcher,
                                                app_root_dir,
                                                source_trackhub_container_folder,
                                                source_trackhub_folder)
            self._get_logger().info("Filesystem synchronization command '{}'".format(sync_command))
            sync_subprocess = subprocess.Popen(sync_command, shell=True)
            stdout = ''
            stderr = ''
            try:
                stdout, stderr = sync_subprocess \
                    .communicate(timeout=self._get_configuration_manager().get_filesystem_sync_run_timeout())
            except subprocess.TimeoutExpired as e:
                exception_message = "TIMEOUT ERROR while running Filesystem synchronization script '{}'," \
                                    " Command: '{}'\n" \
                                    "STDOUT: '{}'\n" \
                                    "STDERR: '{}'" \
                    .format(self._get_configuration_manager().get_path_script_filesystem_sync(),
                            sync_command,
                            stdout,
                            stderr)
                self._get_logger().error(exception_message)
                sync_subprocess.kill()
                stdout, stderr = sync_subprocess.communicate()
                raise pipeline_exceptions.PipelineDirectorException(exception_message) from e
            if sync_subprocess.poll() and (sync_subprocess.returncode != 0):
                error_msg = "ERROR while running Filesystem synchronization script '{}'," \
                            " Command: '{}'\n" \
                            "STDOUT: '{}'\n" \
                            "STDERR: '{}'" \
                    .format(self._get_configuration_manager().get_path_script_filesystem_sync(),
                            sync_command,
                            stdout,
                            stderr)
                self._get_logger().error(error_msg)
                raise pipeline_exceptions.PipelineDirectorException(error_msg)

    def __get_trackhub_public_url(self, trackhub_exporter):
        # Check if we have been given the public base URL as a parameter
        trackhub_public_url = ""
        if self._get_configuration_manager().get_url_pride_cluster_trackhubs():
            # To calculate the relative path, we remove the root part of the trackhub folder path,
            # e.g. '/nfs/pride/pride-cluster/trackhubs' from '/nfs/pride/pride-cluster/trackhubs/2017-08'
            # to obtain '/2017-08' that we can attach to the end of the base public URL for the trackhubs
            relative_path = ''
            # Default base folder is the parent folder of the trackhub destination folder
            base_folder = os.path.dirname(self.__trackhub_destination_folder)
            if self._get_configuration_manager().get_folder_pride_cluster_trackhubs():
                # If a pride cluster folder has been specified, we do it relative to that
                base_folder = self._get_configuration_manager().get_folder_pride_cluster_trackhubs()
            relative_path = self.__trackhub_destination_folder.replace(base_folder, '')
            # URL to the hub.txt file within the root of the trackhub
            trackhub_public_url = "{}{}/{}".format(self._get_configuration_manager().get_url_pride_cluster_trackhubs(),
                                                   relative_path,
                                                   os.path.basename(trackhub_exporter
                                                                    .export_summary
                                                                    .track_hub_descriptor_file_path))
        self._get_logger().info("Trackhub Public URL is '{}'".format(trackhub_public_url))
        return trackhub_public_url

    def __get_trackhub_registration_service(self):
        # Cache the registry service instance, we only need one
        if not self.__trackhub_registry_service:
            self.__trackhub_registry_service = \
                trackhub_registry.TrackhubRegistryService(
                    self._get_configuration_manager().get_trackhub_registry_username(),
                    self._get_configuration_manager().get_trackhub_registry_password())
            # Set the registry base URL, if set, use default otherwise
            if self._get_configuration_manager().get_trackhub_registry_url():
                self.__trackhub_registry_service.trackhub_registry_base_url = \
                    self._get_configuration_manager().get_trackhub_registry_url()
        return self.__trackhub_registry_service

    def __register_trackhub(self, trackhub_builder, trackhub_exporter):
        if self.__get_trackhub_public_url(trackhub_exporter) == '':
            self._get_logger().warning("THIS TRACKHUB WILL NOT BE PUBLISHED, "
                                       "a trackhub public URL could not be worked out")
        else:
            if self._get_configuration_manager().is_do_register_trackhub():
                # Build the description the trackhub registration service needs
                self._get_logger().debug("Building trackhub registration profile")
                trackhub_registration_profile_builder = trackhub_registry.TrackhubRegistryRequestBodyModelExporter()
                trackhub_builder.accept_exporter(trackhub_registration_profile_builder)
                trackhub_registration_profile = trackhub_registration_profile_builder.export_summary
                if trackhub_registration_profile:
                    trackhub_registration_profile.url = self.__get_trackhub_public_url(trackhub_exporter)
                    self._get_logger().debug("Trackhub '{}' registration profile built!"
                                             .format(trackhub_registration_profile.url))
                    # Register the trackhub
                    trackhub_registration_service = self.__get_trackhub_registration_service()
                    trackhub_registration_service.register_trackhub(trackhub_registration_profile)
                else:
                    error_msg = "ERROR BUILDING TRACKHUB REGISTRATION PROFILE!, the trackhub COULD NOT BE REGISTERED"
                    self._get_logger().error(error_msg)
                    raise pipeline_exceptions.PipelineDirectorException(error_msg)
            else:
                self._get_logger().warning("This session was launch with DO NOT REGISTER Trackhub flag set, "
                                           "thus, this trackhub will not be registered")

    def _run_pipeline(self):
        # Main pipeline algorithm
        self._get_logger().info("[START]---> Pipeline run")
        try:
            # I'll capture exceptions from the helpers to decide whether the pipeline is successful or not
            if self._get_configuration_manager().get_running_mode() \
                    == self._get_configuration_manager().RUNNING_MODE_TEST:
                # Run cluster-file-exporter (dummy step)
                if not self.__runmode_test_run_cluster_file_exporter():
                    return False
            else:
                # Run cluster-file-exporter (for real)
                if not self.__run_cluster_file_exporter():
                    return False
            # Process cluster-file-exporter result files
            cluster_file_exporter_result_mapping = self.__map_cluster_file_exporter_result_files()
            if not cluster_file_exporter_result_mapping:
                self._get_logger().error("ERROR processing cluster-file-exporter result files")
                return False
            self._get_logger().info("PRIDE Cluster File Exporter run completed")
            pogo_run_results = self.__run_pogo_on_pride_cluster_file_exporter_results(
                cluster_file_exporter_result_mapping)
            self._get_logger().info("PoGo results obtained for #{} taxonomies".format(len(pogo_run_results)))
            # TODO - Convert files to BigBed format, this will be addressed in the future
            # Create trackhub structure
            trackhub_builder = self.__get_trackhub_builder(self.__get_trackhub_descriptor())
            self.__populate_assemblies(trackhub_builder, pogo_run_results)
            # Compute the destination folder for this trackhub (including the 'latest' link) and prepare Destination
            # folder for this trackhub
            trackhub_exporter = self.__get_trackhub_exporter()
            self.__prepare_trackhub_destination_folder(trackhub_exporter)
            # Export trackhub to destination folder
            self.__export_trackhub_to_destination_folder(trackhub_builder, trackhub_exporter)
            # Sync Data and get public URL
            self.__sync_filesystem(trackhub_exporter)
            # Publish trackhub
            self.__register_trackhub(trackhub_builder, trackhub_exporter)
        except pipeline_exceptions.PipelineDirectorException as e:
            # It will be the helpers logging the exception
            return False
        return True


if __name__ == '__main__':
    print("ERROR: This script is part of a pipeline collection and it is not meant to be run in stand alone mode")
