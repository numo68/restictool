"""
Fetch the arguments and run the selected functionality
"""
from .argument_parser import Arguments


def run():
    """Run the tool"""
    parser = Arguments()
    parser.parse(None)
    print(parser.tool_arguments)
    print(parser.restic_arguments)
