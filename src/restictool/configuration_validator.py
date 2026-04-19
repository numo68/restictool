"""Validates the configuration schema"""

import typing

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
        Optional("common"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
        Optional("forget"): Or(
            Schema([And(Schema(Use(str)), lambda s: len(s) > 0)]), Schema(None)
        ),
        Optional("prune"): Or(
            Schema([And(Schema(Use(str)), lambda s: len(s) > 0)]), Schema(None)
        ),
        Optional("volume"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
        Optional("localdir"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
    },
)

VOLUME_SCHEMA = Schema(
    {
        "name": And(str, lambda s: len(s) > 0),
        Optional("exclude"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
        Optional("options"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
    },
)

LOCALDIR_SCHEMA = Schema(
    {
        "name": And(str, lambda s: len(s) > 0),
        "path": And(str, lambda s: len(s) > 0),
        Optional("options"): [And(Schema(Use(str)), lambda s: len(s) > 0)],
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


def validate(config: typing.Any) -> typing.Any:
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
