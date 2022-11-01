"""Main entry point"""

import sys

from .restic_tool import ResticTool, ResticToolException
from .argument_parser import Arguments


def run():
    """Run the tool"""

    try:
        arguments = Arguments()
        arguments.parse()

        tool = ResticTool(arguments.to_settings())
        tool.setup()
        tool.run()
    except ResticToolException as ex:
        sys.exit(ex.exit_code)
    except Exception as ex:
        sys.stderr.write(str(ex.with_traceback(None)) + "\n")
        sys.exit(16)
