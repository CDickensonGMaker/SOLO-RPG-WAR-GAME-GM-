"""
Campaign State Models - Core data structures for campaign management.

These models track the state of a running campaign including:
- Turn and phase tracking
- Event queues and history
- NPC relationships
- Domain state
- Victory/failure conditions
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from pathlib import Path
import json


class Season(Enum):
    """Cerilian seasons."""
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

    def next(self) -> "Season":
        """Get the next season."""
        order = [Season.SPRING, Season.SUMMER, Season.AUTUMN, Season.WINTER]
        idx = order.index(self)
        return order[(idx + 1) % 4]


class EventSeverity(Enum):
    """Event importance levels."""
    FLAVOR = "flavor"       # Minor color events
    MINOR = "minor"         # Small impact
    MODERATE = "moderate"   # Significant impact
    MAJOR = "major"         # Campaign-altering
    CRITICAL = "critical"   # Victory/defeat potential


class RelationshipType(Enum):
    """NPC relationship categories."""
    ENEMY = "enemy"         # -100 to -41
    HOSTILE = "hostile"     # -40 to -21
    UNFRIENDLY = "unfriendly"  # -20 to -1
    NEUTRAL = "neutral"     # 0
    FRIENDLY = "friendly"   # 1 to 20
    ALLY = "ally"           # 21 to 40
    DEVOTED = "devoted"     # 41 to 100


@dataclass
class EventChoice:
    """A choice available for a campaign event."""
    id: str
    text: str
    effects: Dict[str, Any] = field(default_factory=dict)
    consequences: str = ""
    oracle_prompt: str = ""
    prerequisites: List[str] = field(default_factory=list)
    difficulty: str = "normal"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventChoice":
        """Create from dictionary."""
        return cls(
            id=data.get("id", "unknown"),
            text=data.get("text", ""),
            effects=data.get("effects", {}),
            consequences=data.get("consequences", ""),
            oracle_prompt=data.get("oracle_prompt", ""),
            prerequisites=data.get("prerequisites", []),
            difficulty=data.get("difficulty", "normal")
        )


@dataclass
class DomainEvent:
    """A campaign event requiring player response."""
    id: str
    name: str
    description: str
    act: int
    turn: Optional[int] = None
    turn_range: Optional[List[int]] = None
    event_type: str = "story"  # story, conditional, random
    mandatory: bool = False
    trigger: Optional[str] = None
    choices: List[EventChoice] = field(default_factory=list)
    severity: EventSeverity = EventSeverity.MODERATE
    resolved: bool = False
    choice_made: Optional[str] = None
    outcome: Optional[str] = None

    @classmethod
    def from_dict(cls, event_id: str, data: Dict[str, Any]) -> "DomainEvent":
        """Create from TOML event dictionary."""
        choices = []
        if "choices" in data:
            for choice_data in data["choices"]:
                choices.append(EventChoice.from_dict(choice_data))

        return cls(
            id=event_id,
            name=data.get("name", event_id),
            description=data.get("description", {}).get("text", ""),
            act=data.get("act", 1),
            turn=data.get("turn"),
            turn_range=data.get("turn_range"),
            event_type=data.get("type", "story"),
            mandatory=data.get("mandatory", False),
            trigger=data.get("trigger"),
            choices=choices,
            severity=EventSeverity(data.get("severity", "moderate"))
        )

    def is_available(self, turn: int, variables: Dict[str, Any]) -> bool:
        """Check if event should trigger on given turn."""
        if self.resolved:
            return False

        # Check turn timing
        if self.turn is not None:
            if turn != self.turn:
                return False
        elif self.turn_range is not None:
            if not (self.turn_range[0] <= turn <= self.turn_range[1]):
                return False

        # Check trigger condition
        if self.trigger and self.event_type == "conditional":
            # Simple trigger evaluation
            return self._evaluate_trigger(self.trigger, variables)

        return True

    def _evaluate_trigger(self, trigger: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a trigger condition string."""
        # Support simple comparisons like "player_visibility >= 15"
        try:
            # Parse operators
            for op in [">=", "<=", "==", "!=", ">", "<"]:
                if op in trigger:
                    parts = trigger.split(op)
                    if len(parts) == 2:
                        var_name = parts[0].strip()
                        value = int(parts[1].strip())
                        var_value = variables.get(var_name, 0)

                        if op == ">=":
                            return var_value >= value
                        elif op == "<=":
                            return var_value <= value
                        elif op == "==":
                            return var_value == value
                        elif op == "!=":
                            return var_value != value
                        elif op == ">":
                            return var_value > value
                        elif op == "<":
                            return var_value < value
        except (ValueError, TypeError):
            pass
        return False


@dataclass
class Relationship:
    """Tracks relationship with an NPC."""
    npc_id: str
    npc_name: str
    disposition: int = 0  # -100 to +100
    known: bool = True
    met: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def relationship_type(self) -> RelationshipType:
        """Get relationship category from disposition."""
        if self.disposition <= -41:
            return RelationshipType.ENEMY
        elif self.disposition <= -21:
            return RelationshipType.HOSTILE
        elif self.disposition < 0:
            return RelationshipType.UNFRIENDLY
        elif self.disposition == 0:
            return RelationshipType.NEUTRAL
        elif self.disposition <= 20:
            return RelationshipType.FRIENDLY
        elif self.disposition <= 40:
            return RelationshipType.ALLY
        else:
            return RelationshipType.DEVOTED

    def modify(self, amount: int, reason: str = ""):
        """Modify disposition with bounds checking."""
        self.disposition = max(-100, min(100, self.disposition + amount))
        if reason:
            self.notes.append(f"[{amount:+d}] {reason}")


@dataclass
class TurnState:
    """State of the current domain turn."""
    turn_number: int
    year: int
    season: Season
    actions_remaining: int = 3
    events_this_turn: List[str] = field(default_factory=list)
    random_event_occurred: bool = False

    def advance(self) -> "TurnState":
        """Advance to next turn."""
        new_season = self.season.next()
        new_year = self.year + 1 if new_season == Season.SPRING else self.year

        return TurnState(
            turn_number=self.turn_number + 1,
            year=new_year,
            season=new_season,
            actions_remaining=3,
            events_this_turn=[],
            random_event_occurred=False
        )


@dataclass
class CampaignState:
    """Complete state of a running campaign."""
    campaign_id: str
    campaign_name: str
    character_id: str
    character_name: str

    # Progress tracking
    current_act: int = 1
    turn: TurnState = None
    started_at: str = ""
    last_saved: str = ""

    # Event management
    event_queue: List[DomainEvent] = field(default_factory=list)
    event_history: List[Dict[str, Any]] = field(default_factory=list)
    pending_event: Optional[DomainEvent] = None

    # NPC relationships
    relationships: Dict[str, Relationship] = field(default_factory=dict)

    # Campaign variables
    variables: Dict[str, Any] = field(default_factory=dict)

    # Victory/failure tracking
    objectives_complete: List[str] = field(default_factory=list)
    victory_achieved: Optional[str] = None
    failure_occurred: Optional[str] = None

    # Oracle integration
    chaos_factor: int = 5

    def __post_init__(self):
        """Initialize defaults after construction."""
        if self.turn is None:
            self.turn = TurnState(
                turn_number=1,
                year=551,
                season=Season.SPRING
            )
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    @classmethod
    def new_campaign(cls, campaign_id: str, campaign_name: str,
                     character_id: str, character_name: str,
                     starting_year: int = 551,
                     starting_season: str = "spring") -> "CampaignState":
        """Create a new campaign state."""
        season = Season(starting_season.lower())
        turn = TurnState(
            turn_number=1,
            year=starting_year,
            season=season
        )

        return cls(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            character_id=character_id,
            character_name=character_name,
            turn=turn,
            started_at=datetime.now().isoformat()
        )

    def add_event(self, event: DomainEvent):
        """Add event to queue."""
        self.event_queue.append(event)

    def resolve_event(self, event: DomainEvent, choice_id: str, outcome: str):
        """Record event resolution."""
        event.resolved = True
        event.choice_made = choice_id
        event.outcome = outcome

        self.event_history.append({
            "event_id": event.id,
            "event_name": event.name,
            "turn": self.turn.turn_number,
            "choice": choice_id,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat()
        })

        # Remove from queue
        self.event_queue = [e for e in self.event_queue if e.id != event.id]
        self.pending_event = None

    def apply_effects(self, effects: Dict[str, Any]):
        """Apply effect dictionary to campaign state."""
        for key, value in effects.items():
            if key.endswith("_disposition"):
                # NPC disposition change
                npc_id = key.replace("_disposition", "")
                if npc_id in self.relationships:
                    self.relationships[npc_id].modify(value)
            else:
                # Variable change
                if isinstance(value, int) and key in self.variables:
                    self.variables[key] = self.variables.get(key, 0) + value
                else:
                    self.variables[key] = value

    def check_completion(self) -> bool:
        """Check if campaign has ended."""
        return self.victory_achieved is not None or self.failure_occurred is not None

    def get_available_events(self) -> List[DomainEvent]:
        """Get events available this turn."""
        return [
            e for e in self.event_queue
            if e.is_available(self.turn.turn_number, self.variables)
        ]

    def save(self, path: Path) -> bool:
        """Save campaign state to file."""
        try:
            self.last_saved = datetime.now().isoformat()
            data = self._to_dict()
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except (IOError, TypeError) as e:
            print(f"Save failed: {e}")
            return False

    @classmethod
    def load(cls, path: Path) -> Optional["CampaignState"]:
        """Load campaign state from file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return cls._from_dict(data)
        except (IOError, json.JSONDecodeError, KeyError) as e:
            print(f"Load failed: {e}")
            return None

    def _to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "current_act": self.current_act,
            "turn": {
                "turn_number": self.turn.turn_number,
                "year": self.turn.year,
                "season": self.turn.season.value,
                "actions_remaining": self.turn.actions_remaining,
            },
            "started_at": self.started_at,
            "last_saved": self.last_saved,
            "event_history": self.event_history,
            "relationships": {
                npc_id: {
                    "npc_id": rel.npc_id,
                    "npc_name": rel.npc_name,
                    "disposition": rel.disposition,
                    "known": rel.known,
                    "met": rel.met,
                    "notes": rel.notes
                }
                for npc_id, rel in self.relationships.items()
            },
            "variables": self.variables,
            "objectives_complete": self.objectives_complete,
            "victory_achieved": self.victory_achieved,
            "failure_occurred": self.failure_occurred,
            "chaos_factor": self.chaos_factor
        }

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "CampaignState":
        """Create from dictionary."""
        turn_data = data.get("turn", {})
        turn = TurnState(
            turn_number=turn_data.get("turn_number", 1),
            year=turn_data.get("year", 551),
            season=Season(turn_data.get("season", "spring")),
            actions_remaining=turn_data.get("actions_remaining", 3)
        )

        relationships = {}
        for npc_id, rel_data in data.get("relationships", {}).items():
            relationships[npc_id] = Relationship(
                npc_id=rel_data.get("npc_id", npc_id),
                npc_name=rel_data.get("npc_name", npc_id),
                disposition=rel_data.get("disposition", 0),
                known=rel_data.get("known", True),
                met=rel_data.get("met", False),
                notes=rel_data.get("notes", [])
            )

        return cls(
            campaign_id=data.get("campaign_id", ""),
            campaign_name=data.get("campaign_name", ""),
            character_id=data.get("character_id", ""),
            character_name=data.get("character_name", ""),
            current_act=data.get("current_act", 1),
            turn=turn,
            started_at=data.get("started_at", ""),
            last_saved=data.get("last_saved", ""),
            event_history=data.get("event_history", []),
            relationships=relationships,
            variables=data.get("variables", {}),
            objectives_complete=data.get("objectives_complete", []),
            victory_achieved=data.get("victory_achieved"),
            failure_occurred=data.get("failure_occurred"),
            chaos_factor=data.get("chaos_factor", 5)
        )
