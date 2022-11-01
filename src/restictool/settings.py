"""
Holds the settings for the tool
"""

from enum import Enum
from os import environ, path


class SubCommand(Enum):
    """restictool subcommand"""

    NOTSET = 0
    BACKUP = 1
    RESTORE = 2
    RUN = 3
    EXISTS = 4
    CHECK = 5


class Settings:
    """
    Contains settings provided by either the command line or in another way
    """

    DEFAULT_IMAGE = "restic/restic"
    DEFAULT_CONFIGURATION_FILE = path.join(
        environ["HOME"], ".config", "restictool", "restictool.yml"
    )
    DEFAULT_CACHE_DIR = path.join(environ["HOME"], ".cache", "restic")

    def __init__(self):
        self.subcommand = SubCommand.NOTSET
        self.image = self.DEFAULT_IMAGE
        self.force_pull = False
        self.configuration_stream = None
        self.cache_directory = self.DEFAULT_CACHE_DIR
        self.log_level = "WARNING"
        self.prune = False
        self.quiet = False
        self.restore_directory = None
        self.restic_arguments = []
