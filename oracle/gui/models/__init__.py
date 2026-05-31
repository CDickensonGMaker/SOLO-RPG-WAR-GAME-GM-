"""
Data Models - Core data structures for campaign and wargame state management.
"""

from oracle.gui.models.campaign import (
    CampaignState,
    DomainEvent,
    EventChoice,
    Relationship,
    TurnState
)
from oracle.gui.models.game_state import GameState
from oracle.gui.models.wargame_data import (
    WargameDataModel,
    SlotCategory,
    UnitCard,
    get_wargame_data,
)
from oracle.gui.models.roster_model import (
    BattleRosterModel,
    BattleState,
    get_battle_roster,
)

__all__ = [
    # Campaign
    "CampaignState",
    "DomainEvent",
    "EventChoice",
    "Relationship",
    "TurnState",
    "GameState",
    # Wargame
    "WargameDataModel",
    "SlotCategory",
    "UnitCard",
    "get_wargame_data",
    "BattleRosterModel",
    "BattleState",
    "get_battle_roster",
]
