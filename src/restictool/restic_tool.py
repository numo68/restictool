"""
Fetch the arguments, parse the configuration and run the selected functionality
"""

import json
import logging
import logging.config
import os
import docker
import yaml
import traceback
import time

from .settings import Settings, SubCommand
from .configuration_parser import Configuration
from .metrics import Metrics


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

    def log(self, log_function, *args, entity=None, elapsed=None):
        """Log the message, filling out the extras.

        Parameters
        ----------
        log_function : callable
            logging.error etc.
        args : Any
            Arguments for the logging function
        entity : str | None
            Volume or local directory name to backup or restore, if known
        elapsed : float | None
            Elapsed time of the operation, if known
        """
        log_function(
            *args,
            extra={
                "operation": str(self.settings.subcommand)[11:].lower(),
                "repoLocation": self.configuration.configuration["repository"][
                    "location"
                ],
                "repoHost": self.configuration.configuration["repository"]["host"],
                "object": entity if entity is not None else "(None)",
                "elapsed": elapsed if elapsed is not None else 0.0,
            },
        )

    def format_exception(self, ex: Exception):
        """Return the formatted exception with the traceback stripped"""
        return str(
            [
                x.strip().replace("\n", " ")
                for x in traceback.format_exception(type(ex), ex, None, limit=0)
            ]
        )

    def configure_default_logging(self):
        """Configures the default logging"""
        logging_config = yaml.safe_load(
            """
version: 1
root:
    handlers:
        - console
handlers:
    console:
        class: logging.StreamHandler
        formatter: detailed
        stream: ext://sys.stderr
formatters:
    detailed:
        format: '%(asctime)s %(levelname)s op=%(operation)s repo=%(repoLocation)s host=%(repoHost)s object=%(object)s msg=%(message)s'
        datefmt: '%Y-%m-%d %H:%M:%S'
"""
        )

        logging_config["root"]["level"] = self.settings.log_level
        logging.config.dictConfig(logging_config)

    def setup(self):
        """Reads and validates the configuration and prepares the tool.

        Raises
        ------
        ResticToolException
            If the configuration could not be loaded or is invalid or if
            the settings specify an unsupported operation.
        """

        # Load the configuration
        self.configuration = Configuration()

        try:
            self.configuration.load(self.settings.configuration_stream)
        except Exception as ex:
            logging.fatal(
                "Could not load the configuration %s", self.format_exception(ex)
            )
            raise ResticToolException(16, self.format_exception(ex)) from ex

        # Configure the logging

        if "logging" in self.configuration.configuration:
            logging_config = self.configuration.configuration["logging"]
            # Set the level if the console handler is present
            try:
                logging_config["handlers"]["console"]["level"] = self.settings.log_level
            except Exception:  # pylint: disable=broad-except
                pass

            try:
                logging.config.dictConfig(logging_config)
            except Exception as ex:  # pylint disable=broad-except
                self.configure_default_logging()
                self.log(
                    logging.error,
                    "Unable to configure logging, falling back to default: %s",
                    self.format_exception(ex),
                )
        else:
            self.configure_default_logging()

        if self.settings.subcommand not in [
            SubCommand.CHECK,
            SubCommand.RUN,
            SubCommand.BACKUP,
            SubCommand.DOCKERDR,
            SubCommand.RESTORE,
            SubCommand.SNAPSHOTS,
            SubCommand.EXISTS,
        ]:
            self.log(logging.fatal, "Unknown command %s", self.settings.subcommand.name)
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
            self.log(
                logging.info, "Configuration is valid"
            )  # Would not come here if invalid
        else:
            command_mux = {
                SubCommand.RUN: self._run_general,
                SubCommand.BACKUP: self._run_backup,
                SubCommand.RESTORE: self._run_restore,
                SubCommand.DOCKERDR: self._run_dockerdr,
                SubCommand.SNAPSHOTS: self._run_general,
                SubCommand.EXISTS: self._run_exists,
            }

            self._pull_if_needed()
            self._create_directories()
            self._find_own_network()

            exit_code = command_mux[self.settings.subcommand]()

            if exit_code != 0:
                if self.settings.subcommand != SubCommand.EXISTS:
                    self.log(logging.error, "restic exited with code %d", exit_code)

                raise ResticToolException(
                    exit_code, f"restic exited with code {exit_code}"
                )

    def _run_general(self) -> int:
        """Run an arbitrary restic command"""
        exit_code, _ = self._run_docker(
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
            self.log(logging.debug, "Backing up volume", entity=volume)
            backed_up = True
            start_time = time.monotonic()

            code, _ = self._run_docker(
                command=self._get_restic_arguments(volume=volume),
                env=self.configuration.environment_vars,
                volumes=self._get_docker_mounts(volume=volume),
            )

            if code == 0:
                self.log(
                    logging.info,
                    "Successfully backed up volume",
                    entity=volume,
                    elapsed=time.monotonic() - start_time,
                )
            else:
                self.log(
                    logging.error,
                    "Backing up volume failed",
                    entity=volume,
                    elapsed=time.monotonic() - start_time,
                )

            if code > exit_code:
                exit_code = code

        for local_dir in self.configuration.localdirs_to_backup:
            self.log(logging.debug, "Backing up local directory", entity=local_dir[0])
            backed_up = True
            start_time = time.monotonic()

            code, _ = self._run_docker(
                command=self._get_restic_arguments(localdir_name=local_dir[0]),
                env=self.configuration.environment_vars,
                volumes=self._get_docker_mounts(localdir=local_dir),
            )

            if code == 0:
                self.log(
                    logging.info,
                    "Successfully backed up local directory",
                    entity=local_dir[0],
                    elapsed=time.monotonic() - start_time,
                )
            else:
                self.log(
                    logging.error,
                    "Backing up local directory failed",
                    entity=local_dir[0],
                    elapsed=time.monotonic() - start_time,
                )

            if code > exit_code:
                exit_code = code

        if backed_up:
            if self.configuration.is_forget_specified():
                self.log(logging.debug, "Forgetting expired backups")
                start_time = time.monotonic()

                code, _ = self._run_docker(
                    command=self._get_restic_arguments(forget=True),
                    env=self.configuration.environment_vars,
                    volumes=self._get_docker_mounts(),
                )

                if code == 0:
                    self.log(
                        logging.info,
                        "Successfully run forget policy",
                        elapsed=time.monotonic() - start_time,
                    )
                else:
                    self.log(
                        logging.error,
                        "Running forget policy failed",
                        elapsed=time.monotonic() - start_time,
                    )

                if code > exit_code:
                    exit_code = code

            if self.configuration.is_prune_specified():
                self.log(logging.debug, "Pruning the repository")
                start_time = time.monotonic()

                code, _ = self._run_docker(
                    command=self._get_restic_arguments(prune=True),
                    env=self.configuration.environment_vars,
                    volumes=self._get_docker_mounts(),
                )

                if code == 0:
                    self.log(
                        logging.info,
                        "Successfully pruned the snapshots",
                        elapsed=time.monotonic() - start_time,
                    )
                else:
                    self.log(
                        logging.error,
                        "Pruning the snapshots failed",
                        elapsed=time.monotonic() - start_time,
                    )

                if code > exit_code:
                    exit_code = code

            if self.configuration.metrics_path:
                self.log(logging.debug, "Generating the metrics")
                start_time = time.monotonic()

                if self.configuration.metrics_dir_exists():
                    options = ["--cache-dir", "/cache", "snapshots"]
                    options.extend(self.configuration.get_options())
                    options.extend(
                        [
                            "--latest=1",
                            "--host=" + self.configuration.hostname,
                            "--json",
                        ]
                    )

                    code, output = self._run_docker(
                        options,
                        env=self.configuration.environment_vars,
                        volumes=self._get_docker_mounts(),
                        quiet=True,
                    )

                    if code == 0:
                        try:
                            metrics = Metrics(self.configuration)
                            metrics.set_snapshots(json.loads(output))
                            metrics.write_to_file()

                            self.log(
                                logging.info,
                                "Successfully generated the metrics",
                                elapsed=time.monotonic() - start_time,
                            )
                        except Exception as ex:  # pylint disable=broad-except
                            self.log(
                                logging.error,
                                "Writing the metrics failed: %s",
                                self.format_exception(ex),
                                elapsed=time.monotonic() - start_time,
                            )
                            
                    else:
                        self.log(
                            logging.error,
                            "Querying the snapshots failed",
                            elapsed=time.monotonic() - start_time,
                        )

                    if code > exit_code:
                        exit_code = code
                else:
                    self.log(
                        logging.error,
                        "Metrics directory does not exist or is not a directory, no metrics generated",
                        elapsed=time.monotonic() - start_time,
                    )

                if code > exit_code:
                    exit_code = code

        else:
            self.log(logging.warning, "Nothing to back up")

        return 0

    def _run_dockerdr(self) -> int:
        """Run the docker volume disaster recovery"""

        # Get the volumes
        volumes = {
            v.attrs["Name"]: v.attrs["Mountpoint"]
            for v in self.client.volumes.list()
            if v.attrs["Driver"] == "local"
        }

        # Get the snapshots
        options = ["--cache-dir", "/cache", "snapshots"]
        options.extend(self.configuration.get_options())
        options.extend(
            ["--latest=1", "--host=" + self.configuration.hostname, "--json"]
        )

        code, output = self._run_docker(
            options,
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
            quiet=True,
        )

        if code > 0:
            self.log(logging.error, "Could not retrieve snapshots")
            return code

        snapshots = json.loads(output)

        exit_code = 0

        for snapshot in snapshots:
            if not snapshot["paths"][0].startswith("/volume/"):
                continue
            volume_name = snapshot["paths"][0][8:]
            snapshot_id = snapshot["short_id"]
            if volume_name not in volumes.keys():
                continue
            dest_dir = os.path.dirname(volumes[volume_name])
            dest_last_component = os.path.basename(volumes[volume_name])
            self.log(
                logging.debug,
                "Restoring volume from snapshot %s to %s",
                snapshot_id,
                dest_dir,
                entity=volume_name,
            )

            options = ["--cache-dir", "/cache", "restore"]
            options.extend(self.configuration.get_options())
            options.extend([snapshot_id, "--target=/target"])

            mounts = self._get_docker_mounts()
            mounts[dest_dir] = {
                "bind": "/target",
                "mode": "rw",
            }

            code, _ = self._run_docker(
                command=options,
                env=self.configuration.environment_vars,
                volumes=mounts,
            )

            if code == 0:
                code, _ = self._run_docker(
                    entrypoint="/bin/mv",
                    command=[
                        os.path.join("/target/volume", volume_name),
                        os.path.join("/target", dest_last_component + ".restored"),
                    ],
                    env=self.configuration.environment_vars,
                    volumes=mounts,
                )

            if code == 0:
                code, _ = self._run_docker(
                    entrypoint="/bin/rmdir",
                    command=["/target/volume"],
                    env=self.configuration.environment_vars,
                    volumes=mounts,
                )

            if code == 0:
                self.log(
                    logging.info,
                    "Sucessfully restored from snapshot %s to %s failed",
                    snapshot_id,
                    dest_dir,
                    entity=volume_name,
                )
            else:
                self.log(
                    logging.error,
                    "Restoring from snapshot %s to %s failed",
                    snapshot_id,
                    dest_dir,
                    entity=volume_name,
                )

                if code > exit_code:
                    exit_code = code

        return exit_code

    def _run_restore(self) -> int:
        """Run the restore"""
        exit_code, _ = self._run_docker(
            command=self._get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
        )

        if exit_code == 0:
            self.log(
                logging.info,
                "Restoring to %s successful",
                self.settings.restore_directory,
            )
        else:
            self.log(
                logging.error,
                "Restoring to %s failed",
                self.settings.restore_directory,
            )

        return exit_code

    def _run_exists(self) -> int:
        """Run an arbitrary restic command"""
        exit_code, _ = self._run_docker(
            command=self._get_restic_arguments(),
            env=self.configuration.environment_vars,
            volumes=self._get_docker_mounts(),
            quiet=True,
        )

        if exit_code > 0:
            self.log(logging.warning, "Repository does not exist or is not reachable")
        else:
            self.log(
                logging.info,
                "Repository exists",
            )

        return exit_code

    def _find_own_network(self):
        """Find own address on the default bridge network"""
        try:
            bridge = self.client.networks.get(self._BRIDGE_NETWORK_NAME, scope="local")
            self.own_ip_address = bridge.attrs["IPAM"]["Config"][0]["Gateway"]
            self.log(
                logging.debug,
                "Own address on the '%s' network: %s",
                self._BRIDGE_NETWORK_NAME,
                self.own_ip_address,
            )
        except (docker.errors.NotFound, KeyError, TypeError, IndexError):
            self.log(
                logging.warning,
                "Network '%s' not recognized, own address won't be added",
                self._BRIDGE_NETWORK_NAME,
            )
            self.own_ip_address = None

    def _pull_if_needed(self):
        """Pull the image if requested"""
        if self.settings.force_pull:
            image = self.settings.image.split(":")
            self.log(logging.info, "Pulling image %s", self.settings.image)
            self.client.images.pull(
                repository=image[0], tag=image[1] if len(image) > 1 else None
            )

    def _create_directory(self, path: str, name: str):
        """Create a directory if needed"""
        try:
            if not os.path.exists(path) or not os.path.isdir(path):
                self.log(logging.info, "Creating %s directory %s", name, path)
                os.makedirs(path, mode=0o755)
        except Exception as ex:
            self.log(
                logging.fatal,
                "Could not create %s directory %s: %s",
                name,
                path,
                self.format_exception(ex),
            )
            raise ResticToolException(16, self.format_exception(ex)) from ex

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
                self.configuration.get_options(volume, localdir_name, forget, prune)
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

    def _run_docker(
        self, command: list, env: dict, volumes: dict, quiet=False, entrypoint=None
    ) -> int:
        """Execute docker with the configured options"""

        self.log(
            logging.debug,
            "Running docker command: %s; environment: %s; mounts: %s",
            command,
            env,
            volumes,
        )

        container = self.client.containers.run(
            image=self.settings.image,
            entrypoint=entrypoint,
            command=command,
            environment=env,
            extra_hosts=(
                {self._OWN_HOSTNAME: self.own_ip_address}
                if self.own_ip_address and self.configuration.network_from is None
                else None
            ),
            network_mode=(
                "container:" + self.configuration.network_from
                if self.configuration.network_from
                else None
            ),
            volumes=volumes,
            detach=True,
        )

        log_save = ""
        for log in container.logs(stream=True):
            line = log.decode("utf-8")
            log_save += line
            if not quiet:
                print(line.rstrip())

        exit_code = container.wait()

        container.remove()

        return (exit_code["StatusCode"], log_save)
