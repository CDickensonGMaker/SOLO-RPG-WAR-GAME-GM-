"""
Oracle Wargame Package

A rules-based wargaming system with AI opponent capabilities.
Supports multiple game systems: Oldhammer 2E, Old World, OPR, Trench Crusade.

Subpackages:
- engine: Rules engines for different game systems
- ai: AI opponent and tactical decision making
- battle: Battle coordination and state management
- data: TOML data files for charts and rules

Quick Start:
    from oracle.wargame import OldhammerRulesEngine, BattleCoordinator
    from oracle.wargame import generate_commander, OpponentAI

    # Create rules engine and commander
    rules = OldhammerRulesEngine()
    commander = generate_commander("aggressive_blitzer")

    # Set up battle
    coordinator = BattleCoordinator(
        rules_engine=rules,
        player_roster=player_army,
        ai_roster=enemy_army,
        commander=commander,
    )

    # Run battle
    coordinator.start_battle()
    result, narrative = coordinator.player_declares_attack(unit, target, weapon)
    ai_actions, ai_narrative = coordinator.opponent_takes_turn()
"""

from __future__ import annotations

__version__ = "0.1.0"

# Import from subpackages for convenient access
from .engine import (
    # Base
    DiceRoll,
    DiceRoller,
    AttackResult,
    MeleeResult,
    MoraleResult,
    RulesEngine,
    RollingMode,
    # Engines
    OldhammerRulesEngine,
    OPRRulesEngine,
    OldWorldRulesEngine,
    TrenchCrusadeEngine,
)

from .ai import (
    # Tactical
    Aggression,
    Doctrine,
    ThreatLevel,
    ThreatAssessment,
    TacticalOption,
    TacticalDecision,
    WargameAI,
    # Commander
    CommanderArchetype,
    CommanderPersonality,
    BattleNarrator,
    generate_commander,
    # Opponent
    OpponentAI,
    AIActivation,
    # Narrator
    EnhancedNarrator,
)

# Backward-compatible module-level functions
from .ai.tactical import (
    decide,
    analyze,
    roll_event,
    roll_priority,
    roll_morale,
    set_doctrine,
    set_aggression,
    render,
    THREAT_KEYWORDS,
    BATTLE_EVENTS,
    BASE_OPTIONS,
)

from .battle import (
    BattlePhase,
    BattleOutcome,
    BattleState,
    BattleLog,
    BattleCoordinator,
)

__all__ = [
    # Version
    "__version__",
    # Engine
    "DiceRoll",
    "DiceRoller",
    "AttackResult",
    "MeleeResult",
    "MoraleResult",
    "RulesEngine",
    "RollingMode",
    "OldhammerRulesEngine",
    "OPRRulesEngine",
    "OldWorldRulesEngine",
    "TrenchCrusadeEngine",
    # AI - Tactical
    "Aggression",
    "Doctrine",
    "ThreatLevel",
    "ThreatAssessment",
    "TacticalOption",
    "TacticalDecision",
    "WargameAI",
    # AI - Commander
    "CommanderArchetype",
    "CommanderPersonality",
    "BattleNarrator",
    "generate_commander",
    # AI - Opponent
    "OpponentAI",
    "AIActivation",
    "EnhancedNarrator",
    # Battle
    "BattlePhase",
    "BattleOutcome",
    "BattleState",
    "BattleLog",
    "BattleCoordinator",
    # Backward-compatible module-level functions
    "decide",
    "analyze",
    "roll_event",
    "roll_priority",
    "roll_morale",
    "set_doctrine",
    "set_aggression",
    "render",
    "THREAT_KEYWORDS",
    "BATTLE_EVENTS",
    "BASE_OPTIONS",
]
