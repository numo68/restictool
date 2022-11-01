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

        logging.basicConfig(level=self.arguments.tool_arguments["log_level"].upper())

        logging.info("Initializing")

        self.configuration = Configuration()

        try:
            self.configuration.load(self.arguments.tool_arguments["config"])
        except ValueError as ex:
            logging.error(ex.with_traceback(None))
            sys.exit(2)

        if self.arguments.tool_arguments["subcommand"] != "check":
            self.client = docker.from_env()

    def run(self):
        """Run the tool"""
        exit_code = 0

        if self.arguments.tool_arguments["subcommand"] != "check":
            self.pull_if_needed()
            self.create_directories()
            self.find_own_network()

        if self.arguments.tool_arguments["subcommand"] == "run":
            exit_code = self.run_run()
        elif self.arguments.tool_arguments["subcommand"] == "backup":
            exit_code = self.run_backup()
        elif self.arguments.tool_arguments["subcommand"] == "restore":
            exit_code = self.run_restore()
        elif self.arguments.tool_arguments["subcommand"] == "check":
            logging.info("Configuration is valid")
        else:
            logging.fatal(
                "Unknown command %s", self.arguments.tool_arguments["subcommand"]
            )
            exit_code = 2

        if exit_code != 0:
            logging.error("restic exited with code %d", exit_code)
            sys.exit(exit_code)

    def run_run(self) -> int:
        """Run an arbitrary restic command"""
        exit_code = self.run_docker(
            command=self.get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self.get_docker_mounts()
        )

        return exit_code

    def run_backup(self) -> int:
        """Run the backup"""
        return 0

    def run_restore(self) -> int:
        """Run the restore"""
        return 0

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

    def get_docker_mounts(self, volume: str = None, localdir: tuple = None) -> dict:
        """
        Get the dict that can be used as ``volumes`` argument to run()
        """
        mounts = {}

        mounts[self.arguments.tool_arguments["cache"]] = {
            "bind": "/cache",
            "mode": "rw",
        }

        if self.arguments.tool_arguments["subcommand"] == "backup":
            if volume:
                mounts[volume] = {
                    "bind": "/volume/" + volume,
                    "mode": "rw",
                }

            if localdir:
                mounts[localdir[1]] = {
                    "bind": "/localdir/" + localdir[0],
                    "mode": "rw",
                }

        if self.arguments.tool_arguments["subcommand"] == "restore":
            mounts[self.arguments.tool_arguments["restore"]] = {
                "bind": "/target",
                "mode": "rw",
            }

        return mounts

    def get_restic_arguments(
        self, volume: str = None, localdir: str = None, forget: bool = False
    ) -> list:
        """
        Get the restic arguments for the specified command and eventually
        volume or local directory
        """
        options = ["--cache-dir", "/cache"]

        if self.arguments.tool_arguments["subcommand"] == "run":
            options.extend(self.configuration.get_options())
        elif self.arguments.tool_arguments["subcommand"] == "backup":
            options.extend(["--host", self.configuration.hostname])
            options.extend(self.configuration.get_options(volume, localdir, forget))
            if forget:
                if self.arguments.tool_arguments["prune"]:
                    options.append("--prune")
                options.append("forget")
            else:
                assert volume or localdir
                options.append("backup")
                if volume:
                    options.append(f"/volume/{volume}")
                else:
                    options.append(f"/localdir/{localdir}")

        elif self.arguments.tool_arguments["subcommand"] == "restore":
            options.extend(self.configuration.get_options())
            options.extend(["--target", self.arguments.tool_arguments["restore"]])
            options.append("restore")

        if self.arguments.restic_arguments:
            options.extend(self.arguments.restic_arguments)

        return options

    def run_docker(self, command: list, env: dict, volumes: dict) -> int:
        """Execute docker with the configured options"""

        container = self.client.containers.run(
            image=self.arguments.tool_arguments["image"],
            command=command,
            remove=True,
            environment=env,
            extra_hosts={"restictool.local": self.own_ip_address} if self.own_ip_address else None,
            volumes=volumes,
            detach=True
        )

        for log in container.logs(stream=True):
            print(log.decode("utf-8").rstrip())

        exit_code = container.wait()

        return exit_code["StatusCode"]


def run():
    """Run the tool"""
    tool = ResticTool()
    tool.setup()
    tool.run()
