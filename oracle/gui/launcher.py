"""
Birthright Campaign Manager Launcher

Entry point for launching the GUI application.
Can be run directly or invoked from the Oracle CLI.
"""

import sys
from pathlib import Path


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    missing = []

    try:
        import dearpygui
    except ImportError:
        missing.append("dearpygui")

    if missing:
        print("Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def launch():
    """Launch the Birthright Campaign Manager GUI."""
    if not check_dependencies():
        sys.exit(1)

    # Import here to avoid import errors if dependencies missing
    from oracle.gui.app import BirthrightApp

    print("Launching Birthright Campaign Manager...")
    app = BirthrightApp()
    app.run()


def main():
    """Main entry point."""
    launch()


if __name__ == "__main__":
    main()
