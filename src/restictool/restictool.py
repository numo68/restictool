from .parse_arguments import parse

import docker
import yaml


def run():
    args = parse()
    print(args)
