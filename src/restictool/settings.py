"""Holds the settings for the tool.
"""

from enum import Enum
from os import environ, path


class SubCommand(Enum):
    """Defines the sub-command enum for the restic tool."""

    NOTSET = 0
    BACKUP = 1
    RESTORE = 2
    SNAPSHOTS = 3
    RUN = 4
    EXISTS = 5
    CHECK = 6


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
    prune : bool
        True if the ``forget`` should be followed by pruning.
        Only read when backing up and ``forget`` parameters are specified.
    quiet : bool
        Silence the ``restic`` by passing it a ``--quiet`` argument.
    restore_snapshot : str
        Snapshot to restore. Only read when restoring.
    restore_directory : str
        An absolute path to a directory where the snapshot will be restored.
        Only read when restoring.
    restic_arguments : list
        Arguments passed to the ``restic``.

    DEFAULT_IMAGE : str
        Default image to pull/run (class attribute).
    DEFAULT_CONFIGURATION_FILE : str
        Default configuration file to read (class attribute).
    DEFAULT_CACHE_DIR : str
        Default cache directory (class attribute).
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
        self.restore_snapshot = None
        self.restore_directory = None
        self.restic_arguments = []
