"""
Parses the configuration for the restictool
"""

import io
import sys
from yaml import safe_load


class Configuration:
    """
    Parses the configuration
    """

    def __init__(self):
        self.configuration = None

    def load(self, stream, close=True):
        """Loads the stream and does the initial parsing and sanity checking

        Args:
            stream (IOBase): configuration file opened as stream
            close (bool): close the stream after reading
        """
        self.configuration = safe_load(stream)

        if isinstance(stream, io.IOBase) and close:
            stream.close()

        self.validate()

    def validate(self):
        """Validates the parsed configuration"""
        assert self.configuration is not None, "Load configuration before validating"

        if "repository" not in self.configuration or not isinstance(
            self.configuration["repository"], dict
        ):
            sys.exit("'repository' entry is missing or empty in the configuration")

        repo = self.configuration["repository"]
        if "name" not in repo or not isinstance(repo["name"], str) or not repo["name"]:
            sys.exit(
                "'repository.name' entry is missing, empty or not a string in the configuration"
            )

        if (
            "password" not in repo
            or not isinstance(repo["password"], str)
            or not repo["password"]
        ):
            sys.exit(
                "'repository.password' entry is missing, empty or not a string in the configuration"
            )
