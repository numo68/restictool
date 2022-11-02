"""
Fetch the arguments, parse the configuration and run the selected functionality
"""

import logging
import os
import docker
import docker.errors

from restictool.settings import Settings, SubCommand

from .configuration_parser import Configuration


class ResticToolException(Exception):
    """Throw if an error prevents the tool to continue. If invoked from a command
    line exit wit the code provided.
    """

    def __init__(self, code: int, description: str):
        self.exit_code = code
        self.description = description

    def __str__(self):
        return self.description


class ResticTool:
    """Main interface to the dockerized restic

    Parameters
    ----------
    settings : Settings
        Set of the parameters defining the tool configuration.
        It can be either derived from the :class:`.Arguments`
        or set explicitly.
    """

    _OWN_HOSTNAME = "restictool.local"
    _BRIDGE_NETWORK_NAME = "bridge"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.configuration = None
        self.client = None
        self.own_ip_address = None

    def setup(self):
        """Reads and validates the configuration and prepares the tool.

        Raises
        ------
        ResticToolException
            If the configuration could not be loaded or is invalid or if
            the settings specify an unsupported operation.
        """
        logging.basicConfig(level=self.settings.log_level)

        logging.info("Initializing")

        self.configuration = Configuration()

        try:
            self.configuration.load(self.settings.configuration_stream)
        except ValueError as ex:
            logging.fatal(ex.with_traceback(None))
            raise ResticToolException(16, ex.with_traceback(None)) from ex

        if self.settings.subcommand not in [
            SubCommand.CHECK,
            SubCommand.RUN,
            SubCommand.BACKUP,
            SubCommand.RESTORE,
            SubCommand.SNAPSHOTS,
            SubCommand.EXISTS,
        ]:
            logging.fatal("Unknown command %s", self.settings.subcommand.name)
            raise ResticToolException(
                16, f"Unknown command {self.settings.subcommand.name}"
            )

        if self.settings.subcommand != SubCommand.CHECK:
            self.client = docker.from_env()

    def run(self):
        """Runs the tool according to the settings and the configuration.

        Raises
        ------
        ResticToolException
            If the restic container returned an non-zero status code.
        """
        exit_code = 0

        if self.settings.subcommand == SubCommand.CHECK:
            logging.info("Configuration is valid")  # Would not come here if invalid
        else:
            command_mux = {
                SubCommand.RUN: self._run_general,
                SubCommand.BACKUP: self._run_backup,
                SubCommand.RESTORE: self._run_restore,
                SubCommand.SNAPSHOTS: self._run_general,
                SubCommand.EXISTS: self._run_exists,
            }

            self._pull_if_needed()
            self._create_directories()
            self._find_own_network()

            exit_code = command_mux[self.settings.subcommand]()

            if exit_code != 0:
                if self.settings.subcommand != SubCommand.EXISTS:
                    logging.error("restic exited with code %d", exit_code)
                    raise ResticToolException(
                        exit_code, f"restic exited with code {exit_code}"
                    )

    def _run_general(self) -> int:
        """Run an arbitrary restic command"""
        exit_code = self._run_docker(
            command=self._get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
        )

        return exit_code

    def _run_backup(self) -> int:
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

            code = self._run_docker(
                command=self._get_restic_arguments(volume=volume),
                env=self.configuration.environment_vars,
                volumes=self._get_docker_mounts(volume=volume),
            )

            if code > exit_code:
                exit_code = code

        for local_dir in self.configuration.localdirs_to_backup:
            logging.info("Backing up local directory '%s'", local_dir[1])
            backed_up = True

            code = self._run_docker(
                command=self._get_restic_arguments(localdir_name=local_dir[0]),
                env=self.configuration.environment_vars,
                volumes=self._get_docker_mounts(localdir=local_dir),
            )

            if code > exit_code:
                exit_code = code

        if backed_up:
            if self.configuration.is_forget_specified():
                logging.info("Forgetting expired backups")

                code = self._run_docker(
                    command=self._get_restic_arguments(forget=True),
                    env=self.configuration.environment_vars,
                    volumes=self._get_docker_mounts(),
                )

                if self.settings.prune:
                    logging.info("Pruning the repository")

                    code = self._run_docker(
                        command=self._get_restic_arguments(prune=True),
                        env=self.configuration.environment_vars,
                        volumes=self._get_docker_mounts(),
                    )

                if code > exit_code:
                    exit_code = code
        else:
            logging.warning("Nothing to back up")

        return 0

    def _run_restore(self) -> int:
        """Run the restore"""
        exit_code = self._run_docker(
            command=self._get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
        )

        if exit_code == 0:
            logging.info(
                "Restore to %s successful",
                self.settings.restore_directory,
            )

        return exit_code

    def _run_exists(self) -> int:
        """Run an arbitrary restic command"""
        exit_code = self._run_docker(
            command=self._get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
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

    def _find_own_network(self):
        """Find own address on the default bridge network"""
        try:
            bridge = self.client.networks.get(self._BRIDGE_NETWORK_NAME, scope="local")
            self.own_ip_address = bridge.attrs["IPAM"]["Config"][0]["Gateway"]
            logging.debug(
                "Own address on the '%s' network: %s",
                self._BRIDGE_NETWORK_NAME,
                self.own_ip_address,
            )
        except (docker.errors.NotFound, KeyError, TypeError, IndexError):
            logging.warning(
                "Network '%s' not recognized, own address won't be added",
                self._BRIDGE_NETWORK_NAME,
            )
            self.own_ip_address = None

    def _pull_if_needed(self):
        """Pull the image if requested"""
        if self.settings.force_pull:
            image = self.settings.image.split(":")
            logging.info("Pulling image %s", self.settings.image)
            self.client.images.pull(
                repository=image[0], tag=image[1] if len(image) > 1 else None
            )

    def _create_directory(self, path: str, name: str):
        """Create a directory if needed"""
        try:
            if not os.path.exists(path) or not os.path.isdir(path):
                logging.info("Creating %s directory %s", name, path)
                os.makedirs(path, mode=0o755)
        except Exception as ex:
            logging.fatal(
                "Could not create %s directory %s, exiting",
                name,
                path,
            )
            raise ResticToolException(16, ex.with_traceback(None)) from ex

    def _create_directories(self):
        """Create directories"""
        self._create_directory(self.settings.cache_directory, "cache")

        if self.settings.subcommand == SubCommand.RESTORE:
            self._create_directory(self.settings.restore_directory, "restore")

    def _get_docker_mounts(self, volume: str = None, localdir: tuple = None) -> dict:
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

    def _get_restic_arguments(
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

    def _run_docker(self, command: list, env: dict, volumes: dict, quiet=False) -> int:
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
            extra_hosts={self._OWN_HOSTNAME: self.own_ip_address}
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
