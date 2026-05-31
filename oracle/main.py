"""Entry point for the Oracle CLI."""

import logging
import sys

from oracle.cli import run_cli


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the Oracle system.

    Args:
        debug: If True, set logging to DEBUG level with verbose output.
    """
    level = logging.DEBUG if debug else logging.WARNING

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s" if debug else "%(message)s",
        stream=sys.stderr,
    )

    # Set specific loggers
    if debug:
        logging.getLogger("oracle").setLevel(logging.DEBUG)
        logging.getLogger("oracle.tables").setLevel(logging.DEBUG)
        logging.getLogger("oracle.importers").setLevel(logging.DEBUG)
        logging.getLogger("oracle.fate").setLevel(logging.DEBUG)


def main():
    """Entry point for the oracle command."""
    # Check for --debug flag
    debug_mode = "--debug" in sys.argv

    if debug_mode:
        # Remove --debug from sys.argv so it doesn't confuse anything else
        sys.argv = [arg for arg in sys.argv if arg != "--debug"]
        print("[DEBUG MODE ENABLED]", file=sys.stderr)

    setup_logging(debug=debug_mode)

    # Log startup in debug mode
    if debug_mode:
        logger = logging.getLogger("oracle")
        logger.debug("Oracle CLI starting...")
        logger.debug(f"Python version: {sys.version}")
        logger.debug(f"Arguments: {sys.argv}")

    run_cli()


if __name__ == "__main__":
    main()
