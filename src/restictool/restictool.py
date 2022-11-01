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
        elif self.arguments.tool_arguments["subcommand"] == "exists":
            exit_code = self.run_exists()
        elif self.arguments.tool_arguments["subcommand"] == "check":
            logging.info("Configuration is valid")
        else:
            logging.fatal(
                "Unknown command %s", self.arguments.tool_arguments["subcommand"]
            )
            exit_code = 2

        if exit_code != 0:
            if self.arguments.tool_arguments["subcommand"] != "exists":
                logging.error("restic exited with code %d", exit_code)
            sys.exit(exit_code)

    def run_run(self) -> int:
        """Run an arbitrary restic command"""
        exit_code = self.run_docker(
            command=self.get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self.get_docker_mounts(),
        )

        return exit_code

    def run_backup(self) -> int:
        """Run the backup"""
        backed_up = False
        exit_code = 0

        volumes = [
            x.name
            for x in self.client.volumes.list()
            if self.configuration.is_volume_backed_up(x.name)
        ]

        volumes.sort()

        for volume in volumes:
            logging.info("Backing up volume '%s'", volume)
            backed_up = True

            code = self.run_docker(
                command=self.get_restic_arguments(volume=volume),
                env=self.configuration.environment_vars,
                volumes=self.get_docker_mounts(volume=volume),
            )

            if code > exit_code:
                exit_code = code

        for local_dir in self.configuration.localdirs_to_backup:
            logging.info("Backing up local directory '%s'", local_dir[1])
            backed_up = True

            code = self.run_docker(
                command=self.get_restic_arguments(localdir_name=local_dir[0]),
                env=self.configuration.environment_vars,
                volumes=self.get_docker_mounts(localdir=local_dir),
            )

            if code > exit_code:
                exit_code = code

        if backed_up:
            if self.configuration.is_forget_specified():
                logging.info("Forgetting expired backups")

                code = self.run_docker(
                    command=self.get_restic_arguments(forget=True),
                    env=self.configuration.environment_vars,
                    volumes=self.get_docker_mounts(),
                )

                if self.arguments.tool_arguments["prune"]:
                    logging.info("Pruning the repository")

                    code = self.run_docker(
                        command=self.get_restic_arguments(prune=True),
                        env=self.configuration.environment_vars,
                        volumes=self.get_docker_mounts(),
                    )

                if code > exit_code:
                    exit_code = code
        else:
            logging.warning("Nothing to back up")

        return 0

    def run_restore(self) -> int:
        """Run the restore"""
        return 0

    def run_exists(self) -> int:
        """Run an arbitrary restic command"""
        exit_code = self.run_docker(
            command=self.get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self.get_docker_mounts(),
            quiet=True,
        )

        if exit_code > 0:
            logging.warning(
                "Repository '%s' does not exist or is not reachable",
                self.configuration.configuration["repository"]["location"],
            )
        else:
            logging.info(
                "Repository '%s' exists",
                self.configuration.configuration["repository"]["location"],
            )

        return exit_code

    def find_own_network(self):
        """Find own address on the default bridge network"""
        try:
            bridge = self.client.networks.get(self.BRIDGE_NETWORK_NAME, scope="local")
            self.own_ip_address = bridge.attrs["IPAM"]["Config"][0]["Gateway"]
            logging.debug(
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
        self,
        volume: str = None,
        localdir_name: str = None,
        forget: bool = False,
        prune: bool = False,
    ) -> list:
        """
        Get the restic arguments for the specified command and eventually
        volume or local directory
        """
        options = ["--cache-dir", "/cache"]

        if self.arguments.tool_arguments["subcommand"] == "run":
            options.extend(self.configuration.get_options())
        elif self.arguments.tool_arguments["subcommand"] == "exists":
            options.extend(self.configuration.get_options())
            options.extend(["cat", "config"])
        elif self.arguments.tool_arguments["subcommand"] == "backup":
            options.extend(self.configuration.get_options(volume, localdir_name, forget))
            if not prune:
                options.extend(["--host", self.configuration.hostname])

            if forget:
                options.append("forget")
            elif prune:
                options.append("prune")
            else:
                assert volume or localdir_name
                options.append("backup")
                if volume:
                    options.append(f"/volume/{volume}")
                else:
                    options.append(f"/localdir/{localdir_name}")

        elif self.arguments.tool_arguments["subcommand"] == "restore":
            options.extend(self.configuration.get_options())
            options.extend(["--target", self.arguments.tool_arguments["restore"]])
            options.append("restore")

        if self.arguments.restic_arguments:
            options.extend(self.arguments.restic_arguments)

        if self.arguments.tool_arguments["quiet"]:
            options.append("-q")

        return options

    def run_docker(self, command: list, env: dict, volumes: dict, quiet=False) -> int:
        """Execute docker with the configured options"""

        logging.debug(
            "Running docker\ncommand: %s\nenvironment: %s\nmounts: %s",
            command,
            env,
            volumes,
        )

        container = self.client.containers.run(
            image=self.arguments.tool_arguments["image"],
            command=command,
            remove=True,
            environment=env,
            extra_hosts={"restictool.local": self.own_ip_address}
            if self.own_ip_address
            else None,
            volumes=volumes,
            detach=True,
        )

        for log in container.logs(stream=True):
            if not quiet:
                print(log.decode("utf-8").rstrip())

        exit_code = container.wait()

        return exit_code["StatusCode"]


def run():
    """Run the tool"""
    tool = ResticTool()
    tool.setup()
    tool.run()
