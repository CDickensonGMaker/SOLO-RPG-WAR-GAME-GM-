"""Shared TOML loading with readable errors.

Every module that reads a TOML file should use load_toml() instead of
calling tomllib.load() directly, so a bad file produces a readable
one-line warning (or a clear exception) instead of a raw stack trace.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any, Optional


def load_toml(path: str | Path, *, required: bool = False) -> Optional[dict[str, Any]]:
    """Load a TOML file, giving a readable error instead of a stack trace.

    Args:
        path: Path to the TOML file.
        required: If True, raise RuntimeError on any failure instead of
            warning and returning None.

    Returns:
        The parsed dict, or None if the file is missing/invalid and
        required is False.
    """
    path = Path(path)
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        msg = f"TOML file not found: {path}"
    except tomllib.TOMLDecodeError as e:
        msg = f"Bad TOML in {path}: {e}"
    except OSError as e:
        msg = f"Cannot read {path}: {e}"
    if required:
        raise RuntimeError(msg)
    print(f"WARNING: {msg}", file=sys.stderr)
    return None
