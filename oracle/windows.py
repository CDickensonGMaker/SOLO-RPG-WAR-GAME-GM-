"""Pop-out reference window system for Oracle.

Spawns separate terminal windows displaying reference information
that can be kept open alongside the main Oracle CLI.
"""

import subprocess
import sys
import json
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class WindowType(Enum):
    """Types of reference windows available."""
    BLOODLINES = "bloodlines"
    BLOOD_ABILITIES = "blood_abilities"
    DOMAIN_ACTIONS = "domain_actions"
    RANDOM_EVENTS = "random_events"
    REGENTS = "regents"
    PROVINCES = "provinces"
    REALM_SPELLS = "realm_spells"
    UNIT_CARDS = "unit_cards"
    QUICK_REFERENCE = "quick_reference"
    CHARACTER_SHEET = "character"
    CUSTOM = "custom"


@dataclass
class WindowConfig:
    """Configuration for a pop-out window."""
    title: str
    width: int = 80
    height: int = 40
    content_file: Optional[str] = None
    content_type: str = "toml"  # toml, json, text


# Pre-configured windows for Birthright
BIRTHRIGHT_WINDOWS = {
    WindowType.BLOODLINES: WindowConfig(
        title="Birthright - Bloodlines",
        content_file="birthright/bloodlines/derivations.toml",
    ),
    WindowType.BLOOD_ABILITIES: WindowConfig(
        title="Birthright - Blood Abilities",
        content_file="birthright/bloodlines/blood_abilities.toml",
    ),
    WindowType.DOMAIN_ACTIONS: WindowConfig(
        title="Birthright - Domain Actions",
        content_file="birthright/domains/actions.toml",
    ),
    WindowType.RANDOM_EVENTS: WindowConfig(
        title="Birthright - Random Events",
        content_file="birthright/domains/random_events.toml",
    ),
    WindowType.REGENTS: WindowConfig(
        title="Birthright - Anuire Regents",
        content_file="birthright/cerilia/anuire/regents.toml",
    ),
    WindowType.PROVINCES: WindowConfig(
        title="Birthright - Anuire Provinces",
        content_file="birthright/cerilia/anuire/provinces.toml",
    ),
    WindowType.REALM_SPELLS: WindowConfig(
        title="Birthright - Realm Spells",
        content_file="birthright/magic/realm_spells.toml",
    ),
    WindowType.UNIT_CARDS: WindowConfig(
        title="Birthright - Military Units",
        content_file="birthright/warfare/unit_cards.toml",
    ),
    WindowType.QUICK_REFERENCE: WindowConfig(
        title="Birthright - Quick Reference",
        content_file="birthright/rules/quick_reference.toml",
    ),
}


def get_data_path() -> Path:
    """Get the Oracle data directory path."""
    return Path(__file__).parent / "data"


def spawn_reference_window(
    window_type: WindowType,
    custom_content: Optional[str] = None,
    custom_title: Optional[str] = None
) -> bool:
    """
    Spawn a new terminal window with reference content.

    Args:
        window_type: Type of reference window to open
        custom_content: For CUSTOM type, the content to display
        custom_title: For CUSTOM type, the window title

    Returns:
        True if window was spawned successfully
    """
    if window_type == WindowType.CUSTOM:
        if not custom_content:
            return False
        title = custom_title or "Oracle Reference"
        content = custom_content
    else:
        config = BIRTHRIGHT_WINDOWS.get(window_type)
        if not config:
            return False

        title = config.title
        content_path = get_data_path() / config.content_file

        if not content_path.exists():
            return False

        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()

    # Create a temporary Python script that displays the content
    script = _create_viewer_script(title, content)

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    # Spawn new terminal window
    try:
        if sys.platform == "win32":
            # Windows: use 'start' command
            subprocess.Popen(
                f'start "{title}" cmd /k python "{script_path}"',
                shell=True
            )
        elif sys.platform == "darwin":
            # macOS: use osascript
            subprocess.Popen([
                "osascript", "-e",
                f'tell app "Terminal" to do script "python3 {script_path}"'
            ])
        else:
            # Linux: try common terminal emulators
            for terminal in ["gnome-terminal", "xterm", "konsole"]:
                try:
                    subprocess.Popen([terminal, "-e", f"python3 {script_path}"])
                    break
                except FileNotFoundError:
                    continue
        return True
    except Exception:
        return False


def _create_viewer_script(title: str, content: str) -> str:
    """Create a Python script that displays content with scrolling."""
    # Escape content for embedding
    content_escaped = json.dumps(content)

    return f'''#!/usr/bin/env python3
"""Oracle Reference Window: {title}"""

import os
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

TITLE = {json.dumps(title)}
CONTENT = {content_escaped}

def main():
    if sys.platform == "win32":
        os.system(f"title {{TITLE}}")

    if HAS_RICH:
        console = Console()
        console.print(Panel(f"[bold cyan]{{TITLE}}[/bold cyan]", border_style="cyan"))
        console.print()

        # Try to syntax highlight TOML
        if "[[" in CONTENT or "[" in CONTENT.split("\\n")[0]:
            syntax = Syntax(CONTENT, "toml", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(CONTENT)
    else:
        print("=" * 60)
        print(TITLE)
        print("=" * 60)
        print()
        print(CONTENT)

    print()
    print("-" * 60)
    input("Press Enter to close this window...")

if __name__ == "__main__":
    main()
'''


def spawn_character_window(character_data: dict) -> bool:
    """
    Spawn a window showing the current character sheet.

    Args:
        character_data: Character data dictionary

    Returns:
        True if window spawned successfully
    """
    from oracle.birthright_character import format_character_sheet

    content = format_character_sheet(character_data)
    return spawn_reference_window(
        WindowType.CUSTOM,
        custom_content=content,
        custom_title=f"Character: {character_data.get('name', 'Unknown')}"
    )


def list_available_windows() -> list[tuple[str, str]]:
    """Return list of (window_type, description) for available windows."""
    return [
        ("bloodlines", "Bloodline derivations and descriptions"),
        ("blood_abilities", "All blood abilities with 5e mechanics"),
        ("domain_actions", "Domain action reference"),
        ("random_events", "Random event tables"),
        ("regents", "Anuirean NPC regents"),
        ("provinces", "Anuire province data"),
        ("realm_spells", "Realm magic spells"),
        ("unit_cards", "Military unit statistics"),
        ("quick_reference", "Quick reference tables"),
        ("character", "Current character sheet"),
    ]


# CLI integration helper
def open_window_by_name(name: str, character_data: Optional[dict] = None) -> bool:
    """
    Open a window by its string name.

    Args:
        name: Window type name (e.g., "bloodlines", "regents")
        character_data: Required if name is "character"

    Returns:
        True if successful
    """
    name = name.lower().strip()

    if name == "character":
        if character_data:
            return spawn_character_window(character_data)
        return False

    # Map string names to WindowType
    name_map = {
        "bloodlines": WindowType.BLOODLINES,
        "blood": WindowType.BLOODLINES,
        "abilities": WindowType.BLOOD_ABILITIES,
        "blood_abilities": WindowType.BLOOD_ABILITIES,
        "domain": WindowType.DOMAIN_ACTIONS,
        "actions": WindowType.DOMAIN_ACTIONS,
        "domain_actions": WindowType.DOMAIN_ACTIONS,
        "events": WindowType.RANDOM_EVENTS,
        "random": WindowType.RANDOM_EVENTS,
        "random_events": WindowType.RANDOM_EVENTS,
        "regents": WindowType.REGENTS,
        "npcs": WindowType.REGENTS,
        "provinces": WindowType.PROVINCES,
        "map": WindowType.PROVINCES,
        "spells": WindowType.REALM_SPELLS,
        "realm": WindowType.REALM_SPELLS,
        "realm_spells": WindowType.REALM_SPELLS,
        "magic": WindowType.REALM_SPELLS,
        "units": WindowType.UNIT_CARDS,
        "military": WindowType.UNIT_CARDS,
        "army": WindowType.UNIT_CARDS,
        "unit_cards": WindowType.UNIT_CARDS,
        "quick": WindowType.QUICK_REFERENCE,
        "reference": WindowType.QUICK_REFERENCE,
        "ref": WindowType.QUICK_REFERENCE,
        "quick_reference": WindowType.QUICK_REFERENCE,
    }

    window_type = name_map.get(name)
    if window_type:
        return spawn_reference_window(window_type)
    return False
