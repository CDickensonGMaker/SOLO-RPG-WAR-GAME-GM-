"""
Roster Model - Bridge between roster.py and GUI.

Provides:
- Observable roster state for UI binding
- Dual roster management (friendly + enemy)
- Wound/casualty tracking with UI notifications
- Battle state persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from pathlib import Path
from datetime import datetime
import json

# Import core roster module
from oracle.roster import (
    Roster,
    RosterUnit,
    RosterManager,
    SlotType,
    UnitStatus,
    get_manager as get_roster_manager,
)

# Import game systems for unit import
from oracle.gamesystems import UnitProfile


# Observer callback types
RosterObserver = Callable[["BattleRosterModel"], None]
UnitObserver = Callable[[RosterUnit], None]


@dataclass
class BattleState:
    """
    Current battle state tracking turn and phase.
    """
    turn_number: int = 1
    current_phase: str = "Movement"
    phases: list[str] = field(default_factory=lambda: [
        "Movement", "Psychic", "Shooting", "Charge", "Combat", "Morale"
    ])

    # Battle metadata
    battle_name: str = ""
    mission: str = ""
    points_limit: int = 0
    deployment: str = ""

    # History
    turn_log: list[str] = field(default_factory=list)

    def advance_phase(self) -> str:
        """Advance to next phase, or next turn if at end."""
        current_idx = self.phases.index(self.current_phase)
        if current_idx >= len(self.phases) - 1:
            # End of turn
            self.turn_number += 1
            self.current_phase = self.phases[0]
            self.turn_log.append(f"--- Turn {self.turn_number} ---")
        else:
            self.current_phase = self.phases[current_idx + 1]
        return self.current_phase

    def set_phase(self, phase: str) -> bool:
        """Set phase directly."""
        if phase in self.phases:
            self.current_phase = phase
            return True
        return False

    def log_event(self, event: str) -> None:
        """Log a battle event."""
        self.turn_log.append(f"T{self.turn_number} {self.current_phase}: {event}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "turn_number": self.turn_number,
            "current_phase": self.current_phase,
            "phases": self.phases,
            "battle_name": self.battle_name,
            "mission": self.mission,
            "points_limit": self.points_limit,
            "deployment": self.deployment,
            "turn_log": self.turn_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BattleState":
        """Deserialize from dict."""
        return cls(
            turn_number=data.get("turn_number", 1),
            current_phase=data.get("current_phase", "Movement"),
            phases=data.get("phases", ["Movement", "Psychic", "Shooting", "Charge", "Combat", "Morale"]),
            battle_name=data.get("battle_name", ""),
            mission=data.get("mission", ""),
            points_limit=data.get("points_limit", 0),
            deployment=data.get("deployment", ""),
            turn_log=data.get("turn_log", []),
        )


class BattleRosterModel:
    """
    Observable model managing both friendly and enemy rosters for battle.

    Provides:
    - Separate friendly and enemy force tracking
    - UI notification on any change
    - Wound tracking at model level
    - Battle state (turns, phases)
    - Save/load battle state
    """

    def __init__(self):
        self._roster_manager = get_roster_manager()

        # Dual rosters
        self._friendly_roster: Optional[Roster] = None
        self._enemy_roster: Optional[Roster] = None

        # Battle state
        self._battle_state = BattleState()

        # Observers
        self._roster_observers: list[RosterObserver] = []
        self._unit_observers: list[UnitObserver] = []

        # Save directory for battles
        self._save_dir = Path.home() / ".oracle" / "battles"
        self._save_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Observer Pattern
    # -------------------------------------------------------------------------

    def add_roster_observer(self, observer: RosterObserver) -> None:
        """Register observer for roster-level changes."""
        if observer not in self._roster_observers:
            self._roster_observers.append(observer)

    def remove_roster_observer(self, observer: RosterObserver) -> None:
        """Remove roster observer."""
        if observer in self._roster_observers:
            self._roster_observers.remove(observer)

    def add_unit_observer(self, observer: UnitObserver) -> None:
        """Register observer for unit-level changes (damage, status)."""
        if observer not in self._unit_observers:
            self._unit_observers.append(observer)

    def remove_unit_observer(self, observer: UnitObserver) -> None:
        """Remove unit observer."""
        if observer in self._unit_observers:
            self._unit_observers.remove(observer)

    def _notify_roster_change(self) -> None:
        """Notify roster observers."""
        for observer in self._roster_observers:
            try:
                observer(self)
            except Exception:
                pass

    def _notify_unit_change(self, unit: RosterUnit) -> None:
        """Notify unit observers."""
        for observer in self._unit_observers:
            try:
                observer(unit)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Roster Management
    # -------------------------------------------------------------------------

    @property
    def friendly_roster(self) -> Optional[Roster]:
        """Get the friendly forces roster."""
        return self._friendly_roster

    @property
    def enemy_roster(self) -> Optional[Roster]:
        """Get the enemy forces roster."""
        return self._enemy_roster

    @property
    def battle_state(self) -> BattleState:
        """Get current battle state."""
        return self._battle_state

    def new_battle(
        self,
        battle_name: str = "",
        friendly_name: str = "Your Army",
        enemy_name: str = "Enemy Forces",
        game_system: str = "",
        friendly_faction: str = "",
        enemy_faction: str = "",
        points_limit: int = 0,
        mission: str = "",
    ) -> None:
        """
        Start a new battle with fresh rosters.

        Args:
            battle_name: Name for this battle
            friendly_name: Name for your roster
            enemy_name: Name for enemy roster
            game_system: Game system ID
            friendly_faction: Your faction
            enemy_faction: Enemy faction
            points_limit: Points limit for armies
            mission: Mission type
        """
        self._friendly_roster = Roster(
            name=friendly_name,
            game_system=game_system,
            faction=friendly_faction,
            mode="wargame",
            points_limit=points_limit,
        )

        self._enemy_roster = Roster(
            name=enemy_name,
            game_system=game_system,
            faction=enemy_faction,
            mode="wargame",
            points_limit=points_limit,
        )

        self._battle_state = BattleState(
            battle_name=battle_name,
            mission=mission,
            points_limit=points_limit,
        )

        self._notify_roster_change()

    def load_friendly_roster(self, filename: str) -> bool:
        """Load a saved roster as friendly forces."""
        try:
            roster = self._roster_manager.load(filename)
            self._friendly_roster = roster
            self._notify_roster_change()
            return True
        except Exception:
            return False

    def load_enemy_roster(self, filename: str) -> bool:
        """Load a saved roster as enemy forces."""
        try:
            # Save current, load enemy, restore current
            saved_current = self._roster_manager.current
            roster = self._roster_manager.load(filename)
            self._enemy_roster = roster
            self._roster_manager.current = saved_current
            self._notify_roster_change()
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Unit Management
    # -------------------------------------------------------------------------

    def add_unit_to_friendly(
        self,
        name: str,
        slot_type: SlotType | str = SlotType.TROOPS,
        stats: Optional[dict[str, Any]] = None,
        weapons: Optional[list[dict[str, Any]]] = None,
        wounds: int = 1,
        models: int = 1,
        points: int = 0,
        **kwargs
    ) -> Optional[RosterUnit]:
        """
        Add a custom unit to friendly forces.

        Returns:
            The created RosterUnit, or None if no roster
        """
        if not self._friendly_roster:
            return None

        if isinstance(slot_type, str):
            slot_type = SlotType.from_string(slot_type)

        unit = self._roster_manager.create_custom_unit(
            name=name,
            slot_type=slot_type,
            stats=stats or {},
            weapons=weapons or [],
            wounds=wounds,
            models=models,
            points=points,
            **kwargs
        )

        self._friendly_roster.add_unit(unit)
        self._notify_roster_change()
        return unit

    def add_unit_to_enemy(
        self,
        name: str,
        slot_type: SlotType | str = SlotType.TROOPS,
        stats: Optional[dict[str, Any]] = None,
        weapons: Optional[list[dict[str, Any]]] = None,
        wounds: int = 1,
        models: int = 1,
        points: int = 0,
        **kwargs
    ) -> Optional[RosterUnit]:
        """Add a custom unit to enemy forces."""
        if not self._enemy_roster:
            return None

        if isinstance(slot_type, str):
            slot_type = SlotType.from_string(slot_type)

        unit = self._roster_manager.create_custom_unit(
            name=name,
            slot_type=slot_type,
            stats=stats or {},
            weapons=weapons or [],
            wounds=wounds,
            models=models,
            points=points,
            **kwargs
        )

        self._enemy_roster.add_unit(unit)
        self._notify_roster_change()
        return unit

    def add_unit_from_profile(
        self,
        profile: UnitProfile,
        to_friendly: bool = True,
        model_count: Optional[int] = None
    ) -> Optional[RosterUnit]:
        """
        Add a unit from a game system UnitProfile.

        Args:
            profile: UnitProfile from gamesystems
            to_friendly: True for friendly roster, False for enemy
            model_count: Override model count (uses profile default if None)

        Returns:
            The created RosterUnit
        """
        roster = self._friendly_roster if to_friendly else self._enemy_roster
        if not roster:
            return None

        # Parse model count from profile
        models_str = str(profile.models_per_unit)
        if model_count is not None:
            models = model_count
        elif "-" in models_str:
            # Variable size - use minimum
            models = int(models_str.split("-")[0])
        else:
            models = int(models_str) if models_str.isdigit() else 1

        # Get wounds per model
        wounds = profile.stats.get("W", profile.stats.get("wounds", 1))
        if isinstance(wounds, str):
            wounds = int(wounds) if wounds.isdigit() else 1

        # Map unit type to slot
        slot_mapping = {
            "character": SlotType.HQ,
            "infantry": SlotType.TROOPS,
            "cavalry": SlotType.FAST_ATTACK,
            "vehicle": SlotType.HEAVY_SUPPORT,
            "monster": SlotType.ELITES,
            "flyer": SlotType.FLYER,
            "warmachine": SlotType.HEAVY_SUPPORT,
            "swarm": SlotType.TROOPS,
        }
        slot = slot_mapping.get(profile.unit_type.value, SlotType.TROOPS)

        # Convert weapons to dict format
        weapons = []
        for w in profile.weapons:
            weapons.append({
                "name": w.name,
                "range": w.range,
                "strength": w.strength,
                "ap": w.ap,
                "damage": w.damage,
                "abilities": w.abilities,
                "type": w.type,
                "shots": w.shots,
            })

        unit = self._roster_manager.create_custom_unit(
            name=profile.name,
            slot_type=slot,
            stats=dict(profile.stats),
            weapons=weapons,
            wargear=list(profile.wargear),
            abilities=list(profile.special_rules),
            wounds=wounds,
            models=models,
            points=profile.points_cost,
            threat_level=profile.threat_level,
            tactical_role=profile.tactical_role,
        )
        unit.source = profile.game_system

        roster.add_unit(unit)
        self._notify_roster_change()
        return unit

    def remove_unit(self, unit_id: str, from_friendly: bool = True) -> bool:
        """
        Remove a unit from a roster.

        Args:
            unit_id: Unit ID to remove
            from_friendly: True to remove from friendly, False for enemy

        Returns:
            True if removed successfully
        """
        roster = self._friendly_roster if from_friendly else self._enemy_roster
        if not roster:
            return False

        try:
            roster.remove_unit(unit_id)
            self._notify_roster_change()
            return True
        except Exception:
            return False

    def get_unit(self, name_or_id: str, from_friendly: bool = True) -> Optional[RosterUnit]:
        """Find a unit by name or ID."""
        roster = self._friendly_roster if from_friendly else self._enemy_roster
        if roster:
            return roster.get_unit(name_or_id)
        return None

    # -------------------------------------------------------------------------
    # Wound/Casualty Tracking
    # -------------------------------------------------------------------------

    def damage_unit(
        self,
        unit_id: str,
        wounds: int,
        from_friendly: bool = True
    ) -> str:
        """
        Apply damage to a unit.

        Args:
            unit_id: Unit name or ID
            wounds: Amount of damage
            from_friendly: Which roster

        Returns:
            Description of damage result
        """
        unit = self.get_unit(unit_id, from_friendly)
        if not unit:
            return f"Unit '{unit_id}' not found."

        result = unit.take_damage(wounds)

        # Log the event
        self._battle_state.log_event(result)

        # Notify observers
        self._notify_unit_change(unit)
        self._notify_roster_change()

        return result

    def heal_unit(
        self,
        unit_id: str,
        wounds: int,
        from_friendly: bool = True
    ) -> str:
        """Heal a unit."""
        unit = self.get_unit(unit_id, from_friendly)
        if not unit:
            return f"Unit '{unit_id}' not found."

        result = unit.heal(wounds)
        self._battle_state.log_event(result)
        self._notify_unit_change(unit)
        self._notify_roster_change()
        return result

    def restore_model(self, unit_id: str, from_friendly: bool = True) -> str:
        """Restore a destroyed model to a unit."""
        unit = self.get_unit(unit_id, from_friendly)
        if not unit:
            return f"Unit '{unit_id}' not found."

        result = unit.restore_model()
        self._battle_state.log_event(result)
        self._notify_unit_change(unit)
        self._notify_roster_change()
        return result

    def set_unit_status(
        self,
        unit_id: str,
        status: UnitStatus | str,
        from_friendly: bool = True
    ) -> str:
        """Set unit status manually."""
        unit = self.get_unit(unit_id, from_friendly)
        if not unit:
            return f"Unit '{unit_id}' not found."

        result = unit.set_status(status)
        self._battle_state.log_event(result)
        self._notify_unit_change(unit)
        self._notify_roster_change()
        return result

    # -------------------------------------------------------------------------
    # Battle State
    # -------------------------------------------------------------------------

    def advance_phase(self) -> str:
        """Advance to next phase/turn."""
        phase = self._battle_state.advance_phase()
        self._notify_roster_change()
        return phase

    def set_phase(self, phase: str) -> bool:
        """Set current phase directly."""
        result = self._battle_state.set_phase(phase)
        self._notify_roster_change()
        return result

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_friendly_summary(self) -> dict[str, Any]:
        """Get summary statistics for friendly forces."""
        if not self._friendly_roster:
            return {}
        return self._friendly_roster.summary()

    def get_enemy_summary(self) -> dict[str, Any]:
        """Get summary statistics for enemy forces."""
        if not self._enemy_roster:
            return {}
        return self._enemy_roster.summary()

    def get_active_friendly_units(self) -> list[RosterUnit]:
        """Get list of active (non-destroyed) friendly units."""
        if self._friendly_roster:
            return self._friendly_roster.active_units
        return []

    def get_active_enemy_units(self) -> list[RosterUnit]:
        """Get list of active enemy units."""
        if self._enemy_roster:
            return self._enemy_roster.active_units
        return []

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def reset_all_units(self) -> str:
        """Reset all units to fresh status with full wounds."""
        results = []
        if self._friendly_roster:
            results.append(f"Friendly: {self._friendly_roster.reset_all()}")
        if self._enemy_roster:
            results.append(f"Enemy: {self._enemy_roster.reset_all()}")

        self._notify_roster_change()
        return " ".join(results)

    # -------------------------------------------------------------------------
    # Save/Load
    # -------------------------------------------------------------------------

    def save_battle(self, filename: Optional[str] = None) -> Path:
        """
        Save complete battle state to file.

        Args:
            filename: Filename (auto-generated if None)

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = self._battle_state.battle_name or "battle"
            safe_name = "".join(c for c in name if c.isalnum() or c in "_-")
            filename = f"{safe_name}_{timestamp}.json"

        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        filepath = self._save_dir / filename

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "battle_state": self._battle_state.to_dict(),
            "friendly_roster": self._friendly_roster.to_dict() if self._friendly_roster else None,
            "enemy_roster": self._enemy_roster.to_dict() if self._enemy_roster else None,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath

    def load_battle(self, filename: str) -> bool:
        """
        Load battle state from file.

        Args:
            filename: Filename to load

        Returns:
            True if loaded successfully
        """
        filepath = self._save_dir / filename
        if not filepath.exists():
            filepath = self._save_dir / f"{filename}.json"
        if not filepath.exists():
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._battle_state = BattleState.from_dict(data.get("battle_state", {}))

            if data.get("friendly_roster"):
                self._friendly_roster = Roster.from_dict(data["friendly_roster"])
            else:
                self._friendly_roster = None

            if data.get("enemy_roster"):
                self._enemy_roster = Roster.from_dict(data["enemy_roster"])
            else:
                self._enemy_roster = None

            self._notify_roster_change()
            return True

        except (json.JSONDecodeError, KeyError):
            return False

    def list_saved_battles(self) -> list[dict[str, Any]]:
        """List available saved battles."""
        battles = []
        for filepath in self._save_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                battles.append({
                    "filename": filepath.name,
                    "name": data.get("battle_state", {}).get("battle_name", filepath.stem),
                    "saved_at": data.get("saved_at", ""),
                    "turn": data.get("battle_state", {}).get("turn_number", 1),
                })
            except Exception:
                pass

        # Sort by save time, newest first
        battles.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return battles


# Module-level singleton
_battle_model: Optional[BattleRosterModel] = None


def get_battle_roster() -> BattleRosterModel:
    """
    Get the module-level BattleRosterModel instance.

    Returns:
        The singleton BattleRosterModel
    """
    global _battle_model
    if _battle_model is None:
        _battle_model = BattleRosterModel()
    return _battle_model
