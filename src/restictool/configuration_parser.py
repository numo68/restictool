"""
Parses the configuration for the restictool
"""

import io
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

    Methods
    -------

    load(self, stream, close=True)
        loads, parses and validates the configuration from a stream. If the stream
        is an instance of io.IOBase and the close argument is True, it will be closed.
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

    def __init__(self):
        self.configuration = None
        self.environment_vars = None

    def load(self, stream, close=True):
        """Loads the stream and does the initial parsing and sanity checking

        Args:
            stream (IOBase): configuration file opened as stream
            close (bool): close the stream after reading
        """
        config = safe_load(stream)

        if isinstance(stream, io.IOBase) and close:
            stream.close()

        try:
            self.configuration = validate(config)
        except SchemaError as ex:
            raise ValueError(
                "configuration invalid\n" + str(ex.with_traceback(None))
            ) from None

        self.create_env_vars()

    def create_env_vars(self):
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
