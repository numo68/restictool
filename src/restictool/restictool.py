"""
Fetch the arguments, parse the configuration and run the selected functionality
"""

import logging
import os
import sys
import docker
import docker.errors

from .argument_parser import Arguments
from .configuration_parser import Configuration


class ResticTool:
    """Main interface to the dockerized restic"""

    BRIDGE_NETWORK_NAME = "bridge"
    OWN_HOSTNAME = "restic.local"

    def __init__(self):
        self.arguments = None
        self.configuration = None
        self.client = None
        self.own_ip_address = None

    def setup(self, args=None):
        """Parse the arguments and fetch the configuration"""
        self.arguments = Arguments()
        self.arguments.parse(args)

        if self.arguments.get_verbosity_level() >= 3:
            logging_level = logging.DEBUG
        elif self.arguments.get_verbosity_level() >= 2:
            logging_level = logging.INFO
        else:
            logging_level = logging.WARNING

        logging.basicConfig(level=logging_level)

        logging.info("Initializing")

        self.configuration = Configuration()
        self.configuration.load(self.arguments.tool_arguments["config"])

        self.client = docker.from_env()

    def run(self):
        """Run the tool"""
        if self.arguments.tool_arguments["subcommand"] != "check":
            self.pull_if_needed()
            self.create_directories()
            self.find_own_network()

        if self.arguments.tool_arguments["subcommand"] == "run":
            self.run_run()
        elif self.arguments.tool_arguments["subcommand"] == "backup":
            self.run_backup()
        elif self.arguments.tool_arguments["subcommand"] == "restore":
            self.run_restore()
        elif self.arguments.tool_arguments["subcommand"] == "check":
            pass
        else:
            logging.fatal(
                "Unknown command %s", self.arguments.tool_arguments["subcommand"]
            )
            sys.exit(2)

    def run_run(self):
        """Run an arbitrary restic command"""

    def run_backup(self):
        """Run the backup"""

    def run_restore(self):
        """Run the restore"""

    def find_own_network(self):
        """Find own address on the default bridge network"""
        try:
            bridge = self.client.networks.get(self.BRIDGE_NETWORK_NAME, scope="local")
            self.own_ip_address = bridge.attrs["IPAM"]["Config"][0]["Gateway"]
            logging.info(
                "Own address on the '%s' network: %s",
                self.BRIDGE_NETWORK_NAME,
                self.own_ip_address,
            )
        except (docker.errors.NotFound, KeyError, TypeError, IndexError):
            logging.warning(
                "Network '%s' not recognized, own address won't be added",
                self.BRIDGE_NETWORK_NAME,
            )
            self.own_ip_address = None

    def pull_if_needed(self):
        """Pull the image if requested"""
        if self.arguments.tool_arguments["force_pull"]:
            image = self.arguments.tool_arguments["image"].split(":")
            logging.info("Pulling image %s", self.arguments.tool_arguments["image"])
            self.client.images.pull(
                repository=image[0], tag=image[1] if len(image) > 1 else None
            )

    def create_directories(self):
        """Create directories"""
        if not os.path.exists(self.arguments.tool_arguments["cache"]):
            logging.info(
                "Creating cache directory %s", self.arguments.tool_arguments["cache"]
            )
            os.makedirs(self.arguments.tool_arguments["cache"], mode=0o755)

        if not os.path.isdir(self.arguments.tool_arguments["cache"]):
            logging.fatal(
                "Could not create cache directory %s, exiting",
                self.arguments.tool_arguments["cache"],
            )
            sys.exit(2)

        if self.arguments.tool_arguments["subcommand"] == "restore":
            if not os.path.exists(self.arguments.tool_arguments["restore"]):
                logging.info(
                    "Creating restore directory %s",
                    self.arguments.tool_arguments["restore"],
                )
                os.makedirs(self.arguments.tool_arguments["restore"], mode=0o755)

            if not os.path.isdir(self.arguments.tool_arguments["restore"]):
                logging.fatal(
                    "Could not create restore directory %s, exiting",
                    self.arguments.tool_arguments["restore"],
                )
                sys.exit(2)

    def get_docker_volume_mounts(self, volume: str = None, localdir: str = None):
        """
        Get the dict that can be used as ``volumes`` argument to run()
        """

    def get_restic_arguments(
        self, volume: str = None, localdir: str = None, forget: bool = False
    ):
        """
        Get the restic arguments for the specified command and eventually
        volume or local directory
        """
        if self.arguments.tool_arguments["subcommand"] == "run":
            pass
        elif self.arguments.tool_arguments["subcommand"] == "backup":
            pass
        elif self.arguments.tool_arguments["subcommand"] == "restore":
            pass


def run():
    """Run the tool"""
    tool = ResticTool()
    tool.setup()
    tool.run()
