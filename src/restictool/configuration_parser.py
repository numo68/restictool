"""
Parses the configuration for the restictool
"""

import io
import platform
import re

from schema import SchemaError
from yaml import safe_load

from .configuration_validator import validate


class Configuration:
    """
    Parses the configuration given by a stream

    Attributes
    ----------

    configuration : dict
        a parsed and validated configuration
    environment_vars : dict
        a dictionary of environment names and values to be passed to the restic
        container
    hostname : str
        name of the host to be used for the restic backup and restore.
    volumes_to_backup : list
        list of the explicitly specified volumes to backup
    backup_all_volumes: bool
        if the list of volumes contains a ``*``, volumes_to_backup is empty
        and this attribute is True
    localdirs_to_backup : list
        list of the explicitly specified local directories to backup.
        Items are the (name,path) tuples

    Methods
    -------

    load(stream, close=True)
        loads, parses and validates the configuration from a stream. If the stream
        is an instance of io.IOBase and the close argument is True, it will be closed.

    get_options(volume : str, localdir : str) -> list
        returns the list of restic command-line options to use. If volume or localdir
        are specified, the volume/localdir options are appended as well, both general
        and per-volume/localdir
    
    is_volume_backed_up(volume : str) -> bool
        True if the specified volume should be backed up. If there is a ``*`` entry,
        all volumes except anonymous ones (48+ hex characters) match. If there is not,
        the name has to match exactly.
    """

    FORBIDDEN_ENV_VARS = [
        "RESTIC_REPOSITORY",
        "RESTIC_REPOSITORY_FILE",
        "RESTIC_PASSWORD",
        "RESTIC_PASSWORD_FILE",
        "RESTIC_PASSWORD_COMMAND",
        "RESTIC_CACHE_DIR",
        "TMPDIR",
    ]

    ANONYMOUS_VOLUME_REGEX = re.compile(r"^[0-9a-fA-f]{48,}$")

    def __init__(self):
        self.configuration = None
        self.environment_vars = None
        self.hostname = None
        self.volumes_to_backup = None
        self.backup_all_volumes = False
        self.localdirs_to_backup = None

    def load(self, stream, close=True) -> None:
        """Loads the stream and does the initial parsing and sanity checking

        Args:
            stream (IOBase): configuration file opened as stream
            close (bool): close the stream after reading
        """

        try:
            config = safe_load(stream)
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

        if ("host") in self.configuration["repository"]:
            self.hostname = self.configuration["repository"]["host"]
        else:
            self.hostname = platform.node().lower()

        self.volumes_to_backup = []
        self.backup_all_volumes = False

        if "volumes" in self.configuration:
            for vol in self.configuration["volumes"]:
                if vol["name"] == "*":
                    self.volumes_to_backup.clear()
                    self.backup_all_volumes = True
                    break
                self.volumes_to_backup.append(vol["name"])

        self.localdirs_to_backup = []
        if "localdirs" in self.configuration:
            for ldir in self.configuration["localdirs"]:
                self.localdirs_to_backup.append((ldir["name"], ldir["path"]))

    def create_env_vars(self) -> None:
        """Parse and set the environment variables"""
        self.environment_vars = {}

        if "authentication" in self.configuration["repository"]:
            self.environment_vars.update(
                self.configuration["repository"]["authentication"]
            )

        if "extra" in self.configuration["repository"]:
            self.environment_vars.update(self.configuration["repository"]["extra"])

        for key in self.FORBIDDEN_ENV_VARS:
            if key in self.environment_vars:
                raise ValueError(f"configuration invalid: variable {key} is forbidden")

        self.environment_vars["RESTIC_REPOSITORY"] = self.configuration["repository"]["location"]
        self.environment_vars["RESTIC_PASSWORD"] = self.configuration["repository"]["password"]

    def get_options(self, volume: str = None, localdir: str = None) -> list:
        """Collect the list of the options to be used for rsetic invocation"""
        options = []
        if "options" in self.configuration:
            if "common" in self.configuration["options"]:
                options.extend(self.configuration["options"]["common"])
            if volume and "volume" in self.configuration["options"]:
                options.extend(self.configuration["options"]["volume"])
            if localdir and "localdir" in self.configuration["options"]:
                options.extend(self.configuration["options"]["localdir"])

        if volume:
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

        if localdir:
            if "localdirs" in self.configuration:
                for ldir in self.configuration["localdirs"]:
                    if localdir == ldir["name"]:
                        if "options" in ldir:
                            options.extend(ldir["options"])
                        break

        return options

    def is_volume_backed_up(self, volume: str) -> bool:
        """Returns whether the volume is to be backed up"""
        if self.backup_all_volumes:
            return not self.ANONYMOUS_VOLUME_REGEX.match(volume)
        else:
            return volume in self.volumes_to_backup
