"""
Wargame Rules Engines

Abstract base classes and concrete implementations for different
game systems. Each engine knows how to resolve attacks, check morale,
and apply game-specific rules.

Available Engines:
- OldhammerRulesEngine: Warhammer 40K 2nd Edition
- OldWorldRulesEngine: Warhammer: The Old World
- OPRRulesEngine: OnePageRules (Grimdark Future, Age of Fantasy)
- TrenchCrusadeEngine: Trench Crusade (WWI horror skirmish)
"""

from __future__ import annotations

from .base import (
    DiceRoll,
    DiceRoller,
    AttackResult,
    MeleeResult,
    ActivationResult,
    MoraleResult,
    RulesEngine,
    RollingMode,
    get_default_roller,
    roll_d6,
    roll_dice,
)

from .oldhammer import OldhammerRulesEngine, SustainedFireResult, GetsHotResult
from .opr import OPRRulesEngine, SpecialRule
from .old_world import OldWorldRulesEngine, CombatResolution
from .trench_crusade import TrenchCrusadeEngine, TrenchCrusadeResult, TCDiceResult

__all__ = [
    # Base classes
    "DiceRoll",
    "DiceRoller",
    "AttackResult",
    "MeleeResult",
    "ActivationResult",
    "MoraleResult",
    "RulesEngine",
    "RollingMode",
    "get_default_roller",
    "roll_d6",
    "roll_dice",
    # Oldhammer
    "OldhammerRulesEngine",
    "SustainedFireResult",
    "GetsHotResult",
    # OPR
    "OPRRulesEngine",
    "SpecialRule",
    # Old World
    "OldWorldRulesEngine",
    "CombatResolution",
    # Trench Crusade
    "TrenchCrusadeEngine",
    "TrenchCrusadeResult",
    "TCDiceResult",
]
