"""
Parses the arguments for the restictool
"""

import argparse
from os import environ, path

DEFAULT_CONFIGURATION_FILE = "restictool.conf"
DEFAULT_CACHE_DIR = path.join(environ["HOME"], ".cache", ".restic")
DEFAULT_IMAGE = "restic/restic"
HELP_EPILOG = """
Use %(prog)s {backup,restore,run} --help to get the sub-command specific help.

The rest of the parameters are passed to the restic command. In case the first
parameter is a recognized optional one, use -- as a separator.

For backup the parameters to the restic are built from the configuration file.
The configuration is a YAML file with the following content:

TODO

For restore you need to specify at least the snapshot to restore. As seen from
the restic the dorecotry to restore to is /target and the snapshots created
with the backup commands are /volume/VOLNAME for docker volumes and
/localdir/TAG for locally specified ones.
"""


def parse():
    """Parses the restictool arguments

    Returns: a tuple of the restictol arguments as a dict and the restic ones as a list
    """
    parser = argparse.ArgumentParser(
        prog="restictool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="A Python wrapper for the dockerized restic tool",
        epilog=HELP_EPILOG,
    )

    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIGURATION_FILE,
        metavar="FILE",
        type=argparse.FileType("r"),
        help="the configuration file (default: %(default)s)",
    )
    parser.add_argument(
        "-t",
        "--cache",
        default=DEFAULT_CACHE_DIR,
        metavar="DIR",
        help="the cache directory (default: %(default)s)",
    )
    parser.add_argument(
        "-i",
        "--image",
        default=DEFAULT_IMAGE,
        help="the docker restic image name (default: to %(default)s)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="remain quiet")

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

    args = parser.parse_known_args()
    restic_args = args[1]

    if len(restic_args) > 0 and restic_args[0] == "--":
        restic_args.pop(0)

    return (vars(args[0]), restic_args)
