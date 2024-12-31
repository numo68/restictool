"""Parses the configuration for the restictool
"""

import io
import platform
import re
import os

from schema import SchemaError
from yaml import load, FullLoader

from .configuration_validator import validate


class Configuration:
    """Parses the configuration given by a stream

    Attributes
    ----------

    configuration : dict
        A parsed and validated configuration.
    environment_vars : dict
        A dictionary of environment names and values to be passed to the restic
        container.
    hostname : str
        Name of the host to be used for the restic backup and restore.
    network_from: str
        Optional name of the container to use for networking.
    volumes_to_backup : list
        List of the explicitly specified volumes to backup.
    volumes_to_exclude : list
        List of the volumes to exclude.
    backup_all_volumes: bool
        If the list of volumes contains a ``*``, volumes_to_backup is empty,
        volumes_to_exclude contains the exclusion list, and this attribute
        is True.
    localdirs_to_backup : list
        List of the explicitly specified local directories to backup.
        Items are the (name, path) tuples.
    """

    _FORBIDDEN_ENV_VARS = [
        "RESTIC_REPOSITORY",
        "RESTIC_REPOSITORY_FILE",
        "RESTIC_PASSWORD",
        "RESTIC_PASSWORD_FILE",
        "RESTIC_PASSWORD_COMMAND",
        "RESTIC_CACHE_DIR",
        "TMPDIR",
    ]

    _ANONYMOUS_VOLUME_REGEX = re.compile(r"^[0-9a-fA-f]{48,}$")

    _FORGET_DEFAULT = [
        "--keep-daily",
        "7",
        "--keep-weekly",
        "5",
        "--keep-monthly",
        "12",
    ]

    def __init__(self):
        self.configuration = None
        self.environment_vars = None
        self.hostname = None
        self.network_from = None
        self.backup_all_volumes = False
        self.volumes_to_backup = []
        self.volumes_to_exclude = []
        self.localdirs_to_backup = []
        self.metrics_path = None

    def load(self, stream, close=True) -> None:
        """Loads, parses and validates the configuration from a stream.

        Parameters
        ----------
        stream : io.IOBase | str
            Stream to read the configuration from.
        close : bool, optional
            If the stream is an instance of io.IOBase and the close argument is True,
            it will be closed. The default is True.

        Raises
        ------
        ValueError
            If the configuration is invalid.
        """
        try:
            config = load(stream, Loader=FullLoader)
        except Exception as ex:
            raise ValueError(
                "configuration invalid\n" + str(ex.with_traceback(None))
            ) from None

        if isinstance(stream, io.IOBase) and close:
            stream.close()

        try:
            self.configuration = validate(config)
        except SchemaError as ex:
            raise ValueError(
                "configuration invalid\n" + str(ex.with_traceback(None))
            ) from None

        self.create_env_vars()

        if "host" in self.configuration["repository"]:
            self.hostname = self.configuration["repository"]["host"]
        else:
            self.hostname = platform.node().lower()

        if "network_from" in self.configuration["repository"]:
            self.network_from = self.configuration["repository"]["network_from"]

        if "metrics" in self.configuration:
            self.metrics_path = os.path.join(
                self.configuration["metrics"]["directory"], "restictool"
            )

            if "suffix" in self.configuration["metrics"]:
                self.metrics_path += "-" + self.configuration["metrics"]["suffix"]

            self.metrics_path += ".prom"

        self.volumes_to_backup = []
        self.backup_all_volumes = False

        if "volumes" in self.configuration:
            for vol in self.configuration["volumes"]:
                if vol["name"] == "*":
                    self.volumes_to_backup.clear()
                    self.backup_all_volumes = True
                    if "exclude" in vol:
                        self.volumes_to_exclude = vol["exclude"]
                    break
                self.volumes_to_backup.append(vol["name"])

        self.localdirs_to_backup = []
        if "localdirs" in self.configuration:
            for ldir in self.configuration["localdirs"]:
                dir_path = (
                    ldir["path"]
                    if not ldir["path"].startswith("~")
                    else ldir["path"].replace("~", os.environ["HOME"], 1)
                )
                self.localdirs_to_backup.append((ldir["name"], dir_path))

        if self.is_prune_specified() and self.configuration["options"]["prune"] is None:
            self.configuration["options"]["prune"] = []

    def create_env_vars(self) -> None:
        """Retrieves the environment variables the restic is to be executed with.

        Raises
        ------
        ValueError
            If the configuration specifies variables that are forbidden to set
            from the configuration.
        """
        self.environment_vars = {}

        if "authentication" in self.configuration["repository"]:
            self.environment_vars.update(
                self.configuration["repository"]["authentication"]
            )

        if "extra" in self.configuration["repository"]:
            self.environment_vars.update(self.configuration["repository"]["extra"])

        for key in self._FORBIDDEN_ENV_VARS:
            if key in self.environment_vars:
                raise ValueError(f"configuration invalid: variable {key} is forbidden")

        self.environment_vars["RESTIC_REPOSITORY"] = self.configuration["repository"][
            "location"
        ]
        self.environment_vars["RESTIC_PASSWORD"] = self.configuration["repository"][
            "password"
        ]

    def get_options(
        self,
        volume: str = None,
        localdir: str = None,
        forget: bool = False,
        prune: bool = False,
    ) -> list:
        """Retrieves the options the restic is to be executed with.

        If volume or localdir are specified, the volume/localdir options are appended
        as well, both general and per-volume/localdir.

        Parameters
        ----------
        volume : str, optional
            The volume being backed up, by default None.
        localdir : str, optional
            The local directory being backed up, by default None.
        forget : bool, optional
            Return the options for the ``forget`` pass after the backup, by default False.
        prune : bool, optional
            Return the options for the ``prune`` pass after the backup, by default False.

        Returns
        -------
        list
            The list of restic command-line options to use.
        """

        options = []

        if "options" in self.configuration:
            if "common" in self.configuration["options"]:
                options.extend(self.configuration["options"]["common"])
            if forget and "forget" in self.configuration["options"]:
                for opt in self.configuration["options"]["forget"]:
                    if opt == "DEFAULT":
                        options.extend(self._FORGET_DEFAULT)
                    else:
                        options.append(opt)
            if prune and "prune" in self.configuration["options"]:
                options.extend(self.configuration["options"]["prune"])
            if volume and "volume" in self.configuration["options"]:
                options.extend(self.configuration["options"]["volume"])
            if localdir and "localdir" in self.configuration["options"]:
                options.extend(self.configuration["options"]["localdir"])

        if volume:
            options.extend(self._get_volume_options(volume))

        if localdir:
            options.extend(self._get_localdir_options(localdir))

        return options

    def _get_volume_options(self, volume: str) -> list:
        options = []

        if "volumes" in self.configuration:
            for vol in self.configuration["volumes"]:
                if volume == vol["name"]:
                    if "options" in vol:
                        options.extend(vol["options"])
                    break
            else:
                for vol in self.configuration["volumes"]:
                    if vol["name"] == "*":
                        if "options" in vol:
                            options.extend(vol["options"])
                        break

        return options

    def _get_localdir_options(self, localdir: str) -> list:
        options = []

        if "localdirs" in self.configuration:
            for ldir in self.configuration["localdirs"]:
                if localdir == ldir["name"]:
                    if "options" in ldir:
                        options.extend(ldir["options"])
                    break

        return options

    def is_volume_backed_up(self, volume: str) -> bool:
        """Check whether a volume with a specified name is to be backed up.

        Parameters
        ----------
        volume : str
            The name of the volume.

        Returns
        -------
        bool
            True if the specified volume should be backed up. If there is a ``*``
            entry, all volumes except anonymous ones (48+ hex characters) match.
            If there is not, the name has to match exactly.
        """

        if self.backup_all_volumes:
            return (
                not self._ANONYMOUS_VOLUME_REGEX.match(volume)
                and not volume in self.volumes_to_exclude
            )

        return volume in self.volumes_to_backup

    def is_forget_specified(self) -> bool:
        """Check whether a ``forget`` should be run after finishing the backup.

        Returns
        -------
        bool
            The configuration specifies the settings for a ``forget`` pass.
        """
        return (
            "options" in self.configuration
            and "forget" in self.configuration["options"]
        )

    def is_prune_specified(self) -> bool:
        """Check whether a ``prune`` should be run after finishing the backup.

        Returns
        -------
        bool
            The configuration specifies the settings for a ``prune`` pass.
        """
        return (
            "options" in self.configuration and "prune" in self.configuration["options"]
        )

    def metrics_dir_exists(self) -> bool:
        """Checks whether the metrics directory exists

        Returns:
            bool: The configuration specifies the metrics directory and it exists.
        """
        return (
            "metrics" in self.configuration
            and os.path.exists(self.configuration["metrics"]["directory"])
            and os.path.isdir(
                os.path.realpath(self.configuration["metrics"]["directory"])
            )
        )
