"""Holds the settings for the tool.
"""

from enum import Enum
from os import environ, path


class SubCommand(Enum):
    """Defines the sub-command enum for the restic tool."""

    NOTSET = 0
    BACKUP = 1
    RESTORE = 2
    DOCKERDR = 3
    SNAPSHOTS = 4
    RUN = 5
    EXISTS = 6
    CHECK = 7


class Settings:
    """Contains settings provided by either the command line or via other means.

    Attributes
    ----------

    subcommand : Subcommand
        The sub-command to run.
    image : str
        The docker image to pull/run.
    force_pull : bool
        If True the image will be pulled before running the backup. If False
        it will be only pulled if not present on the system.
    configuration_stream : io.IOBase | str
        The configuration file or string.
    cache_directory: str
        An absolute path to a cache directory.
    log_level : str
        Logging level that can be parsed by ``logging.basicConfig``.
    quiet : bool
        Silence the ``restic`` by passing it a ``--quiet`` argument.
    restore_snapshot : str
        Snapshot to restore. Only read when restoring.
    restore_directory : str
        An absolute path to a directory where the snapshot will be restored.
        Only read when restoring.
    restic_arguments : list
        Arguments passed to the ``restic``.
    """

    DEFAULT_IMAGE = "restic/restic"
    """Default image to pull/run"""
    DEFAULT_CONFIGURATION_FILE = path.join(
        environ["HOME"], ".config", "restictool", "restictool.yml"
    )
    """Default configuration file to read (class attribute)."""
    DEFAULT_CACHE_DIR = path.join(environ["HOME"], ".cache", "restic")
    """Default cache directory (class attribute)."""

    def __init__(self):
        self.subcommand = SubCommand.NOTSET
        self.image = self.DEFAULT_IMAGE
        self.force_pull = False
        self.configuration_stream = None
        self.cache_directory = self.DEFAULT_CACHE_DIR
        self.log_level = "WARNING"
        self.quiet = False
        self.restore_snapshot = None
        self.restore_directory = None
        self.restic_arguments = []
