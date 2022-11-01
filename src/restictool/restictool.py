"""
Fetch the arguments, parse the configuration and run the selected functionality
"""

import logging
import os
import sys
import docker
import docker.errors

from restictool.settings import Settings, SubCommand

from .argument_parser import Arguments
from .configuration_parser import Configuration


class ResticTool:
    """Main interface to the dockerized restic"""

    BRIDGE_NETWORK_NAME = "bridge"
    OWN_HOSTNAME = "restic.local"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.configuration = None
        self.client = None
        self.own_ip_address = None

    def setup(self):
        """Parse the arguments and fetch the configuration"""
        logging.basicConfig(level=self.settings.log_level)

        logging.info("Initializing")

        self.configuration = Configuration()

        try:
            self.configuration.load(self.settings.configuration_stream)
        except ValueError as ex:
            logging.error(ex.with_traceback(None))
            sys.exit(2)

        if self.settings.subcommand != SubCommand.CHECK:
            self.client = docker.from_env()

    def run(self):
        """Run the tool"""
        exit_code = 0

        if self.settings.subcommand != SubCommand.CHECK:
            self.pull_if_needed()
            self.create_directories()
            self.find_own_network()

        if self.settings.subcommand == SubCommand.RUN:
            exit_code = self.run_general()
        elif self.settings.subcommand == SubCommand.BACKUP:
            exit_code = self.run_backup()
        elif self.settings.subcommand == SubCommand.RESTORE:
            exit_code = self.run_restore()
        elif self.settings.subcommand == SubCommand.SNAPSHOTS:
            exit_code = self.run_general()
        elif self.settings.subcommand == SubCommand.EXISTS:
            exit_code = self.run_exists()
        elif self.settings.subcommand == SubCommand.CHECK:
            logging.info("Configuration is valid")
        else:
            logging.fatal("Unknown command %s", self.settings.subcommand.name)
            exit_code = 2

        if exit_code != 0:
            if self.settings.subcommand != SubCommand.EXISTS:
                logging.error("restic exited with code %d", exit_code)
            sys.exit(exit_code)

    def run_general(self) -> int:
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

                if self.settings.prune:
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
        exit_code = self.run_docker(
            command=self.get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self.get_docker_mounts(),
        )

        if exit_code == 0:
            logging.info(
                "Restore to %s successful",
                self.settings.restore_directory,
            )

        return exit_code

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
        if self.settings.force_pull:
            image = self.settings.image.split(":")
            logging.info("Pulling image %s", self.settings.image)
            self.client.images.pull(
                repository=image[0], tag=image[1] if len(image) > 1 else None
            )

    def create_directory(self, path: str, name: str) -> bool:
        """Create a directory if needed"""
        if not os.path.exists(path):
            logging.info("Creating %s directory %s", name, path)
            os.makedirs(path, mode=0o755)

        if not os.path.isdir(path):
            logging.fatal(
                "Could not create %s directory %s, exiting",
                name,
                path,
            )
            return False

        return True

    def create_directories(self):
        """Create directories"""
        if not self.create_directory(self.settings.cache_directory, "cache"):
            sys.exit(2)

        if self.settings.subcommand == SubCommand.RESTORE:
            if not self.create_directory(self.settings.restore_directory, "restore"):
                sys.exit(2)

    def get_docker_mounts(self, volume: str = None, localdir: tuple = None) -> dict:
        """
        Get the dict that can be used as ``volumes`` argument to run()
        """
        mounts = {}

        mounts[self.settings.cache_directory] = {
            "bind": "/cache",
            "mode": "rw",
        }

        if self.settings.subcommand == SubCommand.BACKUP:
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

        if self.settings.subcommand == SubCommand.RESTORE:
            mounts[self.settings.restore_directory] = {
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

        if self.settings.subcommand == SubCommand.RUN:
            options.extend(self.configuration.get_options())
        elif self.settings.subcommand == SubCommand.EXISTS:
            options.extend(["cat", "config"])
            options.extend(self.configuration.get_options())
        elif self.settings.subcommand == SubCommand.SNAPSHOTS:
            options.append("snapshots")
            options.extend(self.configuration.get_options())
        elif self.settings.subcommand == SubCommand.BACKUP:
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

            options.extend(
                self.configuration.get_options(volume, localdir_name, forget)
            )

            if not prune:
                options.extend(["--host", self.configuration.hostname])

        elif self.settings.subcommand == SubCommand.RESTORE:
            options.extend(["restore", self.settings.restore_snapshot])
            options.extend(["--target", "/target"])
            options.extend(self.configuration.get_options())

        if self.settings.restic_arguments:
            options.extend(self.settings.restic_arguments)

        if self.settings.quiet:
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
            image=self.settings.image,
            command=command,
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

        container.remove()

        return exit_code["StatusCode"]


def run():
    """Run the tool"""
    arguments = Arguments()
    arguments.parse()

    tool = ResticTool(arguments.to_settings())
    tool.setup()
    tool.run()
