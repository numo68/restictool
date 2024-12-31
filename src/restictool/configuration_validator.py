"""Validates the configuration schema"""

from schema import Schema, And, Or, Optional, Use

REPOSITORY_SCHEMA = Schema(
    {
        "location": And(str, lambda s: len(s) > 0),
        "password": And(str, lambda s: len(s) > 0),
        Optional("host"): And(str, lambda s: len(s) > 0),
        Optional("network_from"): And(str, lambda s: len(s) > 0),
        Optional("authentication"): {str: str},
        Optional("extra"): {str: str},
    },
)

METRICS_SCHEMA = Schema(
    {
        "directory": And(str, lambda s: len(s) > 0),
        Optional("suffix"): And(str, lambda s: len(s) > 0),
    },
)

OPTIONS_SCHEMA = Schema(
    {
        Optional("common"): [And(Use(str), lambda s: len(s) > 0)],
        Optional("forget"): [And(Use(str), lambda s: len(s) > 0)],
        Optional("prune"): Or([And(Use(str), lambda s: len(s) > 0)], None),
        Optional("volume"): [And(Use(str), lambda s: len(s) > 0)],
        Optional("localdir"): [And(Use(str), lambda s: len(s) > 0)],
    },
)

VOLUME_SCHEMA = Schema(
    {
        "name": And(str, lambda s: len(s) > 0),
        Optional("exclude"): [And(Use(str), lambda s: len(s) > 0)],
        Optional("options"): [And(Use(str), lambda s: len(s) > 0)],
    },
)

LOCALDIR_SCHEMA = Schema(
    {
        "name": And(str, lambda s: len(s) > 0),
        "path": And(str, lambda s: len(s) > 0),
        Optional("options"): [And(Use(str), lambda s: len(s) > 0)],
    },
)

SCHEMA = Schema(
    {
        "repository": REPOSITORY_SCHEMA,
        Optional("logging"): dict,
        Optional("metrics"): METRICS_SCHEMA,
        Optional("options"): OPTIONS_SCHEMA,
        Optional("volumes"): [VOLUME_SCHEMA],
        Optional("localdirs"): [LOCALDIR_SCHEMA],
    },
)


def validate(config):
    """Validate the configuration file.

    Parameters
    ----------
    config : object
        Configuration to validate.

    Returns
    -------
    object
        Validated configuration.
    """

    return SCHEMA.validate(config)
