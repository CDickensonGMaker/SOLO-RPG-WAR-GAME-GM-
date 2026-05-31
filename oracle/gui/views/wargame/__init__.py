"""
Wargame Views - UI components for wargame mode.

This package provides the complete wargame UI including:
- Game system and faction selection
- Army building with unit catalog
- Battle tracking with force displays
- Tactical AI integration
- Casualty and turn tracking
"""

from oracle.gui.views.wargame.game_selector import GameSelectorPanel
from oracle.gui.views.wargame.army_builder import ArmyBuilderPanel
from oracle.gui.views.wargame.unit_detail import UnitDetailPanel
from oracle.gui.views.wargame.force_display import ForceDisplayPanel, CompactForceDisplay
from oracle.gui.views.wargame.casualty_tracker import (
    CasualtyTracker,
    QuickCasualtyButtons,
)
from oracle.gui.views.wargame.turn_tracker import TurnTrackerPanel, CompactTurnDisplay, BattleEvent
from oracle.gui.views.wargame.tactical_panel import TacticalAIPanel
from oracle.gui.views.wargame.rules_browser import RulesBrowserPanel, CompactRulesSearch
from oracle.gui.views.wargame.battle_events import (
    BattleEventSystem,
    EventType,
    ConsequenceType,
    EventConsequence,
    get_event_system,
)
from oracle.gui.views.wargame.equipment_dialog import (
    EquipmentDialog,
    QuickEquipmentPanel,
)

__all__ = [
    # Setup
    "GameSelectorPanel",
    # Army Building
    "ArmyBuilderPanel",
    "UnitDetailPanel",
    # Battle Tracking
    "ForceDisplayPanel",
    "CompactForceDisplay",
    "CasualtyTracker",
    "QuickCasualtyButtons",
    "TurnTrackerPanel",
    "CompactTurnDisplay",
    "BattleEvent",
    # Tactical AI
    "TacticalAIPanel",
    # Rules Reference
    "RulesBrowserPanel",
    "CompactRulesSearch",
    # Battle Events
    "BattleEventSystem",
    "EventType",
    "ConsequenceType",
    "EventConsequence",
    "get_event_system",
    # Equipment
    "EquipmentDialog",
    "QuickEquipmentPanel",
]
