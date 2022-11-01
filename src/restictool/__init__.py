"""
Exports the setuptools entrypoint
"""

from .entry_point import run

# The following imports are needed for the sphinx
from .restic_tool import ResticTool, Settings

def main():
    """Entry point for setuptools"""
    run()
