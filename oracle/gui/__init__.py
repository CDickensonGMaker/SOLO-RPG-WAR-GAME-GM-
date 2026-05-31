"""
Oracle GUI Suite

Desktop GUI applications for solo tabletop gaming:
- Oracle App: Unified solo GM with chat interface
- Birthright Campaign Manager: Domain-level Cerilia campaigns

Built with Dear PyGui for a native desktop experience.
"""

__version__ = "1.0.0"
__author__ = "Oracle Project"

from oracle.gui.app import BirthrightApp
from oracle.gui.launcher import launch
from oracle.gui.oracle_app import OracleApp
from oracle.gui.oracle_launcher import main as launch_oracle

__all__ = [
    "BirthrightApp",
    "OracleApp",
    "launch",
    "launch_oracle"
]
