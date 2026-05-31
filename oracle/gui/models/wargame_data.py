"""
Wargame Data Model - Bridge between gamesystems.py and GUI.

Provides:
- Observable game system state for UI binding
- Cached faction/unit data
- Search and filter functions for army building
- Slot type organization for force org charts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable, Any, List
from enum import Enum
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Import the core game systems module
from oracle.gamesystems import (
    GameSystemManager,
    GameSystem,
    UnitType,
    UnitProfile,
    WeaponProfile,
    Faction,
    RuleReference,
    get_manager as get_gamesystem_manager,
)


class SlotCategory(Enum):
    """
    Battlefield role categories for unit organization.

    Maps game-system-specific categories to unified slots.
    """
    HQ = "hq"
    TROOPS = "troops"
    ELITES = "elites"
    FAST_ATTACK = "fast_attack"
    HEAVY_SUPPORT = "heavy_support"
    FLYER = "flyer"
    TRANSPORT = "transport"
    LORD_OF_WAR = "lord_of_war"
    # Fantasy-specific
    LORDS = "lords"
    HEROES = "heroes"
    CORE = "core"
    SPECIAL = "special"
    RARE = "rare"
    # Universal
    UNCATEGORIZED = "uncategorized"

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        names = {
            SlotCategory.HQ: "HQ",
            SlotCategory.TROOPS: "Troops",
            SlotCategory.ELITES: "Elites",
            SlotCategory.FAST_ATTACK: "Fast Attack",
            SlotCategory.HEAVY_SUPPORT: "Heavy Support",
            SlotCategory.FLYER: "Flyers",
            SlotCategory.TRANSPORT: "Transports",
            SlotCategory.LORD_OF_WAR: "Lords of War",
            SlotCategory.LORDS: "Lords",
            SlotCategory.HEROES: "Heroes",
            SlotCategory.CORE: "Core",
            SlotCategory.SPECIAL: "Special",
            SlotCategory.RARE: "Rare",
            SlotCategory.UNCATEGORIZED: "Other",
        }
        return names.get(self, self.value.replace("_", " ").title())

    @classmethod
    def from_category_string(cls, category: str) -> "SlotCategory":
        """Convert a category string from TOML data to SlotCategory."""
        mapping = {
            "hq": cls.HQ,
            "headquarters": cls.HQ,
            "troops": cls.TROOPS,
            "core": cls.CORE,
            "elites": cls.ELITES,
            "elite": cls.ELITES,
            "fast_attack": cls.FAST_ATTACK,
            "fast attack": cls.FAST_ATTACK,
            "cavalry": cls.FAST_ATTACK,
            "heavy_support": cls.HEAVY_SUPPORT,
            "heavy support": cls.HEAVY_SUPPORT,
            "flyer": cls.FLYER,
            "flyers": cls.FLYER,
            "transport": cls.TRANSPORT,
            "dedicated_transport": cls.TRANSPORT,
            "lord_of_war": cls.LORD_OF_WAR,
            "lords of war": cls.LORD_OF_WAR,
            "lords": cls.LORDS,
            "lord": cls.LORDS,
            "heroes": cls.HEROES,
            "hero": cls.HEROES,
            "special": cls.SPECIAL,
            "rare": cls.RARE,
        }
        return mapping.get(category.lower().strip(), cls.UNCATEGORIZED)


@dataclass
class UnitCard:
    """
    Simplified unit data for display in army builder lists.

    Contains the essential info needed for unit selection UI
    without the full profile overhead.
    """
    name: str
    faction: str
    points: int
    models: str  # e.g., "5-10" or "1"
    slot: SlotCategory
    unit_type: UnitType
    threat_level: str
    tactical_role: str
    # Reference to full profile
    profile: UnitProfile

    @classmethod
    def from_profile(cls, profile: UnitProfile, category: str = "") -> "UnitCard":
        """Create a UnitCard from a UnitProfile."""
        # Determine slot from category or unit type
        if category:
            slot = SlotCategory.from_category_string(category)
        else:
            # Fallback mapping by unit type
            type_to_slot = {
                UnitType.CHARACTER: SlotCategory.HQ,
                UnitType.INFANTRY: SlotCategory.TROOPS,
                UnitType.CAVALRY: SlotCategory.FAST_ATTACK,
                UnitType.VEHICLE: SlotCategory.HEAVY_SUPPORT,
                UnitType.MONSTER: SlotCategory.ELITES,
                UnitType.FLYER: SlotCategory.FLYER,
                UnitType.WARMACHINE: SlotCategory.HEAVY_SUPPORT,
                UnitType.SWARM: SlotCategory.TROOPS,
            }
            slot = type_to_slot.get(profile.unit_type, SlotCategory.UNCATEGORIZED)

        return cls(
            name=profile.name,
            faction=profile.faction,
            points=profile.points_cost,
            models=profile.models_per_unit,
            slot=slot,
            unit_type=profile.unit_type,
            threat_level=profile.threat_level,
            tactical_role=profile.tactical_role,
            profile=profile,
        )

    def __str__(self) -> str:
        """Format for list display."""
        return f"{self.name} ({self.points}pts)"


# Observer callback types
WargameDataObserver = Callable[["WargameDataModel"], None]
# Event-based observer: (event_type, data) -> None
WargameEventObserver = Callable[[str, Any], None]


class WargameDataModel:
    """
    Observable wrapper around GameSystemManager for GUI integration.

    Provides:
    - Event notification when system/faction changes
    - Cached unit cards for fast list rendering
    - Filter/search optimized for UI
    - Organized unit lists by slot category
    """

    def __init__(self):
        self._manager = get_gamesystem_manager()
        self._observers: list[WargameDataObserver] = []
        self._event_observers: list[WargameEventObserver] = []

        # Cached data
        self._unit_cards: dict[str, list[UnitCard]] = {}  # faction -> cards
        self._current_system: Optional[GameSystem] = None
        self._current_faction: Optional[Faction] = None

    # -------------------------------------------------------------------------
    # Observer Pattern
    # -------------------------------------------------------------------------

    def add_observer(self, observer: WargameEventObserver) -> None:
        """
        Register an event-based observer for data changes.

        The observer receives (event_type, data) where event_type is one of:
        - "system_changed": data is the new GameSystem
        - "faction_changed": data is the new Faction
        - "data_changed": data is None (generic update)
        """
        if observer not in self._event_observers:
            self._event_observers.append(observer)

    def remove_observer(self, observer: WargameEventObserver) -> None:
        """Remove an observer."""
        if observer in self._event_observers:
            self._event_observers.remove(observer)
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify_observers(self, event: str = "data_changed", data: Any = None) -> None:
        """
        Notify all observers of a data change.

        Args:
            event: Event type string
            data: Event-specific data
        """
        # Notify event-based observers
        for observer in self._event_observers:
            try:
                observer(event, data)
            except Exception:
                pass  # Don't let observer errors break the model

        # Notify legacy observers (backwards compatibility)
        for observer in self._observers:
            try:
                observer(self)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # System Selection
    # -------------------------------------------------------------------------

    @property
    def current_system(self) -> Optional[GameSystem]:
        """Get the currently selected game system."""
        return self._current_system

    @property
    def current_system_name(self) -> str:
        """Get display name of current system."""
        if self._current_system:
            return self._current_system.display_name
        return "No System Selected"

    @property
    def current_faction(self) -> Optional[Faction]:
        """Get the currently selected faction."""
        return self._current_faction

    @property
    def current_faction_name(self) -> str:
        """Get name of current faction."""
        if self._current_faction:
            return self._current_faction.name
        return "No Faction Selected"

    def list_available_systems(self) -> list[tuple[str, str]]:
        """
        List game systems that have data files.

        Returns:
            List of (system_id, display_name) tuples
        """
        systems = self._manager.list_available_systems()
        return [(s.id, s.display_name) for s in systems]

    def set_system(self, system_id: str) -> bool:
        """
        Set the current game system.

        Args:
            system_id: System ID (e.g., 'oldhammer_2e')

        Returns:
            True if system was found and set
        """
        # Try by ID first
        system = GameSystem.from_id(system_id)
        if system:
            self._manager.set_system(system)
            self._current_system = system
            self._current_faction = None
            self._rebuild_unit_cache()
            self._notify_observers("system_changed", system)
            return True

        # Try by name/alias
        if self._manager.set_system_by_name(system_id):
            self._current_system = self._manager.current_system
            self._current_faction = None
            self._rebuild_unit_cache()
            self._notify_observers("system_changed", self._current_system)
            return True

        return False

    def list_factions(self) -> list[str]:
        """List available factions for current system."""
        return self._manager.list_factions()

    def set_faction(self, faction_name: str) -> bool:
        """
        Set the current faction.

        Args:
            faction_name: Faction name (partial match supported)

        Returns:
            True if faction was found and set
        """
        if self._manager.set_faction(faction_name):
            self._current_faction = self._manager.current_faction
            self._notify_observers("faction_changed", self._current_faction)
            return True
        return False

    def get_faction(self, name: str) -> Optional[Faction]:
        """Get a faction without setting it as current."""
        return self._manager.get_faction(name)

    # -------------------------------------------------------------------------
    # Unit Data
    # -------------------------------------------------------------------------

    def _rebuild_unit_cache(self) -> None:
        """Rebuild the unit cards cache from loaded factions."""
        self._unit_cards.clear()

        for faction in self._manager.factions.values():
            cards = []
            for unit in faction.units.values():
                # Get category from unit stats if available
                category = unit.stats.get("category", "")
                card = UnitCard.from_profile(unit, category)
                cards.append(card)

            # Sort by slot then name
            cards.sort(key=lambda c: (c.slot.value, c.name))
            self._unit_cards[faction.name.lower()] = cards

    def get_unit_cards(self, faction_name: Optional[str] = None) -> list[UnitCard]:
        """
        Get unit cards for a faction.

        Args:
            faction_name: Faction name (uses current faction if None)

        Returns:
            List of UnitCard objects
        """
        if faction_name is None:
            if self._current_faction:
                faction_name = self._current_faction.name
            else:
                return []

        return self._unit_cards.get(faction_name.lower(), [])

    def get_units_by_slot(
        self,
        slot: SlotCategory,
        faction_name: Optional[str] = None
    ) -> list[UnitCard]:
        """
        Get units filtered by slot category.

        Args:
            slot: Slot category to filter by
            faction_name: Faction (uses current if None)

        Returns:
            List of matching UnitCard objects
        """
        cards = self.get_unit_cards(faction_name)
        return [c for c in cards if c.slot == slot]

    def get_available_slots(self, faction_name: Optional[str] = None) -> list[SlotCategory]:
        """
        Get slot categories that have units in the faction.

        Args:
            faction_name: Faction (uses current if None)

        Returns:
            List of SlotCategory values that have units
        """
        cards = self.get_unit_cards(faction_name)
        slots = set(c.slot for c in cards)
        # Return in logical order
        order = [
            SlotCategory.HQ, SlotCategory.LORDS, SlotCategory.HEROES,
            SlotCategory.TROOPS, SlotCategory.CORE,
            SlotCategory.ELITES, SlotCategory.SPECIAL,
            SlotCategory.FAST_ATTACK,
            SlotCategory.HEAVY_SUPPORT, SlotCategory.RARE,
            SlotCategory.FLYER, SlotCategory.TRANSPORT,
            SlotCategory.LORD_OF_WAR, SlotCategory.UNCATEGORIZED,
        ]
        return [s for s in order if s in slots]

    def search_units(
        self,
        query: str,
        faction_name: Optional[str] = None
    ) -> list[UnitCard]:
        """
        Search units by name, role, or type.

        Args:
            query: Search string (case-insensitive)
            faction_name: Faction to search (uses current if None)

        Returns:
            List of matching UnitCard objects
        """
        cards = self.get_unit_cards(faction_name)
        query_lower = query.lower()

        return [
            c for c in cards
            if (query_lower in c.name.lower() or
                query_lower in c.tactical_role.lower() or
                query_lower in c.unit_type.value.lower())
        ]

    def get_unit_profile(self, unit_name: str) -> Optional[UnitProfile]:
        """
        Get full unit profile by name.

        Searches current faction first, then all factions.
        """
        return self._manager.lookup_unit(unit_name)

    # -------------------------------------------------------------------------
    # Rules Reference
    # -------------------------------------------------------------------------

    def lookup_rule(self, rule_name: str) -> Optional[RuleReference]:
        """Look up a rule by name."""
        return self._manager.lookup_rule(rule_name)

    def search_rules(self, query: str) -> list[RuleReference]:
        """Search rules by query string."""
        return self._manager.search_rules(query)

    def get_all_rules(self) -> dict[str, RuleReference]:
        """Get all loaded rules for current system."""
        return self._manager.rules

    @property
    def rules(self) -> dict[str, RuleReference]:
        """Get all loaded rules for current system (alias for get_all_rules)."""
        return self._manager.rules

    # -------------------------------------------------------------------------
    # Phase Loading
    # -------------------------------------------------------------------------

    def _get_system_data_path(self) -> Optional[Path]:
        """Get the data path for the current game system."""
        if not self._current_system:
            return None

        # Map system IDs to folder names
        system_folders = {
            "oldhammer_2e": "oldhammer_2e",
            "old_world": "old_world",
            "grimdark_future": "grimdark_future",
            "age_of_fantasy": "age_of_fantasy",
            "trench_crusade": "trench_crusade",
        }

        folder = system_folders.get(self._current_system.id)
        if not folder:
            return None

        # Try to find the data path
        base_paths = [
            Path(__file__).parent.parent.parent / "data" / "wargames" / folder,
            Path("oracle/data/wargames") / folder,
        ]

        for path in base_paths:
            if path.exists():
                return path

        return None

    def get_phases(self) -> List[str]:
        """
        Get phase names for the current game system from TOML.

        Returns:
            List of phase names in order, or default phases if not found
        """
        data_path = self._get_system_data_path()
        if not data_path:
            return ["Movement", "Shooting", "Combat", "Morale"]

        phases_file = data_path / "phases.toml"
        if not phases_file.exists():
            return ["Movement", "Shooting", "Combat", "Morale"]

        try:
            with open(phases_file, "rb") as f:
                data = tomllib.load(f)

            phases = data.get("phases", [])
            if not phases:
                return ["Movement", "Shooting", "Combat", "Morale"]

            # Sort by order and extract names
            sorted_phases = sorted(phases, key=lambda p: p.get("order", 0))
            return [p.get("name", "Unknown") for p in sorted_phases]

        except Exception:
            return ["Movement", "Shooting", "Combat", "Morale"]

    def get_phase_details(self) -> List[dict]:
        """
        Get full phase information including descriptions and steps.

        Returns:
            List of phase dictionaries with name, description, order, steps, etc.
        """
        data_path = self._get_system_data_path()
        if not data_path:
            return []

        phases_file = data_path / "phases.toml"
        if not phases_file.exists():
            return []

        try:
            with open(phases_file, "rb") as f:
                data = tomllib.load(f)

            phases = data.get("phases", [])
            if not phases:
                return []

            # Sort by order
            sorted_phases = sorted(phases, key=lambda p: p.get("order", 0))

            # Return full phase data
            result = []
            for p in sorted_phases:
                phase_info = {
                    "name": p.get("name", "Unknown"),
                    "description": p.get("description", ""),
                    "order": p.get("order", 0),
                    "steps": p.get("steps", []),
                    "available_actions": p.get("available_actions", []),
                }
                result.append(phase_info)

            return result

        except Exception:
            return []

    def get_turn_structure(self) -> dict:
        """
        Get turn structure info (e.g., alternating activations vs I-GO-U-GO).

        Returns:
            Dictionary with turn structure details
        """
        data_path = self._get_system_data_path()
        if not data_path:
            return {"name": "Standard", "description": "Standard turn structure"}

        phases_file = data_path / "phases.toml"
        if not phases_file.exists():
            return {"name": "Standard", "description": "Standard turn structure"}

        try:
            with open(phases_file, "rb") as f:
                data = tomllib.load(f)

            turn_structure = data.get("turn_structure", {})
            return {
                "name": turn_structure.get("name", "Standard"),
                "description": turn_structure.get("description", ""),
                "key_concept": turn_structure.get("key_concept", ""),
            }

        except Exception:
            return {"name": "Standard", "description": "Standard turn structure"}

    # -------------------------------------------------------------------------
    # Faction Info
    # -------------------------------------------------------------------------

    def get_faction_info(self, faction_name: Optional[str] = None) -> dict[str, Any]:
        """
        Get faction metadata for display.

        Args:
            faction_name: Faction (uses current if None)

        Returns:
            Dictionary with name, description, playstyle, strengths, weaknesses
        """
        faction = self._current_faction
        if faction_name:
            faction = self.get_faction(faction_name)

        if not faction:
            return {}

        return {
            "name": faction.name,
            "description": faction.description,
            "playstyle": faction.playstyle,
            "strengths": faction.strengths,
            "weaknesses": faction.weaknesses,
            "unit_count": len(faction.units),
        }

    # -------------------------------------------------------------------------
    # Tactical AI Support
    # -------------------------------------------------------------------------

    def get_tactical_info(self, unit_name: str) -> dict[str, Any]:
        """
        Get tactical information for a unit (for AI decision-making).

        Returns:
            Dictionary with threat_level, tactical_role, preferred_targets, weaknesses
        """
        return self._manager.get_tactical_info(unit_name)

    def compare_units(self, unit1_name: str, unit2_name: str) -> Optional[str]:
        """
        Generate a comparison between two units.

        Returns:
            Formatted comparison string
        """
        return self._manager.compare_units(unit1_name, unit2_name)


# Module-level singleton
_wargame_data: Optional[WargameDataModel] = None


def get_wargame_data() -> WargameDataModel:
    """
    Get the module-level WargameDataModel instance.

    Returns:
        The singleton WargameDataModel
    """
    global _wargame_data
    if _wargame_data is None:
        _wargame_data = WargameDataModel()
    return _wargame_data
