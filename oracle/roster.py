"""
Roster and party tracking for wargames and RPGs.

This module provides a unified system for managing army rosters in wargames
and party/NPC tracking in RPGs. It supports:

- Wargame army rosters with units organized by battlefield role
- RPG party tracking with PCs, NPCs, allies, and enemies
- Custom unit/NPC creation with flexible stat blocks
- Importing units from game system data (see gamesystems.py)
- Saving/loading rosters to JSON files
- Tracking wounds, status effects, and unit state during play

Example Usage (Wargame):
    >>> from oracle.roster import new_roster, add_custom_unit, SlotType
    >>> roster = new_roster("My Army", game_system="grimdark_future", faction="Battle Brothers")
    >>> add_custom_unit(name="Assault Squad", slot_type=SlotType.TROOPS, models=5, points=100)
    >>> print(roster)

Example Usage (RPG):
    >>> from oracle.roster import new_roster, add_custom_unit, SlotType
    >>> roster = new_roster("The Party", mode="rpg")
    >>> add_custom_unit(
    ...     name="Grognard the Barbarian",
    ...     slot_type=SlotType.PARTY_MEMBER,
    ...     stats={"level": 5, "hp": 45, "str": 18},
    ...     disposition="friendly"
    ... )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
import random

if TYPE_CHECKING:
    from .gamesystems import UnitProfile

logger = logging.getLogger(__name__)


class RosterError(Exception):
    """Base exception for roster-related errors."""
    pass


class NoActiveRosterError(RosterError):
    """Raised when an operation requires an active roster but none exists."""
    pass


class UnitNotFoundError(RosterError):
    """Raised when a unit cannot be found in the roster."""
    pass


class InvalidSlotTypeError(RosterError):
    """Raised when an invalid slot type is specified."""
    pass


class SlotType(Enum):
    """
    Types of roster slots for organizing units.

    Wargame slots follow common army organization patterns.
    RPG slots categorize characters by their relationship to the party.

    Attributes:
        value: String identifier for the slot type
    """
    # Wargame slots (40K-style)
    HQ = "hq"
    TROOPS = "troops"
    ELITES = "elites"
    FAST_ATTACK = "fast_attack"
    HEAVY_SUPPORT = "heavy_support"
    FLYER = "flyer"
    DEDICATED_TRANSPORT = "dedicated_transport"
    LORD_OF_WAR = "lord_of_war"

    # Fantasy slots (WHFB-style)
    LORDS = "lords"
    HEROES = "heroes"
    CORE = "core"
    SPECIAL = "special"
    RARE = "rare"

    # RPG slots
    PARTY_MEMBER = "party_member"
    ALLY = "ally"
    HIRELING = "hireling"
    ENEMY = "enemy"
    NEUTRAL = "neutral"

    # Generic
    CUSTOM = "custom"

    @classmethod
    def from_string(cls, value: str) -> "SlotType":
        """
        Convert a string to SlotType.

        Args:
            value: String representation of slot type (case-insensitive)

        Returns:
            Matching SlotType

        Raises:
            InvalidSlotTypeError: If the string doesn't match any slot type
        """
        value_lower = value.lower().strip()
        for slot in cls:
            if slot.value == value_lower:
                return slot
        # Try matching without underscores
        value_normalized = value_lower.replace(" ", "_").replace("-", "_")
        for slot in cls:
            if slot.value == value_normalized:
                return slot
        raise InvalidSlotTypeError(f"Unknown slot type: '{value}'. Valid types: {[s.value for s in cls]}")

    @classmethod
    def wargame_slots(cls) -> list["SlotType"]:
        """Return all wargame-related slot types."""
        return [
            cls.HQ, cls.TROOPS, cls.ELITES, cls.FAST_ATTACK, cls.HEAVY_SUPPORT,
            cls.FLYER, cls.DEDICATED_TRANSPORT, cls.LORD_OF_WAR,
            cls.LORDS, cls.HEROES, cls.CORE, cls.SPECIAL, cls.RARE
        ]

    @classmethod
    def rpg_slots(cls) -> list["SlotType"]:
        """Return all RPG-related slot types."""
        return [cls.PARTY_MEMBER, cls.ALLY, cls.HIRELING, cls.ENEMY, cls.NEUTRAL]


class UnitStatus(Enum):
    """
    Status of a unit or character during play.

    Status affects whether a unit can act and how it's displayed.
    Some statuses indicate the unit is no longer active (DESTROYED, DEAD, FLED).

    Attributes:
        value: String identifier for the status
    """
    FRESH = "fresh"           # Full health, ready for action
    ENGAGED = "engaged"       # In combat
    DAMAGED = "damaged"       # Has taken wounds but still fighting
    WOUNDED = "wounded"       # Significantly hurt
    ROUTING = "routing"       # Fleeing/broken
    DESTROYED = "destroyed"   # Wargame: unit eliminated
    DEAD = "dead"             # RPG: character killed
    FLED = "fled"             # Escaped the battlefield

    @classmethod
    def from_string(cls, value: str) -> "UnitStatus":
        """
        Convert a string to UnitStatus.

        Args:
            value: String representation of status (case-insensitive)

        Returns:
            Matching UnitStatus, defaults to FRESH if not found
        """
        try:
            return cls(value.lower().strip())
        except ValueError:
            logger.warning(f"Unknown status '{value}', defaulting to FRESH")
            return cls.FRESH

    @property
    def is_active(self) -> bool:
        """Return True if this status indicates the unit can still act."""
        return self not in [UnitStatus.DESTROYED, UnitStatus.DEAD, UnitStatus.FLED]

    @property
    def icon(self) -> str:
        """Return a unicode icon representing this status."""
        icons = {
            UnitStatus.FRESH: "●",
            UnitStatus.ENGAGED: "◐",
            UnitStatus.DAMAGED: "◑",
            UnitStatus.WOUNDED: "◕",
            UnitStatus.ROUTING: "○",
            UnitStatus.DESTROYED: "✗",
            UnitStatus.DEAD: "✗",
            UnitStatus.FLED: "→",
        }
        return icons.get(self, "?")


@dataclass
class RosterUnit:
    """
    A unit or character in a roster.

    RosterUnit is a flexible container that works for both wargame units
    (squads with multiple models) and RPG characters (single individuals).

    The stats dictionary can hold any game system's statistics, making
    this class adaptable to different rules systems.

    Attributes:
        id: Unique identifier for this unit instance
        name: Display name
        slot_type: Organizational category (HQ, TROOPS, PARTY_MEMBER, etc.)
        status: Current condition (FRESH, DAMAGED, DEAD, etc.)
        stats: Flexible dictionary of game statistics
        weapons: List of weapon dictionaries with name, range, strength, etc.
        wargear: List of equipment/item names
        abilities: List of special ability/rule names
        wounds_current: Current wound/HP count
        wounds_max: Maximum wound/HP count
        models_current: Current number of models in unit
        models_max: Starting number of models
        points_cost: Points value for army building
        notes: Freeform notes
        is_custom: True if user-created rather than imported
        source: Where this unit data came from
        disposition: RPG: attitude toward party (friendly, hostile, neutral)
        relationship: RPG: connection to party members
        secrets: RPG: hidden information about this character
        threat_level: AI hint for combat priority
        tactical_role: AI hint for unit purpose
    """
    id: str
    name: str
    slot_type: SlotType
    status: UnitStatus = UnitStatus.FRESH

    # Core stats (flexible dict for any game system)
    stats: dict[str, Any] = field(default_factory=dict)

    # Equipment and abilities
    weapons: list[dict[str, Any]] = field(default_factory=list)
    wargear: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)

    # Tracking
    wounds_current: int = 0
    wounds_max: int = 1
    models_current: int = 1
    models_max: int = 1
    points_cost: int = 0

    # Notes and customization
    notes: str = ""
    is_custom: bool = False
    source: str = ""

    # RPG-specific
    disposition: str = ""
    relationship: str = ""
    secrets: list[str] = field(default_factory=list)

    # Tactical AI hints
    threat_level: str = "medium"
    tactical_role: str = ""

    def __post_init__(self):
        """Initialize wounds_current to wounds_max if not set."""
        if self.wounds_current == 0 and self.wounds_max > 0:
            self.wounds_current = self.wounds_max

    def __str__(self) -> str:
        """
        Format unit as a single-line status display.

        Returns:
            String like "● Space Marines [5/5] W:2/2 (100pts)"
        """
        parts = [f"{self.status.icon} {self.name}"]

        if self.models_max > 1:
            parts.append(f"[{self.models_current}/{self.models_max}]")

        if self.wounds_max > 1:
            parts.append(f"W:{self.wounds_current}/{self.wounds_max}")

        if self.points_cost:
            parts.append(f"({self.points_cost}pts)")

        return " ".join(parts)

    def __repr__(self) -> str:
        """Return detailed representation for debugging."""
        return (f"RosterUnit(id={self.id!r}, name={self.name!r}, "
                f"slot={self.slot_type.value}, status={self.status.value})")

    @property
    def is_active(self) -> bool:
        """Return True if this unit can still act."""
        return self.status.is_active

    @property
    def health_percentage(self) -> float:
        """
        Return current health as a percentage (0.0 to 1.0).

        For multi-model units, considers both wounds and model count.
        """
        if self.wounds_max <= 0:
            return 1.0

        if self.models_max > 1:
            # Multi-model unit: factor in remaining models
            total_wounds = self.wounds_max * self.models_max
            current_wounds = (self.wounds_max * (self.models_current - 1)) + self.wounds_current
            return current_wounds / total_wounds
        else:
            return self.wounds_current / self.wounds_max

    def take_damage(self, wounds: int = 1) -> str:
        """
        Apply damage to the unit.

        For multi-model units, damage spills over to destroy models.
        Updates status based on remaining health.

        Args:
            wounds: Amount of damage to apply

        Returns:
            Description of what happened

        Raises:
            ValueError: If wounds is negative
        """
        if wounds < 0:
            raise ValueError("Damage cannot be negative. Use heal() instead.")

        if wounds == 0:
            return f"{self.name}: No damage taken."

        if not self.is_active:
            return f"{self.name}: Already {self.status.value}."

        messages = []
        remaining_damage = wounds

        while remaining_damage > 0 and self.is_active:
            # Apply damage to current model
            damage_to_apply = min(remaining_damage, self.wounds_current)
            self.wounds_current -= damage_to_apply
            remaining_damage -= damage_to_apply

            if self.wounds_current <= 0:
                if self.models_current > 1:
                    # Multi-model unit: lose a model
                    self.models_current -= 1
                    self.wounds_current = self.wounds_max
                    messages.append(f"Model destroyed! {self.models_current} remaining.")
                else:
                    # Last/only model destroyed
                    self.status = UnitStatus.DESTROYED
                    self.wounds_current = 0
                    messages.append("DESTROYED!")

        # Update status based on health
        if self.is_active:
            health_pct = self.health_percentage
            if health_pct < 0.25:
                self.status = UnitStatus.WOUNDED
            elif health_pct < 0.75:
                self.status = UnitStatus.DAMAGED

        result = f"{self.name}: Takes {wounds} wound(s). "
        if messages:
            result += " ".join(messages)
        else:
            result += f"{self.wounds_current}/{self.wounds_max} remaining."

        return result

    def heal(self, wounds: int = 1) -> str:
        """
        Heal the unit by restoring wounds.

        Cannot restore destroyed models or resurrect dead units.

        Args:
            wounds: Amount of healing to apply

        Returns:
            Description of healing result

        Raises:
            ValueError: If wounds is negative
        """
        if wounds < 0:
            raise ValueError("Healing cannot be negative. Use take_damage() instead.")

        if wounds == 0:
            return f"{self.name}: No healing applied."

        if not self.is_active:
            return f"{self.name}: Cannot heal - unit is {self.status.value}."

        old_wounds = self.wounds_current
        self.wounds_current = min(self.wounds_max, self.wounds_current + wounds)
        healed = self.wounds_current - old_wounds

        if healed > 0:
            # Update status if at full health
            if self.wounds_current == self.wounds_max and self.models_current == self.models_max:
                self.status = UnitStatus.FRESH
            elif self.health_percentage >= 0.75:
                self.status = UnitStatus.FRESH
            return f"{self.name}: Healed {healed} wound(s). {self.wounds_current}/{self.wounds_max}."

        return f"{self.name}: Already at full wounds ({self.wounds_current}/{self.wounds_max})."

    def restore_model(self) -> str:
        """
        Restore one destroyed model to the unit.

        Returns:
            Description of result
        """
        if self.models_current >= self.models_max:
            return f"{self.name}: Already at full strength ({self.models_current}/{self.models_max})."

        self.models_current += 1

        if self.status == UnitStatus.DESTROYED:
            self.status = UnitStatus.DAMAGED
            self.wounds_current = self.wounds_max

        return f"{self.name}: Model restored! Now {self.models_current}/{self.models_max}."

    def set_status(self, status: UnitStatus | str) -> str:
        """
        Manually set unit status.

        Args:
            status: New status (UnitStatus enum or string)

        Returns:
            Confirmation message
        """
        if isinstance(status, str):
            status = UnitStatus.from_string(status)

        old_status = self.status
        self.status = status
        return f"{self.name}: Status changed from {old_status.value} to {status.value}."

    def get_stat(self, stat_name: str, default: Any = None) -> Any:
        """
        Get a statistic value by name.

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

    def set_stat(self, stat_name: str, value: Any) -> None:
        """
        Set a statistic value.

        Args:
            stat_name: Name of the stat
            value: New value
        """
        self.stats[stat_name] = value

    def add_weapon(self, name: str, **kwargs) -> None:
        """
        Add a weapon to the unit.

        Args:
            name: Weapon name
            **kwargs: Additional weapon properties (range, strength, ap, damage, etc.)
        """
        weapon = {"name": name, **kwargs}
        self.weapons.append(weapon)

    def remove_weapon(self, name: str) -> bool:
        """
        Remove a weapon by name.

        Args:
            name: Weapon name to remove

        Returns:
            True if weapon was found and removed
        """
        for i, w in enumerate(self.weapons):
            if w.get("name", "").lower() == name.lower():
                self.weapons.pop(i)
                return True
        return False

    def add_ability(self, ability: str) -> None:
        """Add an ability/special rule to the unit."""
        if ability not in self.abilities:
            self.abilities.append(ability)

    def has_ability(self, ability: str) -> bool:
        """Check if unit has an ability (case-insensitive partial match)."""
        ability_lower = ability.lower()
        return any(ability_lower in a.lower() for a in self.abilities)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation with enum values as strings
        """
        data = asdict(self)
        data["slot_type"] = self.slot_type.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RosterUnit":
        """
        Create a RosterUnit from a dictionary.

        Args:
            data: Dictionary with unit data (e.g., from JSON)

        Returns:
            RosterUnit instance

        Raises:
            KeyError: If required fields are missing
            InvalidSlotTypeError: If slot_type is invalid
        """
        # Make a copy to avoid modifying the input
        data = dict(data)

        # Convert string enums back to enum types
        if "slot_type" in data:
            if isinstance(data["slot_type"], str):
                data["slot_type"] = SlotType.from_string(data["slot_type"])

        if "status" in data:
            if isinstance(data["status"], str):
                data["status"] = UnitStatus.from_string(data["status"])

        return cls(**data)


@dataclass
class Roster:
    """
    A complete roster/party containing multiple units.

    Roster organizes units by slot type and tracks total points.
    It can be saved/loaded to JSON files for persistence.

    Attributes:
        name: Display name for this roster
        game_system: Game system ID (e.g., "grimdark_future")
        faction: Faction/army name
        mode: "wargame" or "rpg"
        units: List of RosterUnit instances
        points_limit: Maximum points allowed (0 = unlimited)
        created: ISO timestamp of creation
        modified: ISO timestamp of last modification
        notes: Freeform notes about the roster
    """
    name: str
    game_system: str = ""
    faction: str = ""
    mode: str = "wargame"

    units: list[RosterUnit] = field(default_factory=list)
    points_limit: int = 0

    # Metadata
    created: str = ""
    modified: str = ""
    notes: str = ""

    def __post_init__(self):
        """Initialize timestamps if not set."""
        now = datetime.now().isoformat()
        if not self.created:
            self.created = now
        if not self.modified:
            self.modified = now

    def _touch(self) -> None:
        """Update the modified timestamp."""
        self.modified = datetime.now().isoformat()

    @property
    def points_total(self) -> int:
        """
        Calculate total points of active units.

        Returns:
            Sum of points_cost for all non-destroyed/dead units
        """
        return sum(u.points_cost for u in self.units if u.is_active)

    @property
    def points_all(self) -> int:
        """
        Calculate total points including destroyed units.

        Returns:
            Sum of points_cost for all units
        """
        return sum(u.points_cost for u in self.units)

    @property
    def points_remaining(self) -> int:
        """
        Calculate remaining points budget.

        Returns:
            Points limit minus total points (0 if no limit set)
        """
        if self.points_limit <= 0:
            return 0
        return max(0, self.points_limit - self.points_all)

    @property
    def active_units(self) -> list[RosterUnit]:
        """Return list of units that can still act."""
        return [u for u in self.units if u.is_active]

    @property
    def destroyed_units(self) -> list[RosterUnit]:
        """Return list of destroyed/dead/fled units."""
        return [u for u in self.units if not u.is_active]

    def __len__(self) -> int:
        """Return total number of units."""
        return len(self.units)

    def __iter__(self):
        """Iterate over all units."""
        return iter(self.units)

    def __contains__(self, item: str | RosterUnit) -> bool:
        """Check if a unit (by name or ID) is in the roster."""
        if isinstance(item, RosterUnit):
            return item in self.units
        # String: check by name or ID
        return self.get_unit(item) is not None

    def __str__(self) -> str:
        """
        Format roster as a multi-line display.

        Returns:
            Formatted roster with units grouped by slot type
        """
        lines = [
            f"{'═' * 3} {self.name} {'═' * 3}",
        ]

        if self.game_system or self.faction:
            info_parts = []
            if self.game_system:
                info_parts.append(f"System: {self.game_system}")
            if self.faction:
                info_parts.append(f"Faction: {self.faction}")
            lines.append(" | ".join(info_parts))

        if self.points_limit:
            lines.append(f"Points: {self.points_total}/{self.points_limit} ({self.points_remaining} remaining)")
        elif self.points_total:
            lines.append(f"Points: {self.points_total}")

        lines.append("")

        # Group by slot type
        slots_used = sorted(set(u.slot_type for u in self.units), key=lambda s: s.value)
        for slot in slots_used:
            slot_units = self.by_slot(slot)
            if slot_units:
                lines.append(f"[{slot.value.upper().replace('_', ' ')}]")
                for u in slot_units:
                    lines.append(f"  {u}")
                lines.append("")

        if not self.units:
            lines.append("(empty roster)")

        return "\n".join(lines)

    def add_unit(self, unit: RosterUnit) -> None:
        """
        Add a unit to the roster.

        Args:
            unit: RosterUnit to add
        """
        self.units.append(unit)
        self._touch()
        logger.debug(f"Added unit '{unit.name}' to roster '{self.name}'")

    def remove_unit(self, unit_id: str) -> RosterUnit:
        """
        Remove a unit by ID.

        Args:
            unit_id: ID of the unit to remove

        Returns:
            The removed unit

        Raises:
            UnitNotFoundError: If no unit with that ID exists
        """
        for i, u in enumerate(self.units):
            if u.id == unit_id:
                removed = self.units.pop(i)
                self._touch()
                logger.debug(f"Removed unit '{removed.name}' from roster '{self.name}'")
                return removed

        raise UnitNotFoundError(f"No unit with ID '{unit_id}' in roster")

    def get_unit(self, name_or_id: str) -> Optional[RosterUnit]:
        """
        Find a unit by name or ID.

        Tries exact match first, then case-insensitive, then partial match.

        Args:
            name_or_id: Name or ID to search for

        Returns:
            Matching unit or None
        """
        if not name_or_id:
            return None

        # Exact ID match
        for u in self.units:
            if u.id == name_or_id:
                return u

        # Exact name match (case-insensitive)
        name_lower = name_or_id.lower()
        for u in self.units:
            if u.name.lower() == name_lower:
                return u

        # Partial name match
        for u in self.units:
            if name_lower in u.name.lower():
                return u

        return None

    def get_unit_strict(self, name_or_id: str) -> RosterUnit:
        """
        Find a unit by name or ID, raising if not found.

        Args:
            name_or_id: Name or ID to search for

        Returns:
            Matching unit

        Raises:
            UnitNotFoundError: If no matching unit found
        """
        unit = self.get_unit(name_or_id)
        if unit is None:
            raise UnitNotFoundError(f"No unit matching '{name_or_id}' in roster")
        return unit

    def by_slot(self, slot: SlotType | str) -> list[RosterUnit]:
        """
        Get all units of a specific slot type.

        Args:
            slot: SlotType enum or string

        Returns:
            List of matching units
        """
        if isinstance(slot, str):
            slot = SlotType.from_string(slot)
        return [u for u in self.units if u.slot_type == slot]

    def by_status(self, status: UnitStatus | str) -> list[RosterUnit]:
        """
        Get all units with a specific status.

        Args:
            status: UnitStatus enum or string

        Returns:
            List of matching units
        """
        if isinstance(status, str):
            status = UnitStatus.from_string(status)
        return [u for u in self.units if u.status == status]

    def search(self, query: str) -> list[RosterUnit]:
        """
        Search units by name, abilities, or notes.

        Args:
            query: Search string (case-insensitive)

        Returns:
            List of matching units
        """
        query_lower = query.lower()
        results = []

        for u in self.units:
            if query_lower in u.name.lower():
                results.append(u)
            elif any(query_lower in a.lower() for a in u.abilities):
                results.append(u)
            elif query_lower in u.notes.lower():
                results.append(u)

        return results

    def reset_all(self) -> str:
        """
        Reset all units to fresh status with full wounds/models.

        Returns:
            Summary of reset
        """
        count = 0
        for u in self.units:
            u.status = UnitStatus.FRESH
            u.wounds_current = u.wounds_max
            u.models_current = u.models_max
            count += 1

        self._touch()
        return f"Reset {count} unit(s) to fresh status."

    def summary(self) -> dict[str, Any]:
        """
        Generate a summary of the roster state.

        Returns:
            Dictionary with counts and statistics
        """
        return {
            "name": self.name,
            "total_units": len(self.units),
            "active_units": len(self.active_units),
            "destroyed_units": len(self.destroyed_units),
            "points_total": self.points_total,
            "points_limit": self.points_limit,
            "points_remaining": self.points_remaining,
            "slots_used": list(set(u.slot_type.value for u in self.units)),
            "statuses": {s.value: len(self.by_status(s)) for s in UnitStatus if self.by_status(s)},
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "game_system": self.game_system,
            "faction": self.faction,
            "mode": self.mode,
            "units": [u.to_dict() for u in self.units],
            "points_limit": self.points_limit,
            "created": self.created,
            "modified": self.modified,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Roster":
        """
        Create a Roster from a dictionary.

        Args:
            data: Dictionary with roster data (e.g., from JSON)

        Returns:
            Roster instance
        """
        # Make a copy to avoid modifying input
        data = dict(data)

        # Extract and convert units separately
        units_data = data.pop("units", [])
        units = [RosterUnit.from_dict(u) for u in units_data]

        # Create roster and add units
        roster = cls(**data)
        roster.units = units

        return roster


class RosterManager:
    """
    Manages rosters and provides unit creation/editing utilities.

    RosterManager maintains a "current" roster that module-level functions
    operate on, and handles saving/loading rosters to disk.

    Attributes:
        save_dir: Directory where roster files are stored
    """

    def __init__(self, save_dir: Optional[Path] = None):
        """
        Initialize the roster manager.

        Args:
            save_dir: Directory for saving rosters. Defaults to ~/.oracle/rosters/
        """
        self.save_dir = save_dir or Path.home() / ".oracle" / "rosters"
        self._ensure_save_dir()
        self._current: Optional[Roster] = None
        self._id_counter = 0

    def _ensure_save_dir(self) -> None:
        """Create save directory if it doesn't exist."""
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create save directory: {e}")
            raise RosterError(f"Cannot create roster save directory: {self.save_dir}") from e

    @property
    def current(self) -> Optional[Roster]:
        """Get the currently active roster."""
        return self._current

    @current.setter
    def current(self, roster: Optional[Roster]) -> None:
        """Set the currently active roster."""
        self._current = roster

    def _generate_id(self, prefix: str = "unit") -> str:
        """
        Generate a unique ID for a unit.

        Args:
            prefix: Prefix for the ID

        Returns:
            Unique ID string
        """
        self._id_counter += 1
        random_suffix = random.randint(1000, 9999)
        return f"{prefix}_{self._id_counter}_{random_suffix}"

    def new_roster(
        self,
        name: str,
        game_system: str = "",
        faction: str = "",
        mode: str = "wargame",
        points_limit: int = 0,
        notes: str = "",
    ) -> Roster:
        """
        Create a new roster and set it as current.

        Args:
            name: Display name for the roster
            game_system: Game system ID (e.g., "grimdark_future")
            faction: Faction/army name
            mode: "wargame" or "rpg"
            points_limit: Maximum points allowed (0 = unlimited)
            notes: Freeform notes

        Returns:
            The new Roster instance
        """
        self._current = Roster(
            name=name,
            game_system=game_system,
            faction=faction,
            mode=mode,
            points_limit=points_limit,
            notes=notes,
        )
        logger.info(f"Created new roster: '{name}'")
        return self._current

    def create_custom_unit(
        self,
        name: str,
        slot_type: SlotType | str = SlotType.CUSTOM,
        stats: Optional[dict[str, Any]] = None,
        weapons: Optional[list[dict[str, Any]]] = None,
        wargear: Optional[list[str]] = None,
        abilities: Optional[list[str]] = None,
        wounds: int = 1,
        models: int = 1,
        points: int = 0,
        notes: str = "",
        disposition: str = "",
        relationship: str = "",
        secrets: Optional[list[str]] = None,
        threat_level: str = "medium",
        tactical_role: str = "",
    ) -> RosterUnit:
        """
        Create a custom unit/NPC with user-provided data.

        This does NOT automatically add the unit to the current roster.
        Use add_unit() or the add_custom_unit() module function for that.

        Args:
            name: Unit/character name
            slot_type: Organizational slot (SlotType or string)
            stats: Dictionary of game statistics
            weapons: List of weapon dictionaries
            wargear: List of equipment names
            abilities: List of ability/rule names
            wounds: Wound/HP count per model
            models: Number of models in unit
            points: Points cost
            notes: Freeform notes
            disposition: RPG: attitude (friendly, hostile, neutral)
            relationship: RPG: connection to party
            secrets: RPG: hidden information
            threat_level: AI hint (low, medium, high, extreme)
            tactical_role: AI hint (assault, fire_support, etc.)

        Returns:
            New RosterUnit instance
        """
        if isinstance(slot_type, str):
            slot_type = SlotType.from_string(slot_type)

        unit = RosterUnit(
            id=self._generate_id(),
            name=name,
            slot_type=slot_type,
            stats=stats or {},
            weapons=weapons or [],
            wargear=wargear or [],
            abilities=abilities or [],
            wounds_current=wounds,
            wounds_max=wounds,
            models_current=models,
            models_max=models,
            points_cost=points,
            notes=notes,
            is_custom=True,
            source="custom",
            disposition=disposition,
            relationship=relationship,
            secrets=secrets or [],
            threat_level=threat_level,
            tactical_role=tactical_role,
        )

        logger.debug(f"Created custom unit: '{name}'")
        return unit

    def create_blank_unit_template(self, mode: str = "wargame") -> dict[str, Any]:
        """
        Return a blank template dictionary for users to fill out.

        This is useful for guided unit creation where users fill in a form.

        Args:
            mode: "wargame" or "rpg" - determines which stats to include

        Returns:
            Dictionary template with empty/default values
        """
        if mode == "wargame":
            return {
                "name": "",
                "slot_type": "troops",
                "stats": {
                    "M": 0,     # Movement
                    "WS": 0,    # Weapon Skill
                    "BS": 0,    # Ballistic Skill
                    "S": 0,     # Strength
                    "T": 0,     # Toughness
                    "W": 0,     # Wounds
                    "A": 0,     # Attacks
                    "Ld": 0,    # Leadership
                    "Sv": "",   # Save
                },
                "weapons": [
                    {
                        "name": "",
                        "range": "",
                        "strength": "",
                        "ap": "",
                        "damage": "",
                        "abilities": [],
                    }
                ],
                "wargear": [],
                "abilities": [],
                "models": 1,
                "wounds": 1,
                "points": 0,
                "notes": "",
                "threat_level": "medium",
                "tactical_role": "",
            }
        else:  # RPG mode
            return {
                "name": "",
                "slot_type": "ally",
                "stats": {
                    "level": 1,
                    "hp": 10,
                    "ac": 10,
                    "str": 10,
                    "dex": 10,
                    "con": 10,
                    "int": 10,
                    "wis": 10,
                    "cha": 10,
                },
                "weapons": [],
                "wargear": [],
                "abilities": [],
                "wounds": 10,
                "disposition": "neutral",
                "relationship": "",
                "secrets": [],
                "notes": "",
            }

    def add_unit_from_template(self, template: dict[str, Any]) -> RosterUnit:
        """
        Create a unit from a filled-out template dictionary.

        Args:
            template: Dictionary with unit data (from create_blank_unit_template)

        Returns:
            New RosterUnit instance

        Raises:
            NoActiveRosterError: If no roster is currently active
        """
        wounds = template.get("wounds", template.get("stats", {}).get("W", 1))
        if isinstance(wounds, str):
            wounds = int(wounds) if wounds.isdigit() else 1

        unit = self.create_custom_unit(
            name=template.get("name", "Unnamed Unit"),
            slot_type=template.get("slot_type", "custom"),
            stats=template.get("stats", {}),
            weapons=template.get("weapons", []),
            wargear=template.get("wargear", []),
            abilities=template.get("abilities", []),
            wounds=wounds,
            models=template.get("models", 1),
            points=template.get("points", 0),
            notes=template.get("notes", ""),
            disposition=template.get("disposition", ""),
            relationship=template.get("relationship", ""),
            secrets=template.get("secrets", []),
            threat_level=template.get("threat_level", "medium"),
            tactical_role=template.get("tactical_role", ""),
        )

        if self._current:
            self._current.add_unit(unit)
        else:
            raise NoActiveRosterError("No active roster. Create one with new_roster() first.")

        return unit

    def add_unit_from_gamesystem(self, unit_profile: "UnitProfile") -> RosterUnit:
        """
        Add a unit from the gamesystems module.

        Converts a UnitProfile (from gamesystems.py) to a RosterUnit
        and adds it to the current roster.

        Args:
            unit_profile: UnitProfile instance from gamesystems module

        Returns:
            New RosterUnit instance added to roster

        Raises:
            NoActiveRosterError: If no roster is currently active
        """
        if not self._current:
            raise NoActiveRosterError("No active roster. Create one with new_roster() first.")

        # Map unit type to slot type
        slot_type = self._map_unit_type_to_slot(unit_profile.unit_type)

        # Parse wounds from stats
        wounds = unit_profile.stats.get("W", unit_profile.stats.get("wounds", 1))
        if isinstance(wounds, str):
            wounds = int(wounds) if wounds.isdigit() else 1

        # Parse model count (handle ranges like "5-10")
        models_str = str(unit_profile.models_per_unit)
        if "-" in models_str:
            parts = models_str.split("-")
            models_min = int(parts[0])
            models_max = int(parts[-1])
        else:
            models_min = models_max = int(models_str) if models_str.isdigit() else 1

        # Convert weapon profiles to dictionaries
        weapons = []
        for w in unit_profile.weapons:
            weapon_dict = {
                "name": w.name,
                "range": w.range,
                "strength": w.strength,
                "ap": w.ap,
                "damage": w.damage,
                "abilities": w.abilities,
                "type": getattr(w, "type", ""),
                "shots": getattr(w, "shots", "1"),
            }
            weapons.append(weapon_dict)

        unit = RosterUnit(
            id=self._generate_id(),
            name=unit_profile.name,
            slot_type=slot_type,
            stats=dict(unit_profile.stats),
            weapons=weapons,
            wargear=list(unit_profile.wargear),
            abilities=list(unit_profile.special_rules),
            wounds_current=wounds,
            wounds_max=wounds,
            models_current=models_min,
            models_max=models_max,
            points_cost=unit_profile.points_cost,
            source=unit_profile.game_system,
            threat_level=unit_profile.threat_level,
            tactical_role=unit_profile.tactical_role,
        )

        self._current.add_unit(unit)
        logger.info(f"Added unit '{unit.name}' from game system")
        return unit

    def _map_unit_type_to_slot(self, unit_type) -> SlotType:
        """
        Map a UnitType to a SlotType.

        Args:
            unit_type: UnitType enum or string

        Returns:
            Corresponding SlotType
        """
        # Get string value if it's an enum
        if hasattr(unit_type, "value"):
            unit_type = unit_type.value

        mapping = {
            "infantry": SlotType.TROOPS,
            "cavalry": SlotType.FAST_ATTACK,
            "vehicle": SlotType.HEAVY_SUPPORT,
            "character": SlotType.HQ,
            "monster": SlotType.ELITES,
            "warmachine": SlotType.HEAVY_SUPPORT,
            "swarm": SlotType.TROOPS,
            "flyer": SlotType.FLYER,
        }
        return mapping.get(str(unit_type).lower(), SlotType.CUSTOM)

    def save(self, filename: Optional[str] = None) -> Path:
        """
        Save the current roster to a JSON file.

        Args:
            filename: Filename (without path). If None, uses roster name.

        Returns:
            Path to the saved file

        Raises:
            NoActiveRosterError: If no roster is currently active
            RosterError: If save fails
        """
        if not self._current:
            raise NoActiveRosterError("No active roster to save")

        if not filename:
            # Sanitize roster name for filename
            safe_name = self._current.name.replace(" ", "_")
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
            filename = f"{safe_name}.json"

        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        filepath = self.save_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._current.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved roster to {filepath}")
            return filepath
        except (OSError, TypeError) as e:
            raise RosterError(f"Failed to save roster: {e}") from e

    def load(self, filename: str) -> Roster:
        """
        Load a roster from a JSON file.

        Args:
            filename: Filename (with or without .json extension)

        Returns:
            Loaded Roster instance (also set as current)

        Raises:
            RosterError: If load fails
        """
        filepath = self.save_dir / filename

        if not filepath.exists():
            # Try adding .json extension
            filepath = self.save_dir / f"{filename}.json"

        if not filepath.exists():
            raise RosterError(f"Roster file not found: {filename}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._current = Roster.from_dict(data)
            logger.info(f"Loaded roster '{self._current.name}' from {filepath}")
            return self._current
        except (OSError, json.JSONDecodeError, KeyError) as e:
            raise RosterError(f"Failed to load roster: {e}") from e

    def list_saved(self) -> list[str]:
        """
        List all saved roster files.

        Returns:
            List of roster names (without .json extension)
        """
        try:
            return sorted(f.stem for f in self.save_dir.glob("*.json"))
        except OSError as e:
            logger.error(f"Failed to list rosters: {e}")
            return []

    def delete_saved(self, filename: str) -> bool:
        """
        Delete a saved roster file.

        Args:
            filename: Filename (with or without .json extension)

        Returns:
            True if deleted, False if not found
        """
        filepath = self.save_dir / filename
        if not filepath.exists():
            filepath = self.save_dir / f"{filename}.json"

        if filepath.exists():
            try:
                filepath.unlink()
                logger.info(f"Deleted roster file: {filepath}")
                return True
            except OSError as e:
                logger.error(f"Failed to delete roster: {e}")
                return False
        return False

    def export_to_text(self, roster: Optional[Roster] = None) -> str:
        """
        Export a roster to human-readable text format.

        Args:
            roster: Roster to export (defaults to current)

        Returns:
            Formatted text representation
        """
        roster = roster or self._current
        if not roster:
            raise NoActiveRosterError("No roster to export")

        return str(roster)

    def duplicate_roster(self, new_name: str) -> Roster:
        """
        Create a copy of the current roster with a new name.

        Args:
            new_name: Name for the duplicated roster

        Returns:
            New Roster instance (also set as current)

        Raises:
            NoActiveRosterError: If no roster is currently active
        """
        if not self._current:
            raise NoActiveRosterError("No roster to duplicate")

        # Deep copy via serialization
        data = self._current.to_dict()
        data["name"] = new_name
        data["created"] = datetime.now().isoformat()
        data["modified"] = datetime.now().isoformat()

        # Generate new IDs for units
        for unit_data in data["units"]:
            unit_data["id"] = self._generate_id()

        self._current = Roster.from_dict(data)
        logger.info(f"Duplicated roster as '{new_name}'")
        return self._current


# Module-level manager instance
_manager = RosterManager()


def get_manager() -> RosterManager:
    """
    Get the module-level RosterManager instance.

    Returns:
        The singleton RosterManager
    """
    return _manager


def new_roster(
    name: str,
    game_system: str = "",
    faction: str = "",
    mode: str = "wargame",
    points_limit: int = 0,
    **kwargs,
) -> Roster:
    """
    Create a new roster and set it as current.

    Convenience wrapper for RosterManager.new_roster().

    Args:
        name: Display name for the roster
        game_system: Game system ID
        faction: Faction/army name
        mode: "wargame" or "rpg"
        points_limit: Maximum points (0 = unlimited)
        **kwargs: Additional arguments passed to Roster

    Returns:
        The new Roster instance
    """
    return _manager.new_roster(
        name=name,
        game_system=game_system,
        faction=faction,
        mode=mode,
        points_limit=points_limit,
        **kwargs,
    )


def current_roster() -> Optional[Roster]:
    """
    Get the currently active roster.

    Returns:
        Current Roster or None if no roster is active
    """
    return _manager.current


def require_roster() -> Roster:
    """
    Get the current roster, raising if none exists.

    Returns:
        Current Roster

    Raises:
        NoActiveRosterError: If no roster is active
    """
    roster = _manager.current
    if roster is None:
        raise NoActiveRosterError("No active roster. Create one with new_roster() first.")
    return roster


def add_custom_unit(
    name: str,
    slot_type: SlotType | str = SlotType.CUSTOM,
    **kwargs,
) -> RosterUnit:
    """
    Create a custom unit and add it to the current roster.

    Args:
        name: Unit/character name
        slot_type: Organizational slot
        **kwargs: Additional unit properties (stats, weapons, etc.)

    Returns:
        New RosterUnit instance

    Raises:
        NoActiveRosterError: If no roster is active
    """
    unit = _manager.create_custom_unit(name=name, slot_type=slot_type, **kwargs)
    roster = require_roster()
    roster.add_unit(unit)
    return unit


def get_blank_template(mode: str = "wargame") -> dict[str, Any]:
    """
    Get a blank template dictionary for unit creation.

    Args:
        mode: "wargame" or "rpg"

    Returns:
        Dictionary template with empty/default values
    """
    return _manager.create_blank_unit_template(mode)


def save_roster(filename: Optional[str] = None) -> Path:
    """
    Save the current roster to file.

    Args:
        filename: Optional filename (defaults to roster name)

    Returns:
        Path to saved file
    """
    return _manager.save(filename)


def load_roster(filename: str) -> Roster:
    """
    Load a roster from file.

    Args:
        filename: Filename to load

    Returns:
        Loaded Roster (also set as current)
    """
    return _manager.load(filename)


def list_rosters() -> list[str]:
    """
    List all saved roster files.

    Returns:
        List of roster names
    """
    return _manager.list_saved()


def get_unit(name_or_id: str) -> Optional[RosterUnit]:
    """
    Find a unit in the current roster.

    Args:
        name_or_id: Name or ID to search for

    Returns:
        Matching unit or None
    """
    roster = _manager.current
    if roster:
        return roster.get_unit(name_or_id)
    return None


def damage_unit(name_or_id: str, wounds: int = 1) -> str:
    """
    Apply damage to a unit in the current roster.

    Args:
        name_or_id: Name or ID of unit to damage
        wounds: Amount of damage

    Returns:
        Description of damage result
    """
    unit = get_unit(name_or_id)
    if unit:
        return unit.take_damage(wounds)
    return f"Unit '{name_or_id}' not found."


def heal_unit(name_or_id: str, wounds: int = 1) -> str:
    """
    Heal a unit in the current roster.

    Args:
        name_or_id: Name or ID of unit to heal
        wounds: Amount of healing

    Returns:
        Description of healing result
    """
    unit = get_unit(name_or_id)
    if unit:
        return unit.heal(wounds)
    return f"Unit '{name_or_id}' not found."
