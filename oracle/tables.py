"""Table loader and roller for procedural generation.

This module handles loading weighted random tables from TOML files and
rolling on them. Tables are organized by setting and mood, with fallback
to neutral tables and core tables when specific files don't exist.
"""

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

# Use tomllib for Python 3.11+, tomli for earlier versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class TableEntry:
    """A single entry in a random table."""
    text: str
    weight: int = 1
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text


@dataclass
class Table:
    """A weighted random table."""
    name: str
    entries: list[TableEntry]
    description: str = ""
    source_path: Optional[Path] = None

    def __str__(self) -> str:
        header = f"Table: {self.name}"
        if self.description:
            header += f" - {self.description}"
        lines = [header, "-" * len(header)]
        for i, entry in enumerate(self.entries, 1):
            weight_str = f" (x{entry.weight})" if entry.weight > 1 else ""
            lines.append(f"  {i}. {entry.text}{weight_str}")
        return "\n".join(lines)

    @property
    def total_weight(self) -> int:
        """Sum of all entry weights."""
        return sum(e.weight for e in self.entries)

    def is_empty(self) -> bool:
        """Check if the table has no entries."""
        return len(self.entries) == 0


class TableLoader:
    """Loads tables from TOML files with fallback resolution."""

    def __init__(self, data_root: Optional[Path] = None):
        """Initialize the table loader.

        Args:
            data_root: Root path for table data. Defaults to oracle/data.
        """
        self._data_root = data_root or self._default_data_root()
        self._cache: dict[Path, Table] = {}

    def _default_data_root(self) -> Path:
        """Get the default data root path."""
        return Path(__file__).parent / "data"

    @property
    def data_root(self) -> Path:
        """Root path for table data files."""
        return self._data_root

    @data_root.setter
    def data_root(self, path: Path):
        """Set the data root path and clear cache."""
        self._data_root = path
        self._cache.clear()

    def clear_cache(self) -> None:
        """Clear the table cache."""
        self._cache.clear()

    def load_table(
        self,
        name: str,
        setting: str = "core",
        mood: str = "neutral",
        use_cache: bool = True
    ) -> Optional[Table]:
        """Load a table with fallback resolution.

        Resolution order:
        1. data/{setting}/{name}/{mood}.toml
        2. data/{setting}/{name}/neutral.toml
        3. data/core/{name}/{mood}.toml
        4. data/core/{name}/neutral.toml

        Args:
            name: Table name (e.g., "encounters", "npcs").
            setting: Setting folder name (e.g., "fantasy", "scifi_military").
            mood: Mood/tone folder name (e.g., "grimdark", "neutral").
            use_cache: If True, use cached tables when available.

        Returns:
            The loaded Table, or None if no table file exists.
        """
        # Build fallback paths
        paths = [
            self._data_root / setting / name / f"{mood}.toml",
            self._data_root / setting / name / "neutral.toml",
            self._data_root / "core" / name / f"{mood}.toml",
            self._data_root / "core" / name / "neutral.toml",
        ]

        # Try each path in order
        for path in paths:
            if path.exists():
                if use_cache and path in self._cache:
                    return self._cache[path]

                table = self._load_from_file(path)
                if table is not None:
                    if use_cache:
                        self._cache[path] = table
                    return table

        return None

    def load_from_path(self, path: Path, use_cache: bool = True) -> Optional[Table]:
        """Load a table directly from a specific path.

        Args:
            path: Path to the TOML file.
            use_cache: If True, use cached tables when available.

        Returns:
            The loaded Table, or None if file doesn't exist or is invalid.
        """
        if not path.exists():
            return None

        if use_cache and path in self._cache:
            return self._cache[path]

        table = self._load_from_file(path)
        if table is not None and use_cache:
            self._cache[path] = table

        return table

    def _load_from_file(self, path: Path) -> Optional[Table]:
        """Load and parse a table from a TOML file.

        Expected TOML format:
        ```toml
        name = "Encounters"
        description = "Random encounter table"

        [[entries]]
        text = "A wandering merchant"
        weight = 2
        tags = ["friendly", "commerce"]

        [[entries]]
        text = "Bandits!"
        weight = 1
        tags = ["hostile", "combat"]
        ```

        Args:
            path: Path to the TOML file.

        Returns:
            The parsed Table, or None on error.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            print(f"WARNING: skipping table file {path}: {e}", file=sys.stderr)
            return None

        # Parse table metadata
        name = data.get("name", path.stem)
        description = data.get("description", "")

        # Parse entries
        entries = []
        for entry_data in data.get("entries", []):
            if isinstance(entry_data, str):
                # Simple string entry
                entries.append(TableEntry(text=entry_data))
            elif isinstance(entry_data, dict):
                # Full entry with weight/tags
                text = entry_data.get("text", "")
                if text:
                    entries.append(TableEntry(
                        text=text,
                        weight=entry_data.get("weight", 1),
                        tags=entry_data.get("tags", []),
                        metadata={k: v for k, v in entry_data.items()
                                  if k not in ("text", "weight", "tags")}
                    ))

        return Table(
            name=name,
            entries=entries,
            description=description,
            source_path=path
        )

    def list_tables(self, setting: str = "core") -> list[str]:
        """List available table names for a setting.

        Args:
            setting: Setting folder to search.

        Returns:
            List of table names (folder names containing .toml files).
        """
        setting_path = self._data_root / setting
        if not setting_path.exists():
            return []

        tables = []
        for item in setting_path.iterdir():
            if item.is_dir():
                # Check if folder contains any .toml files
                if any(item.glob("*.toml")):
                    tables.append(item.name)

        return sorted(tables)


class TableRoller:
    """Rolls on tables using weighted random selection."""

    def __init__(self, rng: Optional[random.Random] = None):
        """Initialize the roller.

        Args:
            rng: Random number generator. Defaults to standard random.
        """
        self.rng = rng or random.Random()

    def roll(self, table: Table) -> Optional[TableEntry]:
        """Roll once on a table.

        Args:
            table: The table to roll on.

        Returns:
            The selected TableEntry, or None if table is empty.
        """
        if table.is_empty():
            return None

        total = table.total_weight
        roll = self.rng.randint(1, total)

        cumulative = 0
        for entry in table.entries:
            cumulative += entry.weight
            if roll <= cumulative:
                return entry

        # Should not reach here, but return last entry as fallback
        return table.entries[-1]

    def roll_many(self, table: Table, count: int, allow_duplicates: bool = True) -> list[TableEntry]:
        """Roll multiple times on a table.

        Args:
            table: The table to roll on.
            count: Number of times to roll.
            allow_duplicates: If False, don't return the same entry twice.

        Returns:
            List of selected TableEntries.
        """
        if table.is_empty():
            return []

        results = []

        if allow_duplicates:
            for _ in range(count):
                entry = self.roll(table)
                if entry:
                    results.append(entry)
        else:
            # Create a working copy of entries with weights
            available = [(e, e.weight) for e in table.entries]
            for _ in range(min(count, len(available))):
                if not available:
                    break

                total = sum(w for _, w in available)
                roll = self.rng.randint(1, total)

                cumulative = 0
                for i, (entry, weight) in enumerate(available):
                    cumulative += weight
                    if roll <= cumulative:
                        results.append(entry)
                        available.pop(i)
                        break

        return results

    def roll_text(self, table: Table) -> str:
        """Roll and return just the text result.

        Args:
            table: The table to roll on.

        Returns:
            The text of the selected entry, or empty string if table is empty.
        """
        entry = self.roll(table)
        return entry.text if entry else ""


@dataclass
class RollResult:
    """Result of a table roll with metadata."""
    entry: TableEntry
    table_name: str
    source_path: Optional[Path] = None

    def __str__(self) -> str:
        return f"{self.table_name}: {self.entry.text}"


# Module-level instances
_loader = TableLoader()
_roller = TableRoller()


def load_table(
    name: str,
    setting: str = "core",
    mood: str = "neutral"
) -> Optional[Table]:
    """Load a table using the default loader."""
    return _loader.load_table(name, setting, mood)


def roll_table(table: Table) -> Optional[TableEntry]:
    """Roll on a table using the default roller."""
    return _roller.roll(table)


def roll_on(
    name: str,
    setting: str = "core",
    mood: str = "neutral"
) -> Optional[RollResult]:
    """Load and roll on a table in one call.

    Args:
        name: Table name.
        setting: Setting folder name.
        mood: Mood/tone name.

    Returns:
        RollResult with the selected entry, or None if table not found.
    """
    table = _loader.load_table(name, setting, mood)
    if table is None:
        return None

    entry = _roller.roll(table)
    if entry is None:
        return None

    return RollResult(
        entry=entry,
        table_name=table.name,
        source_path=table.source_path
    )


def set_data_root(path: Path) -> None:
    """Set the data root for the default loader."""
    _loader.data_root = path


def list_tables(setting: str = "core") -> list[str]:
    """List available tables for a setting."""
    return _loader.list_tables(setting)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if "--help" in args or "-h" in args or not args:
        print("Oracle Table Roller")
        print()
        print("Usage: python -m oracle.tables <table> [options]")
        print()
        print("Options:")
        print("  --setting <name>  Use tables from specific setting")
        print("  --mood <tone>     Use mood-specific table variant")
        print("  --count <n>       Roll multiple times")
        print("  --list            List available tables")
        print()
        print("Examples:")
        print("  python -m oracle.tables complications")
        print("  python -m oracle.tables npcs/names --setting fantasy")
        print("  python -m oracle.tables encounters --setting weird_war --mood grimdark")
        print("  python -m oracle.tables --list --setting core")
    else:
        table_name = None
        setting = "core"
        mood = "neutral"
        count = 1

        i = 0
        while i < len(args):
            if args[i] == "--setting" and i + 1 < len(args):
                setting = args[i + 1]
                i += 2
            elif args[i] == "--mood" and i + 1 < len(args):
                mood = args[i + 1]
                i += 2
            elif args[i] == "--count" and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                except ValueError:
                    count = 1
                i += 2
            elif args[i] == "--list":
                print(f"Available tables in '{setting}':")
                for t in list_tables(setting):
                    print(f"  - {t}")
                sys.exit(0)
            elif not args[i].startswith("-"):
                table_name = args[i]
                i += 1
            else:
                i += 1

        if table_name:
            for _ in range(count):
                result = roll_on(table_name, setting, mood)
                if result:
                    print(result.entry.text)
                else:
                    print(f"Table '{table_name}' not found in {setting}/{mood}")
                    break
