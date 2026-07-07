"""
Base classes and abstractions for wargame rules engines.

This module provides the foundation for implementing game-specific
rules engines. Dice use an injectable RNG so game logic is testable
with a fixed seed.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    from oracle.roster import RosterUnit


class RollingMode(Enum):
    """Dice rolling mode selection."""

    AUTO = auto()  # System rolls automatically
    MANUAL = auto()  # User enters results
    HYBRID = auto()  # User chooses per roll


@dataclass
class DiceRoll:
    """
    Result of a single die roll.

    Captures all information needed to display and validate a roll:
    the die type, what was rolled, what was needed, and whether
    it succeeded.
    """

    die_type: int  # d6, d10, etc.
    result: int  # What was actually rolled
    target: int  # What we needed to succeed
    success: bool  # Did we meet/exceed target?
    critical: bool = False  # Natural max (6 on d6)
    fumble: bool = False  # Natural 1

    def __str__(self) -> str:
        symbol = "+" if self.success else "-"
        crit = "!" if self.critical else ""
        fumble = "X" if self.fumble else ""
        return f"[{self.result}{crit}{fumble}{symbol}]"


@dataclass
class AttackResult:
    """
    Complete result of an attack action.

    Tracks all dice rolled and their results, plus computed outcomes
    like total hits, wounds, and casualties. Includes narrative text
    for display.
    """

    attacker_name: str
    target_name: str
    weapon_name: str

    # Dice pools (in order of resolution)
    to_hit_rolls: list[DiceRoll] = field(default_factory=list)
    to_wound_rolls: list[DiceRoll] = field(default_factory=list)
    save_rolls: list[DiceRoll] = field(default_factory=list)

    # Computed results
    hits: int = 0
    wounds_caused: int = 0
    saves_made: int = 0
    saves_failed: int = 0
    damage_dealt: int = 0
    models_killed: int = 0

    # Special effects triggered
    effects: list[str] = field(default_factory=list)

    # Narrative text (filled by narrator)
    narrative: str = ""

    @property
    def total_shots(self) -> int:
        """Total number of shots fired."""
        return len(self.to_hit_rolls)

    @property
    def successful_hits(self) -> list[DiceRoll]:
        """All successful to-hit rolls."""
        return [r for r in self.to_hit_rolls if r.success]

    @property
    def successful_wounds(self) -> list[DiceRoll]:
        """All successful to-wound rolls."""
        return [r for r in self.to_wound_rolls if r.success]

    @property
    def failed_saves(self) -> list[DiceRoll]:
        """All failed save rolls (damage goes through)."""
        return [r for r in self.save_rolls if not r.success]

    def summary(self) -> str:
        """Brief summary of the attack result."""
        return (
            f"{self.attacker_name} fires {self.weapon_name} at {self.target_name}: "
            f"{self.hits}/{self.total_shots} hits, "
            f"{self.wounds_caused} wounds, "
            f"{self.saves_failed} unsaved, "
            f"{self.models_killed} killed"
        )

    def dice_breakdown(self) -> str:
        """Detailed breakdown of all dice rolled."""
        lines = []

        if self.to_hit_rolls:
            hits_str = "".join(str(r) for r in self.to_hit_rolls)
            lines.append(f"To Hit: {hits_str} = {self.hits} hits")

        if self.to_wound_rolls:
            wounds_str = "".join(str(r) for r in self.to_wound_rolls)
            lines.append(f"To Wound: {wounds_str} = {self.wounds_caused} wounds")

        if self.save_rolls:
            saves_str = "".join(str(r) for r in self.save_rolls)
            lines.append(f"Saves: {saves_str} = {self.saves_made} saved")

        if self.effects:
            lines.append(f"Effects: {', '.join(self.effects)}")

        return "\n".join(lines)


@dataclass
class MeleeResult:
    """
    Result of a melee combat exchange.

    In some systems (Old World, Oldhammer), melee is resolved
    simultaneously with both sides attacking.
    """

    attacker_name: str
    defender_name: str

    # Attacker's attack
    attacker_result: AttackResult
    # Defender's attack (if they fight back)
    defender_result: AttackResult | None = None

    # Combat resolution (for ranked combat systems)
    attacker_combat_res: int = 0
    defender_combat_res: int = 0
    winner: str = ""  # "attacker", "defender", "draw"
    margin: int = 0  # By how much

    def summary(self) -> str:
        """Brief summary of melee outcome."""
        if self.defender_result:
            return (
                f"{self.attacker_name} vs {self.defender_name}: "
                f"{self.attacker_result.models_killed} vs {self.defender_result.models_killed} casualties, "
                f"Winner: {self.winner} by {self.margin}"
            )
        return self.attacker_result.summary()


@dataclass
class MoraleResult:
    """Result of a morale/leadership check."""

    unit_name: str
    test_type: str  # "break", "panic", "rally", "pinning"
    leadership: int
    roll: DiceRoll
    modifiers: list[tuple[str, int]] = field(default_factory=list)
    passed: bool = False
    consequence: str = ""  # "holds", "falls back", "flees", "rallies"

    @property
    def modified_roll(self) -> int:
        """Roll result after modifiers."""
        total_mod = sum(m[1] for m in self.modifiers)
        return self.roll.result + total_mod

    def summary(self) -> str:
        """Brief summary of morale result."""
        mod_str = ""
        if self.modifiers:
            mods = ", ".join(f"{name} {mod:+d}" for name, mod in self.modifiers)
            mod_str = f" ({mods})"
        result = "PASSED" if self.passed else "FAILED"
        return f"{self.unit_name} {self.test_type} test: {self.roll.result}{mod_str} vs Ld{self.leadership} - {result}: {self.consequence}"


@dataclass
class ActivationResult:
    """
    Result of a unit's complete activation.

    An activation may include movement, shooting, charging, or
    other actions depending on game system and tactical decision.
    """

    unit_name: str
    action_type: str  # "shoot", "charge", "hold", "fall_back", "advance"

    # Results of actions taken
    attack_results: list[AttackResult] = field(default_factory=list)
    melee_results: list[MeleeResult] = field(default_factory=list)
    morale_results: list[MoraleResult] = field(default_factory=list)

    # Movement
    moved: bool = False
    move_distance: float = 0.0
    new_position: str = ""  # Description or coordinates

    # Special actions
    special_actions: list[str] = field(default_factory=list)

    # Narrative (filled by narrator)
    narrative: str = ""

    @property
    def total_damage_dealt(self) -> int:
        """Sum of all damage dealt this activation."""
        return sum(r.damage_dealt for r in self.attack_results)

    @property
    def total_kills(self) -> int:
        """Sum of all models killed this activation."""
        return sum(r.models_killed for r in self.attack_results)

    def summary(self) -> str:
        """Brief summary of the activation."""
        parts = [f"{self.unit_name}: {self.action_type}"]
        if self.attack_results:
            kills = self.total_kills
            parts.append(f"{kills} kills")
        if self.moved:
            parts.append(f"moved {self.move_distance}\"")
        return " - ".join(parts)


class DiceRoller:
    """
    High-quality dice roller with multiple modes.

    Supports automatic rolling, manual entry, or hybrid mode.
    Pass a seeded random.Random for deterministic tests.
    """

    def __init__(self, mode: RollingMode = RollingMode.AUTO,
                 rng: random.Random | None = None):
        """
        Initialize the dice roller.

        Args:
            mode: Rolling mode (AUTO, MANUAL, or HYBRID)
            rng: Injectable RNG; defaults to a fresh random.Random()
        """
        self.mode = mode
        self._rng = rng if rng is not None else random.Random()
        self._roll_history: deque[int] = deque(maxlen=100)
        self._manual_input_callback: callable | None = None

    def set_manual_callback(self, callback: callable) -> None:
        """
        Set callback for manual dice input.

        Args:
            callback: Function that takes (count, sides) and returns list[int]
        """
        self._manual_input_callback = callback

    def roll_d6(self) -> int:
        """Roll a single d6 with cryptographic randomness."""
        result = self._rng.randint(1, 6)
        self._roll_history.append(result)
        return result

    def roll_d10(self) -> int:
        """Roll a single d10."""
        result = self._rng.randint(1, 10)
        self._roll_history.append(result)
        return result

    def roll_d100(self) -> int:
        """Roll percentile dice (1-100)."""
        result = self._rng.randint(1, 100)
        self._roll_history.append(result)
        return result

    def roll_2d6(self) -> int:
        """Roll 2d6 and sum."""
        return self.roll_d6() + self.roll_d6()

    def roll_dice(self, count: int, sides: int = 6) -> list[int]:
        """
        Roll multiple dice.

        Args:
            count: Number of dice to roll
            sides: Number of sides per die (default d6)

        Returns:
            List of individual die results
        """
        if self.mode == RollingMode.MANUAL and self._manual_input_callback:
            return self._manual_input_callback(count, sides)

        results = [self._rng.randint(1, sides) for _ in range(count)]
        self._roll_history.extend(results)
        return results

    def roll_check(
        self, count: int, target: int, sides: int = 6
    ) -> list[DiceRoll]:
        """
        Roll multiple dice against a target number.

        Args:
            count: Number of dice to roll
            target: Target number to meet or exceed
            sides: Number of sides per die

        Returns:
            List of DiceRoll objects with success/failure
        """
        raw_results = self.roll_dice(count, sides)
        return [
            DiceRoll(
                die_type=sides,
                result=r,
                target=target,
                success=r >= target,
                critical=r == sides,
                fumble=r == 1,
            )
            for r in raw_results
        ]

    def roll_opposed(
        self, attacker_count: int, defender_count: int, sides: int = 6
    ) -> tuple[list[int], list[int]]:
        """
        Roll opposed dice pools.

        Args:
            attacker_count: Number of attacker dice
            defender_count: Number of defender dice
            sides: Number of sides per die

        Returns:
            Tuple of (attacker_rolls, defender_rolls)
        """
        attacker = self.roll_dice(attacker_count, sides)
        defender = self.roll_dice(defender_count, sides)
        return attacker, defender

    @property
    def recent_average(self) -> float:
        """Average of recent rolls (for statistics display)."""
        if not self._roll_history:
            return 0.0
        return sum(self._roll_history) / len(self._roll_history)

    @property
    def roll_count(self) -> int:
        """Total rolls in history buffer."""
        return len(self._roll_history)


class RulesEngine(ABC):
    """
    Abstract base class for game system rules engines.

    Each concrete implementation handles the specific mechanics
    of a game system: dice resolution, wound charts, saves, etc.
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """
        Initialize the rules engine.

        Args:
            dice_roller: DiceRoller instance (creates one if not provided)
        """
        self.dice = dice_roller or DiceRoller()

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Human-readable name of the game system."""
        ...

    @property
    @abstractmethod
    def system_id(self) -> str:
        """Machine-readable identifier for the game system."""
        ...

    @abstractmethod
    def resolve_shooting(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Resolve a shooting attack.

        Args:
            attacker: The attacking unit
            target: The target unit
            weapon: Weapon profile dict
            modifiers: Optional situational modifiers

        Returns:
            AttackResult with all dice and outcomes
        """
        ...

    @abstractmethod
    def resolve_melee(
        self,
        attacker: RosterUnit,
        defender: RosterUnit,
        modifiers: dict[str, int] | None = None,
    ) -> MeleeResult:
        """
        Resolve melee combat between two units.

        Args:
            attacker: The charging/attacking unit
            defender: The defending unit
            modifiers: Optional situational modifiers

        Returns:
            MeleeResult with attack results from both sides
        """
        ...

    @abstractmethod
    def check_morale(
        self,
        unit: RosterUnit,
        casualties: int,
        test_type: str = "break",
        modifiers: dict[str, int] | None = None,
    ) -> MoraleResult:
        """
        Check unit morale after taking casualties or other triggers.

        Args:
            unit: The unit taking the morale check
            casualties: Number of casualties suffered
            test_type: Type of morale test
            modifiers: Optional situational modifiers

        Returns:
            MoraleResult with pass/fail and consequences
        """
        ...

    def get_to_hit(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        is_melee: bool = False,
    ) -> int:
        """
        Calculate the to-hit target number.

        Default implementation - override for system-specific charts.

        Args:
            attacker: Attacking unit
            target: Target unit
            weapon: Weapon being used
            is_melee: True for melee, False for shooting

        Returns:
            Target number needed on d6
        """
        # Default: use BS for shooting, WS for melee
        if is_melee:
            ws = attacker.get_stat("WS", 3)
            return max(2, min(6, 7 - ws))  # Simple conversion
        else:
            bs = attacker.get_stat("BS", 3)
            return max(2, min(6, 7 - bs))

    def get_to_wound(
        self,
        strength: int,
        toughness: int,
    ) -> int:
        """
        Calculate the to-wound target number.

        Default implementation uses standard S vs T chart.

        Args:
            strength: Attacker's strength
            toughness: Defender's toughness

        Returns:
            Target number needed on d6
        """
        diff = strength - toughness
        if diff >= 2:
            return 2
        elif diff == 1:
            return 3
        elif diff == 0:
            return 4
        elif diff == -1:
            return 5
        else:
            return 6

    def get_armor_save(
        self,
        target: RosterUnit,
        strength: int,
        ap: int = 0,
    ) -> int | None:
        """
        Calculate armor save target or None if no save allowed.

        Default implementation - override for system-specific rules.

        Args:
            target: Unit making the save
            strength: Strength of the attack
            ap: Armor piercing value

        Returns:
            Target number needed on d6, or None if no save
        """
        base_save = target.get_stat("Sv", 7)  # 7+ means no save
        modified = base_save + ap
        if modified > 6:
            return None
        return max(2, modified)  # Can't be better than 2+


# Singleton dice roller for convenience
_default_roller = DiceRoller()


def get_default_roller() -> DiceRoller:
    """Get the default shared dice roller."""
    return _default_roller


def roll_d6() -> int:
    """Convenience function to roll a d6."""
    return _default_roller.roll_d6()


def roll_dice(count: int, sides: int = 6) -> list[int]:
    """Convenience function to roll multiple dice."""
    return _default_roller.roll_dice(count, sides)
