"""
Battle Events System - Event generation with consequences.

Provides:
- Event type definitions
- Consequence mapping
- Effect application to units
- Integration with roster and turn tracking
"""

from typing import Callable, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import random

from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.roster import RosterUnit, UnitStatus


class EventType(Enum):
    """Categories of battle events."""
    MORALE = "morale"
    SUPPLY = "supply"
    WEATHER = "weather"
    REINFORCEMENT = "reinforcement"
    TERRAIN = "terrain"
    COMMAND = "command"
    COMBAT = "combat"
    SPECIAL = "special"


class ConsequenceType(Enum):
    """Types of consequences that can be applied."""
    MORALE_TEST = "morale_test"  # Unit must test morale
    WOUND = "wound"  # Unit takes wounds
    BUFF = "buff"  # Unit gains temporary bonus
    DEBUFF = "debuff"  # Unit gains temporary penalty
    STATUS_CHANGE = "status_change"  # Unit status changes
    RESUPPLY = "resupply"  # Ammunition/supply effect
    MOVEMENT = "movement"  # Movement restriction/bonus
    SHOOTING = "shooting"  # Shooting modifier
    NONE = "none"  # Narrative only, no mechanical effect


@dataclass
class EventConsequence:
    """A consequence that can be applied to units."""
    type: ConsequenceType
    description: str
    magnitude: int = 0  # e.g., -1 modifier, 1 wound, etc.
    duration: int = 1  # Turns the effect lasts
    target: str = "random"  # "random", "all", "friendly", "enemy", or unit name

    def apply_text(self) -> str:
        """Get human-readable description of the effect."""
        if self.type == ConsequenceType.MORALE_TEST:
            return f"Must test morale (modifier: {self.magnitude:+d})"
        elif self.type == ConsequenceType.WOUND:
            return f"Takes {self.magnitude} wound(s)"
        elif self.type == ConsequenceType.BUFF:
            return f"Gains +{self.magnitude} bonus for {self.duration} turn(s)"
        elif self.type == ConsequenceType.DEBUFF:
            return f"Suffers {self.magnitude} penalty for {self.duration} turn(s)"
        elif self.type == ConsequenceType.MOVEMENT:
            return f"Movement modified by {self.magnitude:+d}\" for {self.duration} turn(s)"
        elif self.type == ConsequenceType.SHOOTING:
            return f"Shooting modified by {self.magnitude:+d} for {self.duration} turn(s)"
        elif self.type == ConsequenceType.RESUPPLY:
            return "Check ammunition/supply status"
        elif self.type == ConsequenceType.STATUS_CHANGE:
            return self.description
        return self.description


@dataclass
class BattleEventTemplate:
    """Template for a battle event with possible consequences."""
    text: str
    event_type: EventType
    consequences: List[EventConsequence]
    weight: int = 10  # Higher = more likely to occur


# Event templates organized by type
EVENT_TEMPLATES = {
    EventType.MORALE: [
        BattleEventTemplate(
            "A unit wavers under the pressure of battle",
            EventType.MORALE,
            [EventConsequence(ConsequenceType.MORALE_TEST, "Morale test required", -1, 1, "random")],
        ),
        BattleEventTemplate(
            "Inspiring heroics boost nearby troops' spirits",
            EventType.MORALE,
            [EventConsequence(ConsequenceType.BUFF, "Morale bonus", 1, 2, "friendly")],
        ),
        BattleEventTemplate(
            "The enemy's resolve seems to crack",
            EventType.MORALE,
            [EventConsequence(ConsequenceType.MORALE_TEST, "Enemy morale test", 0, 1, "enemy")],
        ),
    ],
    EventType.SUPPLY: [
        BattleEventTemplate(
            "Ammunition running low - conserve fire",
            EventType.SUPPLY,
            [EventConsequence(ConsequenceType.SHOOTING, "Limited ammo", -1, 2, "random")],
        ),
        BattleEventTemplate(
            "Supply cache discovered!",
            EventType.SUPPLY,
            [EventConsequence(ConsequenceType.RESUPPLY, "Resupply available", 0, 1, "friendly")],
        ),
        BattleEventTemplate(
            "Enemy supply lines disrupted",
            EventType.SUPPLY,
            [EventConsequence(ConsequenceType.DEBUFF, "Supply issues", -1, 2, "enemy")],
        ),
    ],
    EventType.WEATHER: [
        BattleEventTemplate(
            "Fog rolls across the battlefield, reducing visibility",
            EventType.WEATHER,
            [EventConsequence(ConsequenceType.SHOOTING, "Reduced visibility", -1, 2, "all")],
        ),
        BattleEventTemplate(
            "The ground turns to mud, slowing movement",
            EventType.WEATHER,
            [EventConsequence(ConsequenceType.MOVEMENT, "Difficult terrain", -2, 2, "all")],
        ),
        BattleEventTemplate(
            "Weather clears - perfect conditions",
            EventType.WEATHER,
            [EventConsequence(ConsequenceType.NONE, "Clear conditions", 0, 0, "all")],
        ),
    ],
    EventType.TERRAIN: [
        BattleEventTemplate(
            "Unstable ground gives way!",
            EventType.TERRAIN,
            [EventConsequence(ConsequenceType.WOUND, "Terrain hazard", 1, 1, "random")],
        ),
        BattleEventTemplate(
            "Good defensive position identified",
            EventType.TERRAIN,
            [EventConsequence(ConsequenceType.BUFF, "Cover bonus", 1, 3, "friendly")],
        ),
        BattleEventTemplate(
            "Obstacle blocks line of sight",
            EventType.TERRAIN,
            [EventConsequence(ConsequenceType.NONE, "LOS blocked", 0, 1, "all")],
        ),
    ],
    EventType.COMMAND: [
        BattleEventTemplate(
            "Orders get confused in the chaos",
            EventType.COMMAND,
            [EventConsequence(ConsequenceType.DEBUFF, "Confused orders", -1, 1, "random")],
        ),
        BattleEventTemplate(
            "Commander rallies the troops",
            EventType.COMMAND,
            [EventConsequence(ConsequenceType.BUFF, "Inspired", 1, 2, "friendly")],
        ),
        BattleEventTemplate(
            "Enemy communications intercepted",
            EventType.COMMAND,
            [EventConsequence(ConsequenceType.BUFF, "Intel advantage", 1, 1, "friendly")],
        ),
    ],
    EventType.COMBAT: [
        BattleEventTemplate(
            "Stray fire hits an unexpected target",
            EventType.COMBAT,
            [EventConsequence(ConsequenceType.WOUND, "Stray shot", 1, 1, "random")],
        ),
        BattleEventTemplate(
            "Lucky hit scores critical damage",
            EventType.COMBAT,
            [EventConsequence(ConsequenceType.WOUND, "Critical hit", 2, 1, "enemy")],
        ),
        BattleEventTemplate(
            "Weapon malfunction!",
            EventType.COMBAT,
            [EventConsequence(ConsequenceType.SHOOTING, "Weapon jam", -2, 1, "random")],
        ),
    ],
    EventType.REINFORCEMENT: [
        BattleEventTemplate(
            "Reinforcements sighted on the horizon",
            EventType.REINFORCEMENT,
            [EventConsequence(ConsequenceType.NONE, "Reinforcements coming", 0, 0, "friendly")],
        ),
        BattleEventTemplate(
            "Enemy reserves commit to the battle",
            EventType.REINFORCEMENT,
            [EventConsequence(ConsequenceType.NONE, "Enemy reinforcements", 0, 0, "enemy")],
        ),
    ],
    EventType.SPECIAL: [
        BattleEventTemplate(
            "Supernatural phenomena disturb the battlefield",
            EventType.SPECIAL,
            [EventConsequence(ConsequenceType.MORALE_TEST, "Fear test", -1, 1, "all")],
        ),
        BattleEventTemplate(
            "Divine/unholy intervention!",
            EventType.SPECIAL,
            [
                EventConsequence(ConsequenceType.BUFF, "Blessing", 2, 1, "random"),
                EventConsequence(ConsequenceType.MORALE_TEST, "Awe", 0, 1, "all"),
            ],
        ),
    ],
}


class BattleEventSystem:
    """
    Manages battle event generation and consequence application.
    """

    def __init__(self):
        self._battle = get_battle_roster()
        self._rng = random.Random()
        self._active_effects: List[Tuple[EventConsequence, int]] = []  # (effect, turns_remaining)

    def generate_event(self, event_type: Optional[EventType] = None) -> Tuple[str, List[EventConsequence]]:
        """
        Generate a random battle event.

        Args:
            event_type: Optional specific event type, random if None

        Returns:
            Tuple of (event_text, list of consequences)
        """
        if event_type is None:
            event_type = self._rng.choice(list(EVENT_TEMPLATES.keys()))

        templates = EVENT_TEMPLATES.get(event_type, [])
        if not templates:
            return ("Nothing significant happens.", [])

        # Weighted random selection
        total_weight = sum(t.weight for t in templates)
        roll = self._rng.randint(1, total_weight)
        cumulative = 0
        selected = templates[0]
        for template in templates:
            cumulative += template.weight
            if roll <= cumulative:
                selected = template
                break

        return (selected.text, selected.consequences.copy())

    def apply_consequence(
        self,
        consequence: EventConsequence,
        target_unit: Optional[RosterUnit] = None,
    ) -> str:
        """
        Apply a consequence to the battlefield.

        Args:
            consequence: The consequence to apply
            target_unit: Specific unit target (uses consequence.target if None)

        Returns:
            Description of what happened
        """
        result_parts = []

        # Determine target(s)
        if target_unit:
            targets = [target_unit]
        elif consequence.target == "all":
            targets = list(self._battle.friendly_roster.units.values()) + \
                     list(self._battle.enemy_roster.units.values())
        elif consequence.target == "friendly":
            targets = list(self._battle.friendly_roster.units.values())
        elif consequence.target == "enemy":
            targets = list(self._battle.enemy_roster.units.values())
        elif consequence.target == "random":
            all_units = list(self._battle.friendly_roster.units.values()) + \
                       list(self._battle.enemy_roster.units.values())
            if all_units:
                targets = [self._rng.choice(all_units)]
            else:
                targets = []
        else:
            # Try to find named unit
            unit = self._battle.friendly_roster.get_unit(consequence.target)
            if not unit:
                unit = self._battle.enemy_roster.get_unit(consequence.target)
            targets = [unit] if unit else []

        if not targets:
            return "No valid targets for this effect."

        # Apply based on type
        for target in targets:
            if consequence.type == ConsequenceType.WOUND:
                # Apply wounds
                for _ in range(consequence.magnitude):
                    target.take_wound()
                result_parts.append(f"{target.name} takes {consequence.magnitude} wound(s)")

            elif consequence.type == ConsequenceType.MORALE_TEST:
                result_parts.append(f"{target.name} must test morale ({consequence.magnitude:+d})")

            elif consequence.type == ConsequenceType.STATUS_CHANGE:
                result_parts.append(f"{target.name}: {consequence.description}")

            elif consequence.type in (ConsequenceType.BUFF, ConsequenceType.DEBUFF,
                                      ConsequenceType.MOVEMENT, ConsequenceType.SHOOTING):
                # Track duration-based effects
                self._active_effects.append((consequence, consequence.duration))
                modifier_type = "bonus" if consequence.type == ConsequenceType.BUFF else "penalty"
                result_parts.append(
                    f"{target.name} gains {modifier_type}: {consequence.apply_text()}"
                )

            elif consequence.type == ConsequenceType.RESUPPLY:
                result_parts.append(f"{target.name} may resupply")

        return "; ".join(result_parts) if result_parts else "Effect applied."

    def advance_turn(self):
        """
        Advance turn and expire temporary effects.

        Call this at the start of each turn.
        """
        remaining = []
        expired = []

        for effect, turns in self._active_effects:
            if turns > 1:
                remaining.append((effect, turns - 1))
            else:
                expired.append(effect)

        self._active_effects = remaining

        return [e.description for e in expired]

    def get_active_effects(self) -> List[Tuple[EventConsequence, int]]:
        """Get all currently active effects with remaining duration."""
        return self._active_effects.copy()

    def clear_effects(self):
        """Clear all active effects."""
        self._active_effects = []


# Module-level instance
_event_system: Optional[BattleEventSystem] = None


def get_event_system() -> BattleEventSystem:
    """Get or create the event system singleton."""
    global _event_system
    if _event_system is None:
        _event_system = BattleEventSystem()
    return _event_system
