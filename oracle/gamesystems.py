"""
Game systems module for wargame-specific unit profiles and rules.

Supports multiple wargame systems with locally-stored unit data.
No internet connection required at runtime - all data is stored in TOML files
under data/wargames/{system_id}/factions/*.toml

Supported Systems:
    - Oldhammer 40K 2nd Edition
    - Warhammer 40K 10th Edition
    - Kill Team
    - Warhammer: The Old World
    - Warhammer Fantasy 6th Edition
    - Grimdark Future (One Page Rules)
    - Age of Fantasy (One Page Rules)
    - Grimdark Future: Firefight
    - Age of Fantasy: Skirmish
    - Trench Crusade
    - Generic Wargame

Example Usage:
    >>> from oracle.gamesystems import set_game_system, set_faction, lookup_unit
    >>> set_game_system("grimdark future")
    True
    >>> set_faction("battle brothers")
    True
    >>> unit = lookup_unit("assault brothers")
    >>> print(unit)
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Iterator
import json

# Try tomllib (3.11+) or tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore


class GameSystem(Enum):
    """
    Supported wargame systems.

    Each system has an ID (used for directory names) and a display name
    (used for user-facing output).

    Attributes:
        id: Short identifier used for file paths
        display_name: Human-readable name for display
    """
    # Warhammer 40k variants
    OLDHAMMER_2E = ("oldhammer_2e", "Oldhammer 40K 2nd Edition")
    WH40K_10E = ("wh40k_10e", "Warhammer 40K 10th Edition")
    KILL_TEAM = ("kill_team", "Kill Team")

    # Warhammer Fantasy variants
    OLD_WORLD = ("old_world", "Warhammer: The Old World")
    WHFB_6E = ("whfb_6e", "Warhammer Fantasy 6th Edition")

    # One Page Rules (completely free)
    GRIMDARK_FUTURE = ("grimdark_future", "Grimdark Future")
    AGE_OF_FANTASY = ("age_of_fantasy", "Age of Fantasy")
    GF_FIREFIGHT = ("gf_firefight", "Grimdark Future: Firefight")
    AOF_SKIRMISH = ("aof_skirmish", "Age of Fantasy: Skirmish")

    # Independent games
    TRENCH_CRUSADE = ("trench_crusade", "Trench Crusade")

    # Generic
    GENERIC = ("generic", "Generic Wargame")

    def __init__(self, id: str, display_name: str):
        self.id = id
        self.display_name = display_name

    @classmethod
    def from_id(cls, system_id: str) -> Optional["GameSystem"]:
        """
        Get a GameSystem by its ID.

        Args:
            system_id: The system ID to look up

        Returns:
            The matching GameSystem or None if not found
        """
        for system in cls:
            if system.id == system_id:
                return system
        return None


class UnitType(Enum):
    """
    Unit classifications for tactical categorization.

    These types help the tactical AI understand unit capabilities
    and make appropriate decisions.
    """
    INFANTRY = "infantry"
    CAVALRY = "cavalry"
    MONSTER = "monster"
    VEHICLE = "vehicle"
    CHARACTER = "character"
    WARMACHINE = "warmachine"
    SWARM = "swarm"
    FLYER = "flyer"

    @classmethod
    def from_string(cls, value: str) -> "UnitType":
        """
        Convert a string to UnitType, defaulting to INFANTRY.

        Args:
            value: String representation of unit type

        Returns:
            Matching UnitType or INFANTRY as default
        """
        try:
            return cls(value.lower())
        except ValueError:
            return cls.INFANTRY


@dataclass
class WeaponProfile:
    """
    A weapon's statistics and special abilities.

    Weapon profiles are flexible enough to represent weapons from
    different game systems with varying stat lines.

    Attributes:
        name: Weapon name
        range: Range value (e.g., "24\"", "Melee", "Template")
        strength: Strength value or formula (e.g., "4", "User+1")
        ap: Armor penetration or save modifier
        damage: Damage per successful hit
        abilities: List of special rules/abilities
        type: Weapon type (Assault, Heavy, Rapid Fire, etc.)
        shots: Number of attacks/shots
    """
    name: str
    range: str  # e.g., "24\"", "Melee", "Template"
    strength: str  # Could be number or formula like "User+1"
    ap: str  # Armor penetration/save modifier
    damage: str  # Damage per hit
    abilities: list[str] = field(default_factory=list)
    type: str = ""  # Assault, Heavy, Rapid Fire, etc.
    shots: str = "1"

    def __str__(self) -> str:
        """Format weapon profile as a single line."""
        parts = [f"{self.name}:"]
        if self.range and self.range.lower() != "melee":
            parts.append(f"Rng {self.range}")
        parts.append(f"S{self.strength}")
        if self.ap and self.ap != "0" and self.ap != "-":
            parts.append(f"AP{self.ap}")
        parts.append(f"D{self.damage}")
        if self.shots != "1":
            parts.append(f"({self.shots} shots)")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert weapon profile to dictionary for serialization.

        Returns:
            Dictionary representation of the weapon profile
        """
        return {
            "name": self.name,
            "range": self.range,
            "strength": self.strength,
            "ap": self.ap,
            "damage": self.damage,
            "abilities": self.abilities,
            "type": self.type,
            "shots": self.shots,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeaponProfile":
        """
        Create a WeaponProfile from a dictionary.

        Args:
            data: Dictionary with weapon data

        Returns:
            WeaponProfile instance
        """
        return cls(
            name=data.get("name", "Unknown"),
            range=str(data.get("range", "Melee")),
            strength=str(data.get("strength", "3")),
            ap=str(data.get("ap", "0")),
            damage=str(data.get("damage", "1")),
            abilities=data.get("abilities", []),
            type=data.get("type", ""),
            shots=str(data.get("shots", "1")),
        )


@dataclass
class UnitProfile:
    """
    A unit's complete profile including stats, weapons, and tactical hints.

    Unit profiles contain all information needed for both display and
    tactical AI decision making.

    Attributes:
        name: Unit name
        game_system: ID of the game system this unit belongs to
        faction: Faction name
        unit_type: Classification (infantry, vehicle, etc.)
        stats: Core statistics as a flexible dictionary
        weapons: List of weapon profiles
        wargear: List of additional equipment names
        special_rules: List of special rule names
        keywords: List of keywords for rules interactions
        points_cost: Points value for army building
        models_per_unit: Number of models (e.g., "5-10" for variable)
        tactical_role: AI hint for unit purpose
        threat_level: AI hint for prioritization
        preferred_targets: AI hint for target selection
        weaknesses: AI hint for vulnerability assessment
    """
    name: str
    game_system: str
    faction: str
    unit_type: UnitType

    # Core stats (flexible dict for different game systems)
    stats: dict[str, Any] = field(default_factory=dict)

    # Equipment
    weapons: list[WeaponProfile] = field(default_factory=list)
    wargear: list[str] = field(default_factory=list)

    # Rules
    special_rules: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Points
    points_cost: int = 0
    models_per_unit: str = "1"  # e.g., "5-10"

    # Tactical hints for AI
    tactical_role: str = ""  # e.g., "assault", "fire_support", "objective_holder"
    threat_level: str = "medium"  # low, medium, high, extreme
    preferred_targets: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Format unit profile as a multi-line display string."""
        lines = [
            f"{'=' * 3} {self.name} {'=' * 3}",
            f"Faction: {self.faction} | Type: {self.unit_type.value}",
            f"Points: {self.points_cost} | Models: {self.models_per_unit}",
            "",
            "STATS:",
        ]
        for stat, value in self.stats.items():
            lines.append(f"  {stat}: {value}")

        if self.weapons:
            lines.append("")
            lines.append("WEAPONS:")
            for w in self.weapons:
                lines.append(f"  {w}")

        if self.wargear:
            lines.append("")
            lines.append("WARGEAR:")
            for item in self.wargear:
                lines.append(f"  - {item}")

        if self.special_rules:
            lines.append("")
            lines.append("SPECIAL RULES:")
            for rule in self.special_rules:
                lines.append(f"  * {rule}")

        if self.keywords:
            lines.append("")
            lines.append(f"KEYWORDS: {', '.join(self.keywords)}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert unit profile to dictionary for serialization.

        Returns:
            Dictionary representation of the unit profile
        """
        return {
            "name": self.name,
            "game_system": self.game_system,
            "faction": self.faction,
            "type": self.unit_type.value,
            "stats": self.stats,
            "weapons": [w.to_dict() for w in self.weapons],
            "wargear": self.wargear,
            "special_rules": self.special_rules,
            "keywords": self.keywords,
            "points": self.points_cost,
            "models": self.models_per_unit,
            "tactical_role": self.tactical_role,
            "threat_level": self.threat_level,
            "preferred_targets": self.preferred_targets,
            "weaknesses": self.weaknesses,
        }

    def matches_keyword(self, keyword: str) -> bool:
        """
        Check if unit has a specific keyword (case-insensitive).

        Args:
            keyword: Keyword to search for

        Returns:
            True if keyword is present
        """
        keyword_lower = keyword.lower()
        return any(kw.lower() == keyword_lower for kw in self.keywords)

    def has_special_rule(self, rule: str) -> bool:
        """
        Check if unit has a specific special rule (case-insensitive partial match).

        Args:
            rule: Rule name to search for

        Returns:
            True if rule is present
        """
        rule_lower = rule.lower()
        return any(rule_lower in sr.lower() for sr in self.special_rules)

    def get_stat(self, stat_name: str, default: Any = None) -> Any:
        """
        Get a specific stat value.

        Args:
            stat_name: Name of the stat (case-insensitive)
            default: Value to return if stat not found

        Returns:
            Stat value or default
        """
        # Try exact match first
        if stat_name in self.stats:
            return self.stats[stat_name]
        # Try case-insensitive match
        stat_lower = stat_name.lower()
        for key, value in self.stats.items():
            if key.lower() == stat_lower:
                return value
        return default


@dataclass
class Faction:
    """
    A faction/army with its units and tactical information.

    Factions group units together and provide army-wide information
    useful for tactical AI decisions.

    Attributes:
        name: Faction name
        game_system: ID of the game system
        description: Flavor text description
        playstyle: Brief playstyle summary (e.g., "aggressive melee")
        strengths: List of faction advantages
        weaknesses: List of faction vulnerabilities
        units: Dictionary of unit names to profiles
    """
    name: str
    game_system: str
    description: str = ""
    playstyle: str = ""  # e.g., "aggressive melee", "defensive shooting"
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    units: dict[str, UnitProfile] = field(default_factory=dict)

    def get_unit(self, name: str) -> Optional[UnitProfile]:
        """
        Get a unit by name (case-insensitive).

        Args:
            name: Unit name to search for

        Returns:
            UnitProfile if found, None otherwise
        """
        name_lower = name.lower()
        for unit_name, unit in self.units.items():
            if unit_name.lower() == name_lower:
                return unit
        return None

    def search_units(self, query: str) -> list[UnitProfile]:
        """
        Search for units matching a query.

        Searches unit names, tactical roles, and keywords.

        Args:
            query: Search string

        Returns:
            List of matching unit profiles
        """
        results = []
        query_lower = query.lower()

        for unit in self.units.values():
            if (query_lower in unit.name.lower() or
                query_lower in unit.tactical_role.lower() or
                any(query_lower in kw.lower() for kw in unit.keywords)):
                results.append(unit)

        return results

    def units_by_type(self, unit_type: UnitType) -> list[UnitProfile]:
        """
        Get all units of a specific type.

        Args:
            unit_type: The unit type to filter by

        Returns:
            List of matching unit profiles
        """
        return [u for u in self.units.values() if u.unit_type == unit_type]

    def units_by_role(self, role: str) -> list[UnitProfile]:
        """
        Get all units with a specific tactical role.

        Args:
            role: Tactical role to filter by (partial match)

        Returns:
            List of matching unit profiles
        """
        role_lower = role.lower()
        return [u for u in self.units.values() if role_lower in u.tactical_role.lower()]

    def list_unit_names(self) -> list[str]:
        """
        Get sorted list of all unit names.

        Returns:
            Alphabetically sorted list of unit names
        """
        return sorted(self.units.keys())

    def __len__(self) -> int:
        """Return number of units in faction."""
        return len(self.units)

    def __iter__(self) -> Iterator[UnitProfile]:
        """Iterate over unit profiles."""
        return iter(self.units.values())


@dataclass
class RuleReference:
    """
    A rules reference entry for quick lookup.

    Attributes:
        name: Rule name
        description: Full rule text/explanation
        page_reference: Page number in rulebook (if applicable)
        examples: List of example applications
        keywords: Related keywords for search
    """
    name: str
    description: str
    page_reference: str = ""
    examples: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Format rule reference for display."""
        lines = [f"--- {self.name} ---"]
        if self.page_reference:
            lines.append(f"(Page {self.page_reference})")
        lines.append("")
        lines.append(self.description)

        if self.examples:
            lines.append("")
            lines.append("Examples:")
            for ex in self.examples:
                lines.append(f"  - {ex}")

        return "\n".join(lines)

    def matches_query(self, query: str) -> bool:
        """
        Check if rule matches a search query.

        Args:
            query: Search string

        Returns:
            True if rule matches query
        """
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in kw.lower() for kw in self.keywords)
        )


class GameSystemManager:
    """
    Manages game system data, faction loading, and unit lookups.

    The manager handles loading data from TOML files, maintaining
    the current game system and faction context, and providing
    search and lookup functionality.

    Attributes:
        data_dir: Path to the wargames data directory
    """

    # System aliases for flexible name matching
    SYSTEM_ALIASES: dict[str, GameSystem] = {
        # Oldhammer 2E aliases
        "oldhammer": GameSystem.OLDHAMMER_2E,
        "2nd edition": GameSystem.OLDHAMMER_2E,
        "2nd ed": GameSystem.OLDHAMMER_2E,
        "40k 2e": GameSystem.OLDHAMMER_2E,
        "40k 2nd": GameSystem.OLDHAMMER_2E,
        "rogue trader": GameSystem.OLDHAMMER_2E,
        "rt": GameSystem.OLDHAMMER_2E,

        # 40K 10E aliases
        "40k": GameSystem.WH40K_10E,
        "40k 10e": GameSystem.WH40K_10E,
        "40k 10th": GameSystem.WH40K_10E,
        "warhammer 40k": GameSystem.WH40K_10E,
        "warhammer 40000": GameSystem.WH40K_10E,
        "10th edition": GameSystem.WH40K_10E,

        # Old World aliases
        "old world": GameSystem.OLD_WORLD,
        "tow": GameSystem.OLD_WORLD,
        "the old world": GameSystem.OLD_WORLD,
        "warhammer fantasy": GameSystem.OLD_WORLD,

        # WHFB 6E aliases
        "whfb": GameSystem.WHFB_6E,
        "whfb 6e": GameSystem.WHFB_6E,
        "6th edition": GameSystem.WHFB_6E,
        "fantasy 6th": GameSystem.WHFB_6E,

        # Grimdark Future aliases
        "grimdark": GameSystem.GRIMDARK_FUTURE,
        "grimdark future": GameSystem.GRIMDARK_FUTURE,
        "gf": GameSystem.GRIMDARK_FUTURE,
        "opr 40k": GameSystem.GRIMDARK_FUTURE,
        "opr grimdark": GameSystem.GRIMDARK_FUTURE,

        # Age of Fantasy aliases
        "age of fantasy": GameSystem.AGE_OF_FANTASY,
        "aof": GameSystem.AGE_OF_FANTASY,
        "opr fantasy": GameSystem.AGE_OF_FANTASY,
        "opr aof": GameSystem.AGE_OF_FANTASY,

        # Firefight aliases
        "firefight": GameSystem.GF_FIREFIGHT,
        "gf firefight": GameSystem.GF_FIREFIGHT,
        "grimdark firefight": GameSystem.GF_FIREFIGHT,

        # AoF Skirmish aliases
        "aof skirmish": GameSystem.AOF_SKIRMISH,
        "fantasy skirmish": GameSystem.AOF_SKIRMISH,
        "skirmish": GameSystem.AOF_SKIRMISH,

        # Kill Team aliases
        "kill team": GameSystem.KILL_TEAM,
        "kt": GameSystem.KILL_TEAM,
        "killteam": GameSystem.KILL_TEAM,

        # Trench Crusade aliases
        "trench crusade": GameSystem.TRENCH_CRUSADE,
        "tc": GameSystem.TRENCH_CRUSADE,
        "trench": GameSystem.TRENCH_CRUSADE,
        "crusade": GameSystem.TRENCH_CRUSADE,

        # Generic aliases
        "generic": GameSystem.GENERIC,
        "custom": GameSystem.GENERIC,
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the game system manager.

        Args:
            data_dir: Path to wargames data directory. Defaults to
                     data/wargames relative to this module.
        """
        self.data_dir = data_dir or Path(__file__).parent / "data" / "wargames"
        self._current_system: Optional[GameSystem] = None
        self._current_faction: Optional[Faction] = None
        self._factions: dict[str, Faction] = {}
        self._rules: dict[str, RuleReference] = {}
        self._rng = random.Random()

    @property
    def current_system(self) -> Optional[GameSystem]:
        """Get the currently selected game system."""
        return self._current_system

    @property
    def current_faction(self) -> Optional[Faction]:
        """Get the currently selected faction."""
        return self._current_faction

    @property
    def factions(self) -> dict[str, Faction]:
        """Get all loaded factions for current system."""
        return self._factions.copy()

    @property
    def rules(self) -> dict[str, RuleReference]:
        """Get all loaded rules for current system."""
        return self._rules.copy()

    def list_systems(self) -> list[GameSystem]:
        """
        List all available game systems.

        Returns:
            List of all GameSystem enum values
        """
        return list(GameSystem)

    def list_available_systems(self) -> list[GameSystem]:
        """
        List game systems that have data files present.

        Returns:
            List of GameSystem values with existing data directories
        """
        available = []
        for system in GameSystem:
            system_dir = self.data_dir / system.id
            if system_dir.exists():
                factions_dir = system_dir / "factions"
                if factions_dir.exists() and any(factions_dir.glob("*.toml")):
                    available.append(system)
        return available

    def set_system(self, system: GameSystem) -> None:
        """
        Set the current game system and load its data.

        Clears any previously loaded data and loads the new system's
        factions and rules from disk.

        Args:
            system: The GameSystem to activate
        """
        self._current_system = system
        self._current_faction = None
        self._factions = {}
        self._rules = {}
        self._load_system_data(system)

    def set_system_by_name(self, name: str) -> bool:
        """
        Set system by name or alias.

        Supports flexible matching including common abbreviations
        and alternate names.

        Args:
            name: System name or alias (e.g., 'oldhammer', '40k 2nd', 'grimdark')

        Returns:
            True if system was found and set, False otherwise

        Examples:
            >>> manager.set_system_by_name("grimdark future")
            True
            >>> manager.set_system_by_name("gf")
            True
            >>> manager.set_system_by_name("oldhammer")
            True
        """
        name_lower = name.lower().strip()

        # Check aliases first
        if name_lower in self.SYSTEM_ALIASES:
            self.set_system(self.SYSTEM_ALIASES[name_lower])
            return True

        # Try matching enum values directly
        for system in GameSystem:
            if name_lower in system.display_name.lower() or name_lower == system.id:
                self.set_system(system)
                return True

        return False

    def _load_system_data(self, system: GameSystem) -> None:
        """
        Load faction and rules data for a game system from disk.

        Args:
            system: The GameSystem to load data for
        """
        if tomllib is None:
            return

        system_dir = self.data_dir / system.id
        if not system_dir.exists():
            return

        # Load factions
        factions_dir = system_dir / "factions"
        if factions_dir.exists():
            for faction_file in factions_dir.glob("*.toml"):
                faction = self._load_faction(faction_file, system)
                if faction:
                    self._factions[faction.name.lower()] = faction

        # Load rules references
        rules_file = system_dir / "rules.toml"
        if rules_file.exists():
            self._load_rules(rules_file)

    def _load_faction(self, path: Path, system: GameSystem) -> Optional[Faction]:
        """
        Load a faction from a TOML file.

        Args:
            path: Path to the faction TOML file
            system: The GameSystem this faction belongs to

        Returns:
            Loaded Faction or None on error
        """
        if tomllib is None:
            return None

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            faction = Faction(
                name=data.get("name", path.stem.replace("_", " ").title()),
                game_system=system.id,
                description=data.get("description", ""),
                playstyle=data.get("playstyle", ""),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
            )

            # Load units
            for unit_data in data.get("units", []):
                unit = self._parse_unit(unit_data, system, faction.name)
                faction.units[unit.name] = unit

            return faction
        except Exception as e:
            # Silently fail for individual faction files
            return None

    def _parse_unit(self, data: dict, system: GameSystem, faction: str) -> UnitProfile:
        """
        Parse a unit from TOML data.

        Args:
            data: Dictionary containing unit data
            system: The GameSystem this unit belongs to
            faction: Name of the faction

        Returns:
            Parsed UnitProfile
        """
        weapons = []
        for w in data.get("weapons", []):
            weapons.append(WeaponProfile.from_dict(w))

        return UnitProfile(
            name=data.get("name", "Unknown"),
            game_system=system.id,
            faction=faction,
            unit_type=UnitType.from_string(data.get("type", "infantry")),
            stats=data.get("stats", {}),
            weapons=weapons,
            wargear=data.get("wargear", []),
            special_rules=data.get("special_rules", []),
            keywords=data.get("keywords", []),
            points_cost=data.get("points", 0),
            models_per_unit=str(data.get("models", "1")),
            tactical_role=data.get("tactical_role", ""),
            threat_level=data.get("threat_level", "medium"),
            preferred_targets=data.get("preferred_targets", []),
            weaknesses=data.get("weaknesses", []),
        )

    def _load_rules(self, path: Path) -> None:
        """
        Load rules references from a TOML file.

        Args:
            path: Path to the rules TOML file
        """
        if tomllib is None:
            return

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            for rule_data in data.get("rules", []):
                rule = RuleReference(
                    name=rule_data.get("name", ""),
                    description=rule_data.get("description", ""),
                    page_reference=str(rule_data.get("page", "")),
                    examples=rule_data.get("examples", []),
                    keywords=rule_data.get("keywords", []),
                )
                if rule.name:
                    self._rules[rule.name.lower()] = rule
        except Exception:
            pass

    def list_factions(self) -> list[str]:
        """
        List available factions for current system.

        Returns:
            Sorted list of faction names
        """
        return sorted(f.name for f in self._factions.values())

    def get_faction(self, name: str) -> Optional[Faction]:
        """
        Get a faction by name without setting it as current.

        Args:
            name: Faction name (case-insensitive, partial match supported)

        Returns:
            Faction if found, None otherwise
        """
        name_lower = name.lower()

        # Exact match
        if name_lower in self._factions:
            return self._factions[name_lower]

        # Partial match
        for key, faction in self._factions.items():
            if name_lower in key:
                return faction

        return None

    def set_faction(self, name: str) -> bool:
        """
        Set the current faction by name.

        Supports partial matching for convenience.

        Args:
            name: Faction name (case-insensitive, partial match)

        Returns:
            True if faction was found and set, False otherwise
        """
        faction = self.get_faction(name)
        if faction:
            self._current_faction = faction
            return True
        return False

    def lookup_unit(self, name: str) -> Optional[UnitProfile]:
        """
        Look up a unit by name.

        First searches the current faction if set, then searches
        all loaded factions.

        Args:
            name: Unit name to search for (case-insensitive)

        Returns:
            UnitProfile if found, None otherwise
        """
        # Search current faction first
        if self._current_faction:
            unit = self._current_faction.get_unit(name)
            if unit:
                return unit

        # Search all factions
        for faction in self._factions.values():
            unit = faction.get_unit(name)
            if unit:
                return unit

        return None

    def lookup_rule(self, name: str) -> Optional[RuleReference]:
        """
        Look up a rule by name.

        Args:
            name: Rule name (case-insensitive)

        Returns:
            RuleReference if found, None otherwise
        """
        return self._rules.get(name.lower())

    def search_rules(self, query: str) -> list[RuleReference]:
        """
        Search rules by query string.

        Searches rule names, descriptions, and keywords.

        Args:
            query: Search string

        Returns:
            List of matching RuleReference objects
        """
        return [r for r in self._rules.values() if r.matches_query(query)]

    def search_units(self, query: str) -> list[UnitProfile]:
        """
        Search for units matching a query across all factions.

        Searches unit names, tactical roles, and keywords.

        Args:
            query: Search string

        Returns:
            List of matching UnitProfile objects
        """
        results = []
        query_lower = query.lower()

        for faction in self._factions.values():
            for unit in faction.units.values():
                if (query_lower in unit.name.lower() or
                    query_lower in unit.tactical_role.lower() or
                    any(query_lower in kw.lower() for kw in unit.keywords)):
                    results.append(unit)

        return results

    def search_units_by_type(self, unit_type: UnitType) -> list[UnitProfile]:
        """
        Search for all units of a specific type.

        Args:
            unit_type: The unit type to filter by

        Returns:
            List of matching UnitProfile objects
        """
        results = []
        for faction in self._factions.values():
            results.extend(faction.units_by_type(unit_type))
        return results

    def get_tactical_info(self, unit_name: str) -> dict[str, Any]:
        """
        Get tactical information for AI decision making.

        Returns a simplified dictionary of tactical hints suitable
        for the wargame AI module.

        Args:
            unit_name: Name of the unit to look up

        Returns:
            Dictionary of tactical information, empty if unit not found
        """
        unit = self.lookup_unit(unit_name)
        if not unit:
            return {}

        return {
            "name": unit.name,
            "faction": unit.faction,
            "type": unit.unit_type.value,
            "threat_level": unit.threat_level,
            "tactical_role": unit.tactical_role,
            "preferred_targets": unit.preferred_targets,
            "weaknesses": unit.weaknesses,
            "special_rules": unit.special_rules,
            "keywords": unit.keywords,
            "points": unit.points_cost,
        }

    def random_unit(self, faction_name: Optional[str] = None) -> Optional[UnitProfile]:
        """
        Get a random unit, optionally from a specific faction.

        Args:
            faction_name: Optional faction to select from

        Returns:
            Random UnitProfile or None if no units available
        """
        if faction_name:
            faction = self.get_faction(faction_name)
            if faction and faction.units:
                return self._rng.choice(list(faction.units.values()))
        elif self._current_faction and self._current_faction.units:
            return self._rng.choice(list(self._current_faction.units.values()))
        else:
            # Random from all factions
            all_units = []
            for faction in self._factions.values():
                all_units.extend(faction.units.values())
            if all_units:
                return self._rng.choice(all_units)

        return None

    def compare_units(self, unit1_name: str, unit2_name: str) -> Optional[str]:
        """
        Generate a comparison between two units.

        Args:
            unit1_name: Name of first unit
            unit2_name: Name of second unit

        Returns:
            Formatted comparison string, or None if units not found
        """
        unit1 = self.lookup_unit(unit1_name)
        unit2 = self.lookup_unit(unit2_name)

        if not unit1 or not unit2:
            return None

        lines = [
            "=" * 60,
            f"COMPARISON: {unit1.name} vs {unit2.name}",
            "=" * 60,
            "",
            f"{'Attribute':<20} {'Unit 1':<18} {'Unit 2':<18}",
            "-" * 60,
            f"{'Faction':<20} {unit1.faction:<18} {unit2.faction:<18}",
            f"{'Type':<20} {unit1.unit_type.value:<18} {unit2.unit_type.value:<18}",
            f"{'Points':<20} {unit1.points_cost:<18} {unit2.points_cost:<18}",
            f"{'Models':<20} {unit1.models_per_unit:<18} {unit2.models_per_unit:<18}",
            f"{'Threat':<20} {unit1.threat_level:<18} {unit2.threat_level:<18}",
            f"{'Role':<20} {unit1.tactical_role:<18} {unit2.tactical_role:<18}",
            "",
        ]

        # Compare stats
        all_stats = set(unit1.stats.keys()) | set(unit2.stats.keys())
        if all_stats:
            lines.append("STATS:")
            for stat in sorted(all_stats):
                val1 = str(unit1.stats.get(stat, "-"))
                val2 = str(unit2.stats.get(stat, "-"))
                lines.append(f"  {stat:<18} {val1:<18} {val2:<18}")
            lines.append("")

        # Compare weapons count
        lines.append(f"{'Weapons':<20} {len(unit1.weapons):<18} {len(unit2.weapons):<18}")
        lines.append(f"{'Special Rules':<20} {len(unit1.special_rules):<18} {len(unit2.special_rules):<18}")

        return "\n".join(lines)

    def export_army_list(self, units: list[tuple[str, int]]) -> str:
        """
        Generate a formatted army list from unit selections.

        Args:
            units: List of (unit_name, quantity) tuples

        Returns:
            Formatted army list string with point totals
        """
        lines = [
            "=" * 50,
            "ARMY LIST",
        ]

        if self._current_system:
            lines.append(f"System: {self._current_system.display_name}")
        if self._current_faction:
            lines.append(f"Faction: {self._current_faction.name}")

        lines.extend(["=" * 50, ""])

        total_points = 0
        total_models = 0

        for unit_name, qty in units:
            unit = self.lookup_unit(unit_name)
            if unit:
                unit_points = unit.points_cost * qty
                total_points += unit_points

                # Parse models per unit (handle ranges like "5-10")
                models_str = unit.models_per_unit
                if "-" in models_str:
                    # Use minimum for counting
                    try:
                        models = int(models_str.split("-")[0]) * qty
                    except ValueError:
                        models = qty
                else:
                    try:
                        models = int(models_str) * qty
                    except ValueError:
                        models = qty
                total_models += models

                lines.append(f"{qty}x {unit.name:<30} {unit_points:>6} pts")
            else:
                lines.append(f"{qty}x {unit_name:<30} (NOT FOUND)")

        lines.extend([
            "",
            "-" * 50,
            f"{'TOTAL:':<33} {total_points:>6} pts",
            f"{'Models:':<33} {total_models:>6}",
            "=" * 50,
        ])

        return "\n".join(lines)


# ==============================================================================
# Module-level manager instance and convenience functions
# ==============================================================================

_manager = GameSystemManager()


def get_manager() -> GameSystemManager:
    """
    Get the module-level GameSystemManager instance.

    Returns:
        The singleton GameSystemManager instance
    """
    return _manager


def set_game_system(name: str) -> bool:
    """
    Set the current game system by name or alias.

    Args:
        name: System name or alias (e.g., 'grimdark future', 'gf', 'oldhammer')

    Returns:
        True if system was found and set, False otherwise

    Example:
        >>> set_game_system("grimdark future")
        True
        >>> set_game_system("gf")  # Same effect
        True
    """
    return _manager.set_system_by_name(name)


def set_faction(name: str) -> bool:
    """
    Set the current faction by name.

    Requires a game system to be set first.

    Args:
        name: Faction name (case-insensitive, partial match supported)

    Returns:
        True if faction was found and set, False otherwise

    Example:
        >>> set_faction("battle brothers")
        True
    """
    return _manager.set_faction(name)


def lookup_unit(name: str) -> Optional[UnitProfile]:
    """
    Look up a unit profile by name.

    Searches current faction first, then all factions.

    Args:
        name: Unit name to search for (case-insensitive)

    Returns:
        UnitProfile if found, None otherwise

    Example:
        >>> unit = lookup_unit("assault brothers")
        >>> print(unit)
    """
    return _manager.lookup_unit(name)


def lookup_rule(name: str) -> Optional[RuleReference]:
    """
    Look up a rules reference by name.

    Args:
        name: Rule name (case-insensitive)

    Returns:
        RuleReference if found, None otherwise
    """
    return _manager.lookup_rule(name)


def list_factions() -> list[str]:
    """
    List available factions for the current game system.

    Returns:
        Sorted list of faction names
    """
    return _manager.list_factions()


def list_systems() -> list[tuple[str, str]]:
    """
    List all supported game systems.

    Returns:
        List of (id, display_name) tuples
    """
    return [(s.id, s.display_name) for s in _manager.list_systems()]


def current_system() -> Optional[str]:
    """
    Get the display name of the current game system.

    Returns:
        Display name of current system, or None if not set
    """
    sys = _manager.current_system
    return sys.display_name if sys else None


def current_faction_name() -> Optional[str]:
    """
    Get the name of the current faction.

    Returns:
        Faction name, or None if not set
    """
    faction = _manager.current_faction
    return faction.name if faction else None


def search_units(query: str) -> list[UnitProfile]:
    """
    Search for units matching a query.

    Searches unit names, tactical roles, and keywords.

    Args:
        query: Search string

    Returns:
        List of matching UnitProfile objects
    """
    return _manager.search_units(query)


def search_rules(query: str) -> list[RuleReference]:
    """
    Search rules by query string.

    Args:
        query: Search string

    Returns:
        List of matching RuleReference objects
    """
    return _manager.search_rules(query)


def get_tactical_info(unit_name: str) -> dict[str, Any]:
    """
    Get tactical information for AI decision making.

    Args:
        unit_name: Name of the unit to look up

    Returns:
        Dictionary of tactical information, empty if unit not found
    """
    return _manager.get_tactical_info(unit_name)


def random_unit(faction: Optional[str] = None) -> Optional[UnitProfile]:
    """
    Get a random unit, optionally from a specific faction.

    Args:
        faction: Optional faction name to select from

    Returns:
        Random UnitProfile or None if no units available
    """
    return _manager.random_unit(faction)


def compare_units(unit1: str, unit2: str) -> Optional[str]:
    """
    Generate a comparison between two units.

    Args:
        unit1: Name of first unit
        unit2: Name of second unit

    Returns:
        Formatted comparison string, or None if units not found
    """
    return _manager.compare_units(unit1, unit2)
