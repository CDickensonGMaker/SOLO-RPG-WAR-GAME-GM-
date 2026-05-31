"""
Event Handler - Processes campaign events and integrates with Oracle system.

Handles:
- Loading events from TOML campaign files
- Processing player choices
- Oracle roll integration for outcomes
- Applying consequences to campaign state
"""

from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
import tomllib
import random

from oracle.gui.models.campaign import (
    DomainEvent, EventChoice, CampaignState, EventSeverity
)
from oracle.gui.config import CAMPAIGNS_PATH


class EventHandler:
    """
    Handles campaign event processing and Oracle integration.

    Events are the core narrative mechanic - situations that arise
    during a campaign that require player decisions. Each event has:
    - A description of the situation
    - Multiple choices with different consequences
    - Oracle prompts for outcome resolution
    """

    def __init__(self, campaign_state: CampaignState):
        self.campaign = campaign_state
        self._oracle = None  # Will be set when oracle module is available
        self._event_data: Dict[str, Dict] = {}
        self._load_campaign_events()

        # Callbacks
        self._on_event_resolved: List[Callable] = []
        self._on_oracle_roll: List[Callable] = []

    def _load_campaign_events(self):
        """Load events from campaign TOML file."""
        path = CAMPAIGNS_PATH / f"{self.campaign.campaign_id}.toml"
        if not path.exists():
            return

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            self._event_data = data.get("events", {})
        except tomllib.TOMLDecodeError:
            pass

    def on_event_resolved(self, callback: Callable):
        """Register callback for event resolution."""
        self._on_event_resolved.append(callback)

    def on_oracle_roll(self, callback: Callable):
        """Register callback for oracle rolls."""
        self._on_oracle_roll.append(callback)

    def get_event(self, event_id: str) -> Optional[DomainEvent]:
        """Get event by ID, checking both queue and raw data."""
        # Check campaign queue first
        for event in self.campaign.event_queue:
            if event.id == event_id:
                return event

        # Check raw data
        if event_id in self._event_data:
            return DomainEvent.from_dict(event_id, self._event_data[event_id])

        return None

    def get_available_choices(self, event: DomainEvent) -> List[EventChoice]:
        """Get choices available to the player for an event."""
        available = []

        for choice in event.choices:
            if self._check_prerequisites(choice.prerequisites):
                available.append(choice)

        return available

    def _check_prerequisites(self, prerequisites: List[str]) -> bool:
        """Check if prerequisites are met for a choice."""
        if not prerequisites:
            return True

        variables = self.campaign.variables

        for prereq in prerequisites:
            # Handle OR conditions
            if prereq == "or":
                continue  # OR is handled by the surrounding logic

            # Simple variable checks
            if ">=" in prereq:
                var, val = prereq.split(">=")
                if variables.get(var.strip(), 0) < int(val.strip()):
                    return False
            elif "<=" in prereq:
                var, val = prereq.split("<=")
                if variables.get(var.strip(), 0) > int(val.strip()):
                    return False
            elif "==" in prereq:
                var, val = prereq.split("==")
                if str(variables.get(var.strip(), "")) != val.strip():
                    return False
            else:
                # Boolean check
                if not variables.get(prereq, False):
                    return False

        return True

    def resolve_choice(self, event: DomainEvent, choice: EventChoice,
                      oracle_result: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolve a player's choice for an event.

        Args:
            event: The event being resolved
            choice: The chosen option
            oracle_result: Result from Oracle roll (if applicable)

        Returns:
            Dictionary with resolution details
        """
        result = {
            "event_id": event.id,
            "event_name": event.name,
            "choice_id": choice.id,
            "choice_text": choice.text,
            "effects_applied": {},
            "oracle_prompt": choice.oracle_prompt,
            "oracle_result": oracle_result,
            "consequences": choice.consequences,
            "narrative": ""
        }

        # Apply effects
        effects = choice.effects.copy()

        # Modify effects based on difficulty
        if choice.difficulty == "hard":
            # Hard choices have reduced positive effects
            for key, value in effects.items():
                if isinstance(value, int) and value > 0:
                    effects[key] = int(value * 0.7)

        # Apply to campaign state
        self.campaign.apply_effects(effects)
        result["effects_applied"] = effects

        # Generate narrative outcome
        result["narrative"] = self._generate_outcome_narrative(
            event, choice, oracle_result
        )

        # Record resolution
        self.campaign.resolve_event(
            event, choice.id,
            result["narrative"]
        )

        # Notify callbacks
        for callback in self._on_event_resolved:
            callback(result)

        return result

    def _generate_outcome_narrative(self, event: DomainEvent,
                                    choice: EventChoice,
                                    oracle_result: Optional[str]) -> str:
        """Generate narrative text for the outcome."""
        narrative_parts = []

        # Base consequence
        if choice.consequences:
            narrative_parts.append(choice.consequences)

        # Oracle interpretation
        if oracle_result:
            narrative_parts.append(f"Oracle says: {oracle_result}")

        # Effect summary
        effects_summary = []
        for key, value in choice.effects.items():
            if isinstance(value, int):
                if value > 0:
                    effects_summary.append(f"+{value} {key.replace('_', ' ')}")
                else:
                    effects_summary.append(f"{value} {key.replace('_', ' ')}")
            elif isinstance(value, bool):
                effects_summary.append(f"{key.replace('_', ' ')} {'enabled' if value else 'disabled'}")

        if effects_summary:
            narrative_parts.append(f"Effects: {', '.join(effects_summary)}")

        return "\n\n".join(narrative_parts)

    def roll_oracle(self, prompt: str, likelihood: str = "even") -> Dict[str, Any]:
        """
        Roll the Oracle for an outcome.

        This integrates with the Oracle system from oracle.fate module.

        Args:
            prompt: The question to ask the Oracle
            likelihood: One of "impossible", "unlikely", "even", "likely", "certain"

        Returns:
            Dictionary with roll result
        """
        # Map likelihood to numerical modifiers
        likelihood_map = {
            "impossible": -30,
            "unlikely": -15,
            "even": 0,
            "likely": 15,
            "certain": 30
        }

        modifier = likelihood_map.get(likelihood, 0)

        # Base roll
        roll = random.randint(1, 100)
        modified_roll = roll + modifier + (self.campaign.chaos_factor * 2)

        # Determine answer
        if modified_roll <= 15:
            answer = "no_and"
            answer_text = "NO, and..."
        elif modified_roll <= 35:
            answer = "no"
            answer_text = "NO"
        elif modified_roll <= 45:
            answer = "no_but"
            answer_text = "NO, but..."
        elif modified_roll <= 55:
            answer = "yes_but"
            answer_text = "YES, but..."
        elif modified_roll <= 85:
            answer = "yes"
            answer_text = "YES"
        else:
            answer = "yes_and"
            answer_text = "YES, and..."

        # Check for random event trigger
        random_event = roll <= 5 or roll >= 95

        result = {
            "prompt": prompt,
            "likelihood": likelihood,
            "roll": roll,
            "modifier": modifier,
            "modified_roll": modified_roll,
            "answer": answer,
            "answer_text": answer_text,
            "random_event_triggered": random_event,
            "chaos_factor": self.campaign.chaos_factor
        }

        # Notify callbacks
        for callback in self._on_oracle_roll:
            callback(result)

        return result

    def get_event_severity_color(self, severity: EventSeverity) -> tuple:
        """Get color for event severity display."""
        colors = {
            EventSeverity.FLAVOR: (0.5, 0.5, 0.5, 1.0),     # Gray
            EventSeverity.MINOR: (0.4, 0.6, 0.4, 1.0),      # Green
            EventSeverity.MODERATE: (0.7, 0.7, 0.3, 1.0),   # Yellow
            EventSeverity.MAJOR: (0.8, 0.5, 0.2, 1.0),      # Orange
            EventSeverity.CRITICAL: (0.8, 0.2, 0.2, 1.0),   # Red
        }
        return colors.get(severity, (0.5, 0.5, 0.5, 1.0))

    def format_event_for_display(self, event: DomainEvent) -> Dict[str, Any]:
        """Format event data for GUI display."""
        return {
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "act": event.act,
            "type": event.event_type,
            "severity": event.severity.value,
            "severity_color": self.get_event_severity_color(event.severity),
            "choices": [
                {
                    "id": c.id,
                    "text": c.text,
                    "consequences": c.consequences,
                    "difficulty": c.difficulty,
                    "has_oracle": bool(c.oracle_prompt),
                    "available": self._check_prerequisites(c.prerequisites)
                }
                for c in event.choices
            ],
            "resolved": event.resolved,
            "choice_made": event.choice_made,
            "outcome": event.outcome
        }
