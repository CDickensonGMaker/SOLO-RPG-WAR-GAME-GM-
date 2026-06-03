"""
Wargame AI Module

AI opponent system that actually plays the game using rules engines.
Includes personality-driven commanders and narrative generation.

Components:
- OpponentAI: Makes tactical decisions and executes game actions
- CommanderPersonality: Gives AI a face and voice
- BattleNarrator: Turns mechanical results into dramatic narrative
- EnhancedNarrator: Dice-aware narrator with detailed breakdowns
- WargameAI: Tactical analysis (legacy, tactical.py)
"""

from __future__ import annotations

from .tactical import (
    Aggression,
    Doctrine,
    ThreatLevel,
    ThreatAssessment,
    TacticalOption,
    TacticalDecision,
    WargameAI,
)

from .commander import (
    CommanderArchetype,
    CommanderPersonality,
    BattleNarrator,
    generate_commander,
)

from .opponent import (
    ActionType,
    TargetSelection,
    AIActivation,
    OpponentAI,
)

from .narrator import (
    NarrativeStyle,
    EnhancedNarrator,
)

__all__ = [
    # Tactical (legacy)
    "Aggression",
    "Doctrine",
    "ThreatLevel",
    "ThreatAssessment",
    "TacticalOption",
    "TacticalDecision",
    "WargameAI",
    # Commander
    "CommanderArchetype",
    "CommanderPersonality",
    "BattleNarrator",
    "generate_commander",
    # Opponent AI
    "ActionType",
    "TargetSelection",
    "AIActivation",
    "OpponentAI",
    # Narrator
    "NarrativeStyle",
    "EnhancedNarrator",
]
