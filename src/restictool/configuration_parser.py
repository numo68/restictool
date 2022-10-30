"""
Parses the configuration for the restictool
"""

import io
from schema import SchemaError
from yaml import safe_load

from .configuration_validator import validate


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
        config = safe_load(stream)

        if isinstance(stream, io.IOBase) and close:
            stream.close()

        try:
            self.configuration = validate(config)
        except SchemaError as ex:
            raise ValueError("configuration invalid\n" + str(ex.with_traceback(None))) from None
