"""
Battle Coordination Module

Orchestrates player vs AI interactions, maintains battle state,
and logs the narrative history of the battle.

Components:
- BattleCoordinator: Main orchestration class
- BattleState: Current state of the battle
- BattleLog: Narrative history with dice breakdowns
"""

from __future__ import annotations

from .coordinator import (
    BattlePhase,
    BattleOutcome,
    BattleLogEntry,
    BattleState,
    BattleLog,
    BattleCoordinator,
)

__all__ = [
    "BattlePhase",
    "BattleOutcome",
    "BattleLogEntry",
    "BattleState",
    "BattleLog",
    "BattleCoordinator",
]
