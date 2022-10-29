"""
Fetch the arguments and run the selected functionality
"""
from .argument_parser import Arguments
from .configuration_parser import Configuration


def run():
    """Run the tool"""
    parser = Arguments()
    parser.parse(None)
    config = Configuration()
    config.load("repository:\n  name: a\n  password: 'aaa'\n  host: aa\n  authentication:\n    aaa: bbb\n  extra:\n    sss: ccc\n")
