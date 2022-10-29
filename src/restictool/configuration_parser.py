"""
Parses the configuration for the restictool
"""

import io
import sys
from schema import Schema, And, Use, Optional, SchemaError
from yaml import safe_load


class Configuration:
    """
    Parses the configuration
    """

    REPOSITORY_SCHEMA = Schema(
        {
            'name': And(str, lambda s: len(s) > 0),
            'password': And(str, lambda s: len(s) > 0),
            Optional('host'): And(str, lambda s: len(s) > 0),
            Optional('authentication'): And({str: str}),
            Optional('extra'): And({str: str}),
        },
    )

    SCHEMA = Schema(
        {
            'repository': And(REPOSITORY_SCHEMA),
            Optional(object) : object  # Note: remove when the schema is finished
        },
        ignore_extra_keys=True         # Note: remove when the schema is finished
    )

    def __init__(self):
        self.configuration = None

    def load(self, stream, close=True):
        """Loads the stream and does the initial parsing and sanity checking

        Args:
            stream (IOBase): configuration file opened as stream
            close (bool): close the stream after reading
        """
        config = safe_load(stream)

        if isinstance(stream, io.IOBase) and close:
            stream.close()

        self.configuration = self.SCHEMA.validate(config)
