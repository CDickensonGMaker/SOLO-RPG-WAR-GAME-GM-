"""
Domain Turn Controller - Manages the flow of domain turns in campaigns.

Handles:
- Turn phase management
- Random event generation
- NPC AI simulation
- Auto-save logic
"""

from typing import List, Optional, Callable
import random
from pathlib import Path

from oracle.gui.models.campaign import (
    CampaignState, DomainEvent, EventChoice, TurnState, Season, EventSeverity
)
from oracle.gui.models.game_state import GameState
from oracle.gui.config import config, SAVES_PATH


class DomainTurnController:
    """
    Controls the flow of domain turns.

    A domain turn represents one season of game time during which:
    1. Random events may occur
    2. Story events trigger based on conditions
    3. The player takes domain actions
    4. NPCs react and take their own actions
    """

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self._event_callbacks: List[Callable] = []
        self._turn_callbacks: List[Callable] = []

    @property
    def campaign(self) -> Optional[CampaignState]:
        """Get the active campaign."""
        return self.game_state.active_campaign

    def on_event(self, callback: Callable):
        """Register callback for when events trigger."""
        self._event_callbacks.append(callback)

    def on_turn_advance(self, callback: Callable):
        """Register callback for turn advancement."""
        self._turn_callbacks.append(callback)

    def _notify_event(self, event: DomainEvent):
        """Notify listeners of a new event."""
        for callback in self._event_callbacks:
            callback(event)

    def _notify_turn_advance(self, turn: TurnState):
        """Notify listeners of turn advancement."""
        for callback in self._turn_callbacks:
            callback(turn)

    def start_turn(self) -> List[DomainEvent]:
        """
        Start a new turn, returning events that trigger.

        This is the main turn initiation method. It:
        1. Checks for mandatory story events
        2. Rolls for random events
        3. Returns all triggered events for the player to handle
        """
        if not self.campaign:
            return []

        events = []

        # Get available events for this turn
        available = self.campaign.get_available_events()

        # Mandatory events first
        mandatory = [e for e in available if e.mandatory]
        events.extend(mandatory)

        # Then conditional events that trigger
        conditional = [e for e in available if not e.mandatory and e.event_type == "conditional"]
        events.extend(conditional)

        # Random event check
        if not self.campaign.turn.random_event_occurred:
            random_event = self._check_random_event()
            if random_event:
                events.append(random_event)
                self.campaign.turn.random_event_occurred = True

        # Set the first event as pending if any
        if events and not self.campaign.pending_event:
            self.campaign.pending_event = events[0]
            self._notify_event(events[0])

        return events

    def _check_random_event(self) -> Optional[DomainEvent]:
        """Check for and generate random events."""
        base_chance = config.game.random_event_chance
        chaos_modifier = config.game.chaos_event_modifier * self.campaign.chaos_factor

        roll = random.randint(1, 100)

        if roll <= base_chance + chaos_modifier:
            return self._generate_random_event()

        return None

    def _generate_random_event(self) -> DomainEvent:
        """Generate a random event appropriate to the current act."""
        # Random event templates based on campaign themes
        event_templates = {
            "iron_throne": [
                ("diplomatic_overture", "A foreign emissary requests audience"),
                ("court_rumor", "Troubling whispers spread through the court"),
                ("border_skirmish", "Raiders test your borders"),
                ("trade_dispute", "Merchants demand resolution of grievances"),
            ],
            "gorgons_shadow": [
                ("monster_sighting", "Something unnatural has been spotted"),
                ("military_buildup", "Enemy forces are massing"),
                ("refugee_crisis", "Displaced civilians seek shelter"),
                ("supply_shortage", "Military supplies are running low"),
            ],
            "web_of_shadows": [
                ("assassination_plot", "Intelligence suggests a plot against you"),
                ("double_agent", "One of your agents may be compromised"),
                ("information_leak", "Sensitive information has been exposed"),
                ("network_opportunity", "A potential new informant emerges"),
            ],
            "sources_of_power": [
                ("magical_anomaly", "Strange magical phenomena occur"),
                ("source_fluctuation", "A source behaves erratically"),
                ("corrupted_creature", "A magic-warped creature appears"),
                ("vision", "A cryptic vision disturbs your sleep"),
            ],
            "cerilian_alliance": [
                ("alliance_tension", "Friction between allies requires mediation"),
                ("front_development", "News arrives from a distant front"),
                ("supply_chain", "Logistics require attention"),
                ("diplomatic_incident", "A misunderstanding threatens cooperation"),
            ],
            "chosen_bloodline": [
                ("bloodline_surge", "Your blood awakens with new intensity"),
                ("divine_sign", "A portent appears in the sky"),
                ("rival_movement", "Your rival has made a move"),
                ("herald_message", "The Herald brings cryptic guidance"),
            ]
        }

        campaign_id = self.campaign.campaign_id
        templates = event_templates.get(campaign_id, event_templates["iron_throne"])

        event_id, event_name = random.choice(templates)

        return DomainEvent(
            id=f"random_{event_id}_{self.campaign.turn.turn_number}",
            name=event_name,
            description=f"Random event: {event_name}. The Oracle should determine specifics.",
            act=self.campaign.current_act,
            turn=self.campaign.turn.turn_number,
            event_type="random",
            mandatory=False,
            choices=[
                EventChoice(
                    id="investigate",
                    text="Investigate this matter personally",
                    oracle_prompt="What do you discover when investigating?"
                ),
                EventChoice(
                    id="delegate",
                    text="Delegate to a trusted subordinate",
                    oracle_prompt="How well does your subordinate handle this?"
                ),
                EventChoice(
                    id="ignore",
                    text="Focus on more pressing matters",
                    oracle_prompt="Does ignoring this have consequences?"
                )
            ],
            severity=EventSeverity.MINOR
        )

    def resolve_event_choice(self, event: DomainEvent, choice_id: str,
                             outcome: str = ""):
        """
        Resolve a player's choice for an event.

        Args:
            event: The event being resolved
            choice_id: ID of the chosen option
            outcome: Description of the outcome (from Oracle or narration)
        """
        if not self.campaign:
            return

        # Find the choice
        choice = next((c for c in event.choices if c.id == choice_id), None)
        if not choice:
            return

        # Apply effects
        self.campaign.apply_effects(choice.effects)

        # Record resolution
        self.campaign.resolve_event(event, choice_id, outcome)

        # Check if this advances the act
        self._check_act_completion()

        # Check for victory/failure
        self._check_campaign_completion()

        # Move to next pending event if any
        available = self.campaign.get_available_events()
        if available:
            self.campaign.pending_event = available[0]
            self._notify_event(available[0])
        else:
            self.campaign.pending_event = None

    def take_domain_action(self, action_type: str, target: str = "",
                          cost_paid: bool = True) -> bool:
        """
        Process a domain action.

        Args:
            action_type: Type of domain action (e.g., "diplomacy", "espionage")
            target: Target of the action
            cost_paid: Whether costs have been paid

        Returns:
            True if action was successfully taken
        """
        if not self.campaign:
            return False

        if self.campaign.turn.actions_remaining <= 0:
            return False

        # Deduct action
        self.campaign.turn.actions_remaining -= 1

        # Record action
        self.campaign.turn.events_this_turn.append(
            f"{action_type}:{target}"
        )

        return True

    def advance_turn(self) -> TurnState:
        """
        Advance to the next turn.

        This should be called after all events are resolved and actions taken.
        Handles:
        - NPC reactions
        - Turn state advancement
        - Auto-save
        """
        if not self.campaign:
            return None

        # Process NPC AI (simplified - would integrate with full NPC system)
        self._process_npc_reactions()

        # Advance turn state
        old_turn = self.campaign.turn
        self.campaign.turn = old_turn.advance()

        # Notify listeners
        self._notify_turn_advance(self.campaign.turn)

        # Auto-save
        if config.game.auto_save:
            if self.campaign.turn.turn_number % config.game.auto_save_turns == 0:
                self.game_state.save_all("autosave")

        return self.campaign.turn

    def _process_npc_reactions(self):
        """Process NPC AI reactions to player actions."""
        if not self.campaign:
            return

        # Simplified NPC reactions
        # In full implementation, would use oracle + NPC personality
        for rel in self.campaign.relationships.values():
            # Random disposition drift
            if random.random() < 0.1:  # 10% chance of shift
                drift = random.randint(-2, 2)
                if rel.disposition > 0:
                    drift -= 1  # Friendships decay slightly
                else:
                    drift += 1  # Hostility fades slightly
                rel.modify(drift, "Natural drift")

    def _check_act_completion(self):
        """Check if current act objectives are complete."""
        if not self.campaign:
            return

        # Would check campaign-specific objectives
        # For now, check if we've passed the act's turn range
        pass

    def _check_campaign_completion(self):
        """Check victory/failure conditions."""
        if not self.campaign:
            return

        # Check failure conditions first
        variables = self.campaign.variables

        # Generic checks (specific ones would come from campaign data)
        if variables.get("player_provinces", 1) <= 0:
            self.campaign.failure_occurred = "domain_loss"

        if variables.get("player_killed"):
            self.campaign.failure_occurred = "death"

        # Victory would be checked against campaign-specific conditions

    def get_turn_summary(self) -> dict:
        """Get a summary of the current turn state."""
        if not self.campaign:
            return {}

        return {
            "turn_number": self.campaign.turn.turn_number,
            "year": self.campaign.turn.year,
            "season": self.campaign.turn.season.value,
            "actions_remaining": self.campaign.turn.actions_remaining,
            "pending_events": len(self.campaign.get_available_events()),
            "has_pending_event": self.campaign.pending_event is not None,
            "chaos_factor": self.campaign.chaos_factor
        }

    def get_season_modifiers(self) -> dict:
        """Get modifiers for the current season."""
        season = self.campaign.turn.season if self.campaign else Season.SPRING

        modifiers = {
            Season.SPRING: {"trade": 1.1, "description": "Trade routes open, new beginnings"},
            Season.SUMMER: {"war": 1.2, "description": "Campaign season, war flourishes"},
            Season.AUTUMN: {"harvest": 1.3, "description": "Harvest time, wealth flows"},
            Season.WINTER: {"defense": 1.1, "movement": 0.8, "description": "Harsh conditions limit action"}
        }

        return modifiers.get(season, {})
