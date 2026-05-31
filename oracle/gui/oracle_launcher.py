"""
Oracle GUI Launcher

Entry point for the unified Oracle GUI application.
Provides a windowed interface for solo RPG, wargaming,
and Birthright campaign management.
"""

import sys
from pathlib import Path


def main():
    """Launch the Oracle GUI application."""
    # Ensure the oracle package is importable
    oracle_root = Path(__file__).parent.parent.parent
    if str(oracle_root) not in sys.path:
        sys.path.insert(0, str(oracle_root))

    # Check for required dependencies
    try:
        import dearpygui.dearpygui
    except ImportError:
        print("Error: dearpygui not installed.")
        print("Install with: pip install dearpygui>=1.9")
        sys.exit(1)

    # Launch the application
    from oracle.gui.oracle_app import OracleApp

    app = OracleApp()
    app.run()


if __name__ == "__main__":
    main()
