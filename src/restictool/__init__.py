"""
Exports the setuptools entrypoint
"""

from .entry_point import run

# The following imports are needed for the sphinx
from .restic_tool import ResticTool, Settings # noqa: F401,E261


def main():
    """Entry point for setuptools"""
    run()
