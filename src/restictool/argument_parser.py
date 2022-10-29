"""
Parses the arguments for the restictool
"""

import argparse
from os import environ, path


class Arguments:
    """
    Parses the arguments for the restictool
    """

    DEFAULT_CONFIGURATION_FILE = path.join(
        environ["HOME"], ".config", "restictool", "restictool.yml"
    )
    DEFAULT_CACHE_DIR = path.join(environ["HOME"], ".cache", ".restic")
    DEFAULT_IMAGE = "restic/restic"
    HELP_EPILOG = """
    Use %(prog)s {backup,restore,run} --help to get the subcommand
    specific help.

    The rest of the arguments are passed to the restic command. In case the
    first arguments is a recognized optional one, use -- as a separator.
    """

    def __init__(self):
        self.tool_arguments = None
        self.restic_arguments = None

    def parse(self, arguments=None):
        """Parses the restictool arguments

        Args:
            arguments (list): list of arguments to parse

        Returns: a tuple of the restictol arguments as a dict and the restic ones as a list
        """
        parser = argparse.ArgumentParser(
            prog="restictool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description="A Python wrapper for the dockerized restic tool",
            epilog=self.HELP_EPILOG,
        )

        parser.add_argument(
            "-c",
            "--config",
            default=self.DEFAULT_CONFIGURATION_FILE,
            metavar="FILE",
            type=argparse.FileType("r"),
            help="the configuration file (default: %(default)s)",
        )
        parser.add_argument(
            "--cache",
            default=self.DEFAULT_CACHE_DIR,
            metavar="DIR",
            help="the cache directory (default: %(default)s)",
        )
        parser.add_argument(
            "--image",
            default=self.DEFAULT_IMAGE,
            help="the docker restic image name (default: %(default)s)",
        )
        parser.add_argument(
            "--force-pull",
            action="store_true",
            help="force pulling of the docker image first",
        )
        parser.add_argument("-q", "--quiet", action="store_true", help="remain quiet")
        parser.add_argument(
            "-v", "--verbose", action="count", default=0, help="be verbose"
        )

        subparsers = parser.add_subparsers(
            dest="subcommand",
            required=True,
            title="subcommands",
            help="mode of the operation",
        )

        parser_backup = subparsers.add_parser(
            "backup", help="backup the sources specified in the configuration file"
        )
        parser_backup.add_argument(
            "-p",
            "--prune",
            action="store_true",
            help="prune after backup (can be costly on cloud storage)",
        )

        parser_restore = subparsers.add_parser(
            "restore", help="restore a snapshot into the specified directory"
        )
        parser_restore.add_argument(
            "-r",
            "--restore",
            required=True,
            metavar="DIR",
            help="directory to restore to (mandatory). The directory will be created if needed",
        )

        subparsers.add_parser("run", help="run the restic tool")

        parsed_args = parser.parse_known_args(arguments)
        restic_args = parsed_args[1]

        if len(restic_args) > 0 and restic_args[0] == "--":
            restic_args.pop(0)

        self.tool_arguments = vars(parsed_args[0])
        self.restic_arguments = restic_args
