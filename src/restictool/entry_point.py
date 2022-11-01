"""Main entry point"""

from .restic_tool import ResticTool
from .argument_parser import Arguments


def run():
    """Run the tool"""
    arguments = Arguments()
    arguments.parse()

    tool = ResticTool(arguments.to_settings())
    tool.setup()
    tool.run()
