"""
Fetch the arguments, parse the configuration and run the selected functionality
"""

import logging
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

        self.find_own_network()

    def run(self):
        """Run the tool"""
        pass

    def find_own_network(self):
        """Find own address on the default bridge network"""
        try:
            bridge = self.client.networks.get(self.BRIDGE_NETWORK_NAME, scope="local")
            self.own_ip_address = bridge.attrs["IPAM"]["Config"][0]["Gateway"]
            logging.info(
                "Own address on the '%s' network: %s",
                self.BRIDGE_NETWORK_NAME, self.own_ip_address,
            )
        except (docker.errors.NotFound, KeyError, TypeError, IndexError):
            logging.warning(
                "warning: network '%s' not recognized, own address won't be added",
                self.BRIDGE_NETWORK_NAME
            )
            self.own_ip_address = None

    def get_docker_arguments(self, volume: str = None, localdir: str = None):
        """
        Get the docker arguments for the specified command and eventually
        volume or local directory
        """

    def get_restic_arguments(self, volume: str = None, localdir: str = None):
        """
        Get the restic arguments for the specified command and eventually
        volume or local directory
        """


def run():
    """Run the tool"""
    tool = ResticTool()
    tool.setup()
    tool.run()
