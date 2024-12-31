"""Parses the arguments for the restictool
"""

import argparse
from .settings import Settings, SubCommand

class Arguments:
    """Parses the arguments for the restictool"""

    _HELP_EPILOG = """
    Use %(prog)s {backup,restore,run} --help to get the subcommand
    specific help.

    The rest of the arguments are passed to the restic command. In case the
    first arguments is a recognized optional one, use -- as a separator.
    """

    def __init__(self):
        self.tool_arguments = None
        self.restic_arguments = None
        self.version = "0.7.0"

    def parse(self, arguments=None) -> Settings:
        """Parses the restictool arguments

        Args:
            arguments (list): list of arguments to parse

        Returns: a tuple of the restictol arguments as a dict and the restic ones as a list
        """
        parser = argparse.ArgumentParser(
            prog="restictool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description="A Python wrapper for the dockerized restic tool (v"+self.version+")",
            epilog=self._HELP_EPILOG,
        )

        parser.add_argument(
            "-c",
            "--config",
            default=Settings.DEFAULT_CONFIGURATION_FILE,
            metavar="FILE",
            type=argparse.FileType("r"),
            help="the configuration file (default: %(default)s)",
        )
        parser.add_argument(
            "--cache",
            default=Settings.DEFAULT_CACHE_DIR,
            metavar="DIR",
            help="the cache directory (default: %(default)s)",
        )
        parser.add_argument(
            "--image",
            default=Settings.DEFAULT_IMAGE,
            help="the docker restic image name (default: %(default)s)",
        )
        parser.add_argument(
            "--force-pull",
            action="store_true",
            help="force pulling of the docker image first",
        )

        parser.add_argument(
            "--log-level",
            choices=["critical", "error", "warning", "info", "debug"],
            default="warning",
            help="set the logging level (default: %(default)s)",
        )

        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="silence output from the restic",
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
        parser_restore.add_argument(
            "snapshot",
            metavar="SNAPSHOT",
            nargs="?",
            default="latest",
            help="snapshot to restore from (default: %(default)s)",
        )

        subparsers.add_parser("dockerdr", help="restore all docker volumes")
        subparsers.add_parser("snapshots", help="list the snapshots in the repository")
        subparsers.add_parser("run", help="run the restic tool")
        subparsers.add_parser("exists", help="check whether the repository exists")
        subparsers.add_parser("check", help="check the configuration file")

        parsed_args = parser.parse_known_args(arguments)
        restic_args = parsed_args[1]

        if len(restic_args) > 0 and restic_args[0] == "--":
            restic_args.pop(0)

        self.tool_arguments = vars(parsed_args[0])
        self.restic_arguments = restic_args

    def to_settings(self) -> Settings:
        """Convert the parsed arguments to the settings class"""
        settings = Settings()

        settings.subcommand = SubCommand[self.tool_arguments["subcommand"].upper()]
        settings.image = self.tool_arguments["image"]
        settings.force_pull = self.tool_arguments["force_pull"]
        settings.configuration_stream = self.tool_arguments["config"]
        settings.cache_directory = self.tool_arguments["cache"]
        settings.log_level = self.tool_arguments["log_level"].upper()
        settings.quiet = self.tool_arguments["quiet"]
        if "restore" in self.tool_arguments:
            settings.restore_directory = self.tool_arguments["restore"]
            settings.restore_snapshot = self.tool_arguments["snapshot"]
        settings.restic_arguments = self.restic_arguments

        return settings
