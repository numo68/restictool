"""
Fetch the arguments and run the selected functionality
"""
from .parse_arguments import parse


def run():
    """Run the tool"""
    args = parse()
    print(args)
