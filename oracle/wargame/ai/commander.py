"""
Wargame Commander Personalities - Give the tactical AI a face and voice.

Instead of anonymous tactical decisions, commanders have:
- Distinct personalities and tactical preferences
- Voice patterns for narrating their decisions
- Signature moves they favor
- Weaknesses that can be exploited
- Uncertainty and mistakes based on "fog of war"

Usage:
    commander = CommanderPersonality.create("aggressive_blitzer")
    narrator = BattleNarrator(commander)

    decision = tactical_ai.decide(situation)
    narration = narrator.narrate_decision(decision)
    # "Von Krieger's panzers pivot as one. 'Concentrate fire!'
    #  The armor squadron targets your exposed infantry."

Moved from oracle/wargame_commander.py as part of the wargame package restructure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from .tactical import Aggression, Doctrine, TacticalDecision, TacticalOption


class CommanderArchetype(Enum):
    """Commander personality archetypes."""

    AGGRESSIVE_BLITZER = "aggressive_blitzer"
    CAUTIOUS_PLANNER = "cautious_planner"
    CUNNING_FEINTER = "cunning_feinter"
    STUBBORN_DEFENDER = "stubborn_defender"
    METHODICAL_GRINDER = "methodical_grinder"
    GLORY_HUNTER = "glory_hunter"
    RUTHLESS_PRAGMATIST = "ruthless_pragmatist"


@dataclass
class CommanderPersonality:
    """
    A commander personality with distinct tactical style and voice.

    Commanders have preferences that modify tactical AI decisions
    and voice patterns that make narration feel like facing
    a thinking opponent.
    """

    name: str
    archetype: CommanderArchetype
    title: str = ""
    description: str = ""

    # Tactical preferences
    preferred_doctrine: Doctrine = Doctrine.BALANCED if hasattr(Doctrine, 'BALANCED') else Doctrine.ELITE
    preferred_aggression: Aggression = Aggression.BALANCED
    signature_moves: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    # Voice and personality
    voice_patterns: list[str] = field(default_factory=list)
    victory_lines: list[str] = field(default_factory=list)
    defeat_lines: list[str] = field(default_factory=list)
    taunt_lines: list[str] = field(default_factory=list)
    respect_lines: list[str] = field(default_factory=list)

    # Behavioral modifiers
    risk_tolerance: float = 0.5  # 0.0 = very cautious, 1.0 = very risky
    patience: float = 0.5  # 0.0 = impulsive, 1.0 = very patient
    adaptability: float = 0.5  # 0.0 = rigid, 1.0 = highly adaptive

    # Fog of war / imperfection
    perception_accuracy: float = 0.8  # How accurately they read the battlefield
    mistake_chance: float = 0.1  # Chance of tactical error

    # Aggression property for OpponentAI compatibility
    @property
    def aggression(self) -> float:
        """Get aggression as a 0.0-1.0 float for OpponentAI."""
        return self.risk_tolerance

    @classmethod
    def create(
        cls, archetype: str | CommanderArchetype
    ) -> "CommanderPersonality":
        """Create a commander from an archetype with randomized details."""
        if isinstance(archetype, str):
            archetype = CommanderArchetype(archetype)

        generators = {
            CommanderArchetype.AGGRESSIVE_BLITZER: cls._create_aggressive_blitzer,
            CommanderArchetype.CAUTIOUS_PLANNER: cls._create_cautious_planner,
            CommanderArchetype.CUNNING_FEINTER: cls._create_cunning_feinter,
            CommanderArchetype.STUBBORN_DEFENDER: cls._create_stubborn_defender,
            CommanderArchetype.METHODICAL_GRINDER: cls._create_methodical_grinder,
            CommanderArchetype.GLORY_HUNTER: cls._create_glory_hunter,
            CommanderArchetype.RUTHLESS_PRAGMATIST: cls._create_ruthless_pragmatist,
        }

        return generators.get(archetype, cls._create_aggressive_blitzer)()

    @classmethod
    def _create_aggressive_blitzer(cls) -> "CommanderPersonality":
        names = ["Von Krieger", "Hammerfist", "The Red Baron", "Ironclad", "Blitzmann"]
        titles = ["Marshal", "Warlord", "General", "Commander", "Battlemaster"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.AGGRESSIVE_BLITZER,
            title=random.choice(titles),
            description="Believes in overwhelming force and rapid assault. Hesitation is defeat.",
            preferred_doctrine=Doctrine.ALPHA_STRIKE,
            preferred_aggression=Aggression.AGGRESSIVE,
            signature_moves=[
                "Concentrated armor assault",
                "Alpha strike on exposed units",
                "Refuses to retreat under any circumstances",
                "Overwhelming first strike",
            ],
            weaknesses=[
                "Overextends flanks",
                "Ignores rear guard",
                "Burns through reserves quickly",
                "Predictable aggression",
            ],
            voice_patterns=[
                "We attack at dawn.",
                "Hesitation is death.",
                "Forward! Always forward!",
                "Crush them before they can react.",
                "No prisoners.",
            ],
            victory_lines=[
                "As expected. They never stood a chance.",
                "Victory through superior firepower.",
                "This is what happens when you face true strength.",
            ],
            defeat_lines=[
                "A tactical withdrawal. We will return.",
                "They got lucky. It won't happen again.",
                "Regroup and counterattack!",
            ],
            taunt_lines=[
                "Is that the best you can do?",
                "Your defenses are laughable.",
                "Run while you still can.",
            ],
            respect_lines=[
                "A worthy opponent. This will be interesting.",
                "You fight well. But not well enough.",
            ],
            risk_tolerance=0.8,
            patience=0.2,
            adaptability=0.3,
            perception_accuracy=0.7,
            mistake_chance=0.15,
        )

    @classmethod
    def _create_cautious_planner(cls) -> "CommanderPersonality":
        names = ["Eisenhardt", "The Grey Fox", "Prudence", "Calculon", "Methodius"]
        titles = ["Strategos", "Grand Tactician", "Lord Marshal", "High Commander"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.CAUTIOUS_PLANNER,
            title=random.choice(titles),
            description="Every battle is won before it's fought. Preparation is everything.",
            preferred_doctrine=Doctrine.DEFENSIVE,
            preferred_aggression=Aggression.CAUTIOUS,
            signature_moves=[
                "Fortified defensive positions",
                "Careful probe before commitment",
                "Reserves always maintained",
                "Coordinated crossfire zones",
            ],
            weaknesses=[
                "Slow to react to opportunities",
                "Overthinks simple situations",
                "Can be baited by feints",
                "Struggles against unpredictable opponents",
            ],
            voice_patterns=[
                "Patience. The moment will come.",
                "We have prepared for this.",
                "Let them come to us.",
                "Every variable has been accounted for.",
                "Proceed according to plan.",
            ],
            victory_lines=[
                "As I calculated.",
                "The plan succeeded perfectly.",
                "They walked into our trap.",
            ],
            defeat_lines=[
                "There was a variable I failed to account for.",
                "We must revise our models.",
                "A setback. Not a defeat.",
            ],
            taunt_lines=[
                "Your moves are... predictable.",
                "I expected more from you.",
                "You're playing into our hands.",
            ],
            respect_lines=[
                "An unexpected move. Impressive.",
                "You've given me something to think about.",
            ],
            risk_tolerance=0.2,
            patience=0.9,
            adaptability=0.4,
            perception_accuracy=0.9,
            mistake_chance=0.05,
        )

    @classmethod
    def _create_cunning_feinter(cls) -> "CommanderPersonality":
        names = ["The Shadow", "Deceiver", "Trickster", "Phantom", "Mirage"]
        titles = ["Schemer", "Master of Shadows", "The Unseen Hand", "Puppeteer"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.CUNNING_FEINTER,
            title=random.choice(titles),
            description="War is deception. Make them look where you aren't.",
            preferred_doctrine=Doctrine.GUERRILLA,
            preferred_aggression=Aggression.BALANCED,
            signature_moves=[
                "Feint attacks to draw attention",
                "Hidden reserve sudden deployment",
                "Misdirection before real assault",
                "Appear weak when strong",
            ],
            weaknesses=[
                "Overcomplicated plans",
                "Vulnerable to direct assault",
                "Relies on confusion",
                "Struggles when plan is exposed",
            ],
            voice_patterns=[
                "They see what we want them to see.",
                "The real attack comes from elsewhere.",
                "Misdirection is our greatest weapon.",
                "By the time they realize, it will be too late.",
                "Let them think they're winning.",
            ],
            victory_lines=[
                "They never saw it coming.",
                "Deception is the art of war.",
                "The trap is sprung.",
            ],
            defeat_lines=[
                "They saw through the ruse. Impressive.",
                "We underestimated their perception.",
                "Time for a different approach.",
            ],
            taunt_lines=[
                "Are you sure that's what you're seeing?",
                "Question everything.",
                "Nothing is as it appears.",
            ],
            respect_lines=[
                "You didn't fall for it. Interesting.",
                "A fellow student of deception?",
            ],
            risk_tolerance=0.5,
            patience=0.7,
            adaptability=0.8,
            perception_accuracy=0.75,
            mistake_chance=0.1,
        )

    @classmethod
    def _create_stubborn_defender(cls) -> "CommanderPersonality":
        names = ["The Wall", "Ironhold", "Steadfast", "Bulwark", "The Immovable"]
        titles = ["Castellan", "Guardian", "Defender", "Shieldbearer"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.STUBBORN_DEFENDER,
            title=random.choice(titles),
            description="We hold. No matter the cost. This position will not fall.",
            preferred_doctrine=Doctrine.DEFENSIVE,
            preferred_aggression=Aggression.PASSIVE,
            signature_moves=[
                "Fighting withdrawal to prepared positions",
                "Overlapping fields of fire",
                "Never abandons position willingly",
                "Counter-attacks only when advantageous",
            ],
            weaknesses=[
                "Won't pursue fleeing enemies",
                "Predictable defensive positions",
                "Can be bypassed",
                "Struggles with mobile warfare",
            ],
            voice_patterns=[
                "We hold.",
                "Not one step back.",
                "They shall not pass.",
                "The line must hold.",
                "Hold until relieved.",
            ],
            victory_lines=[
                "The position held. As it always does.",
                "They broke against us like waves against stone.",
                "Defensive victory is still victory.",
            ],
            defeat_lines=[
                "We held as long as we could.",
                "The position was untenable.",
                "We'll make them pay for every inch.",
            ],
            taunt_lines=[
                "Come and try to take it.",
                "We've held against worse.",
                "Your assault is futile.",
            ],
            respect_lines=[
                "You found a weakness. That won't happen twice.",
                "A tenacious assault. We'll be ready next time.",
            ],
            risk_tolerance=0.1,
            patience=0.95,
            adaptability=0.2,
            perception_accuracy=0.85,
            mistake_chance=0.05,
        )

    @classmethod
    def _create_methodical_grinder(cls) -> "CommanderPersonality":
        names = ["The Reaper", "Attritor", "Relentless", "The Inevitable"]
        titles = ["War Marshal", "Grand General", "Supreme Commander"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.METHODICAL_GRINDER,
            title=random.choice(titles),
            description="Slow, steady, inevitable. We will wear them down.",
            preferred_doctrine=Doctrine.HORDE,
            preferred_aggression=Aggression.BALANCED,
            signature_moves=[
                "Constant pressure on all fronts",
                "Attrition warfare",
                "Replacement waves",
                "Systematic elimination of enemy strength",
            ],
            weaknesses=[
                "Slow to achieve decisive victory",
                "Vulnerable to quick strikes",
                "Resource dependent",
                "Morale problems in prolonged fights",
            ],
            voice_patterns=[
                "Time is on our side.",
                "We have more. We always have more.",
                "Attrition favors the patient.",
                "Every loss they take is one they can't replace.",
                "Slowly, inevitably.",
            ],
            victory_lines=[
                "Inevitable.",
                "They couldn't sustain the losses.",
                "Attrition always wins in the end.",
            ],
            defeat_lines=[
                "We underestimated their resilience.",
                "They moved faster than expected.",
                "We need more resources.",
            ],
            taunt_lines=[
                "How long can you hold out?",
                "We have infinite patience.",
                "Every shot you fire is one less.",
            ],
            respect_lines=[
                "You've held longer than most.",
                "Impressive endurance. But futile.",
            ],
            risk_tolerance=0.3,
            patience=0.85,
            adaptability=0.3,
            perception_accuracy=0.8,
            mistake_chance=0.08,
        )

    @classmethod
    def _create_glory_hunter(cls) -> "CommanderPersonality":
        names = ["Glorious", "The Champion", "Vainglory", "The Bold"]
        titles = ["Hero General", "Champion Commander", "Lord Paramount"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.GLORY_HUNTER,
            title=random.choice(titles),
            description="Victory must be glorious! We shall write history today!",
            preferred_doctrine=Doctrine.ELITE,
            preferred_aggression=Aggression.RECKLESS,
            signature_moves=[
                "Dramatic charges",
                "Personal heroics",
                "Seeking out enemy leaders",
                "Grand tactical flourishes",
            ],
            weaknesses=[
                "Takes unnecessary risks",
                "Ignores tactical fundamentals",
                "Obsessed with dramatic victories",
                "Vulnerable to traps",
            ],
            voice_patterns=[
                "For glory!",
                "History will remember this day!",
                "A magnificent charge!",
                "Let them see our banners!",
                "This shall be our finest hour!",
            ],
            victory_lines=[
                "A glorious victory! Songs will be sung!",
                "Did you see that charge? Magnificent!",
                "History is written by the victorious!",
            ],
            defeat_lines=[
                "A temporary setback in our glorious campaign!",
                "We shall return more glorious than before!",
                "Even in defeat, we were magnificent!",
            ],
            taunt_lines=[
                "Face me if you dare!",
                "Where is your courage?",
                "History favors the bold!",
            ],
            respect_lines=[
                "A worthy foe! This will be a battle worth remembering!",
                "You fight with honor. I respect that.",
            ],
            risk_tolerance=0.95,
            patience=0.1,
            adaptability=0.4,
            perception_accuracy=0.6,
            mistake_chance=0.2,
        )

    @classmethod
    def _create_ruthless_pragmatist(cls) -> "CommanderPersonality":
        names = ["The Cold One", "Calculator", "The Efficient", "Zero"]
        titles = ["Director", "Coordinator", "Overseer"]

        return cls(
            name=random.choice(names),
            archetype=CommanderArchetype.RUTHLESS_PRAGMATIST,
            title=random.choice(titles),
            description="Victory at any cost. Sentiment has no place in war.",
            preferred_doctrine=Doctrine.ALPHA_STRIKE,
            preferred_aggression=Aggression.BALANCED,
            signature_moves=[
                "Sacrificing units for advantage",
                "Exploiting any weakness ruthlessly",
                "No concern for 'fair' tactics",
                "Maximum efficiency, minimum waste",
            ],
            weaknesses=[
                "Underestimates morale factors",
                "Predictable optimization",
                "No inspire loyalty",
                "Relies purely on calculation",
            ],
            voice_patterns=[
                "Acceptable losses.",
                "Efficient.",
                "The numbers favor this approach.",
                "Sentiment is irrelevant.",
                "Optimization complete.",
            ],
            victory_lines=[
                "Optimal outcome achieved.",
                "As calculated.",
                "Efficiency proven.",
            ],
            defeat_lines=[
                "Parameters require adjustment.",
                "Miscalculation detected.",
                "Recalibrating...",
            ],
            taunt_lines=[
                "Your inefficiency is... notable.",
                "Suboptimal tactics.",
                "The numbers are against you.",
            ],
            respect_lines=[
                "Efficient. I approve.",
                "Your tactics exceed expected parameters.",
            ],
            risk_tolerance=0.5,
            patience=0.6,
            adaptability=0.7,
            perception_accuracy=0.85,
            mistake_chance=0.08,
        )

    def modify_decision_weights(
        self, options: list[TacticalOption], rng: Optional[random.Random] = None
    ) -> list[TacticalOption]:
        """
        Modify tactical option weights based on commander personality.

        Args:
            options: List of tactical options to modify
            rng: Optional random generator

        Returns:
            Modified options with adjusted weights
        """
        if rng is None:
            rng = random.Random()

        for option in options:
            # Apply personality modifiers
            description_lower = option.description.lower()

            # Aggressive types boost attack options
            if self.risk_tolerance > 0.6:
                if any(
                    word in description_lower
                    for word in ["attack", "assault", "charge", "advance"]
                ):
                    option.modified_weight *= 1.3

            # Cautious types boost defensive options
            if self.risk_tolerance < 0.4:
                if any(
                    word in description_lower
                    for word in ["defend", "hold", "fortify", "cover"]
                ):
                    option.modified_weight *= 1.3

            # Patient types boost waiting options
            if self.patience > 0.7:
                if any(
                    word in description_lower
                    for word in ["wait", "observe", "prepare", "position"]
                ):
                    option.modified_weight *= 1.2

            # Random variation for fog of war
            variation = rng.uniform(0.9, 1.1)
            option.modified_weight *= variation

            # Chance of mistake - might boost a bad option
            if rng.random() < self.mistake_chance:
                option.modified_weight *= rng.uniform(0.8, 1.5)

        return options

    def get_voice_line(
        self, context: str = "general", rng: Optional[random.Random] = None
    ) -> str:
        """Get an appropriate voice line for the context."""
        if rng is None:
            rng = random.Random()

        lines = {
            "general": self.voice_patterns,
            "victory": self.victory_lines,
            "defeat": self.defeat_lines,
            "taunt": self.taunt_lines,
            "respect": self.respect_lines,
        }

        line_list = lines.get(context, self.voice_patterns)
        if line_list:
            return rng.choice(line_list)
        return ""


class BattleNarrator:
    """
    Narrates tactical decisions with commander personality.

    Transforms mechanical decision output into dramatic narrative
    that makes facing the AI feel like facing a thinking opponent.
    """

    def __init__(self, commander: CommanderPersonality):
        self.commander = commander

    def narrate_decision(
        self, decision: TacticalDecision, rng: Optional[random.Random] = None
    ) -> str:
        """
        Narrate a tactical decision with dramatic flair.

        Args:
            decision: The tactical decision to narrate
            rng: Optional random generator

        Returns:
            Dramatic narration of the decision
        """
        if rng is None:
            rng = random.Random()

        lines = []

        # Commander identification
        title = f"{self.commander.title} {self.commander.name}"

        # Opening - what are they doing?
        action = decision.selected.description.lower()
        if "attack" in action or "assault" in action:
            opener = self._narrate_attack(decision, title, rng)
        elif "defend" in action or "hold" in action:
            opener = self._narrate_defense(decision, title, rng)
        elif "retreat" in action or "withdraw" in action:
            opener = self._narrate_retreat(decision, title, rng)
        elif "flank" in action or "maneuver" in action:
            opener = self._narrate_maneuver(decision, title, rng)
        else:
            opener = self._narrate_generic(decision, title, rng)

        lines.append(opener)

        # Add voice line
        voice_line = self.commander.get_voice_line("general", rng)
        if voice_line:
            lines.append(f'"{voice_line}"')

        return "\n".join(lines)

    def _narrate_attack(
        self, decision: TacticalDecision, title: str, rng: random.Random
    ) -> str:
        templates = [
            f"{title} signals the advance. {decision.selected.description}.",
            f"{title}'s forces move to attack. {decision.selected.description}.",
            f"At {title}'s command, the assault begins. {decision.selected.description}.",
            f"{title} commits to the offensive. {decision.selected.description}.",
        ]
        return rng.choice(templates)

    def _narrate_defense(
        self, decision: TacticalDecision, title: str, rng: random.Random
    ) -> str:
        templates = [
            f"{title} orders the line to hold. {decision.selected.description}.",
            f"{title}'s forces dig in. {decision.selected.description}.",
            f"At {title}'s signal, defenses are reinforced. {decision.selected.description}.",
            f"{title} commits to holding position. {decision.selected.description}.",
        ]
        return rng.choice(templates)

    def _narrate_retreat(
        self, decision: TacticalDecision, title: str, rng: random.Random
    ) -> str:
        templates = [
            f"{title} orders a tactical withdrawal. {decision.selected.description}.",
            f"{title}'s forces pull back in good order. {decision.selected.description}.",
            f"At {title}'s command, the retreat begins. {decision.selected.description}.",
            f"{title} concedes ground - for now. {decision.selected.description}.",
        ]
        return rng.choice(templates)

    def _narrate_maneuver(
        self, decision: TacticalDecision, title: str, rng: random.Random
    ) -> str:
        templates = [
            f"{title}'s forces reposition. {decision.selected.description}.",
            f"At {title}'s direction, units maneuver. {decision.selected.description}.",
            f"{title} sees an opportunity. {decision.selected.description}.",
            f"{title} adjusts the tactical picture. {decision.selected.description}.",
        ]
        return rng.choice(templates)

    def _narrate_generic(
        self, decision: TacticalDecision, title: str, rng: random.Random
    ) -> str:
        templates = [
            f"{title} makes a decision. {decision.selected.description}.",
            f"At {title}'s command: {decision.selected.description}.",
            f"{title} acts. {decision.selected.description}.",
        ]
        return rng.choice(templates)

    def narrate_battle_event(
        self, event: str, rng: Optional[random.Random] = None
    ) -> str:
        """Narrate a battle event with commander reaction."""
        if rng is None:
            rng = random.Random()

        title = f"{self.commander.title} {self.commander.name}"
        event_lower = event.lower()

        if any(word in event_lower for word in ["reinforcement", "support", "arrive"]):
            reactions = [
                f"{title} notes the new arrivals.",
                f"{title} adjusts plans for the reinforcements.",
                f"'{self.commander.get_voice_line('general', rng)}'",
            ]
        elif any(
            word in event_lower for word in ["ammunition", "supply", "malfunction"]
        ):
            reactions = [
                f"{title} frowns at the supply report.",
                f"{title} adjusts tactics for the shortage.",
                f"A setback. {title} adapts.",
            ]
        else:
            reactions = [
                f"{title} takes note of the development.",
                f"{title} considers the implications.",
                f"The battlefield shifts. {title} responds.",
            ]

        return f"{event}\n{rng.choice(reactions)}"

    def narrate_victory(self, rng: Optional[random.Random] = None) -> str:
        """Narrate a battle victory."""
        if rng is None:
            rng = random.Random()

        title = f"{self.commander.title} {self.commander.name}"
        victory_line = self.commander.get_voice_line("victory", rng)

        templates = [
            f'{title} surveys the field. The battle is won.\n"{victory_line}"',
            f'{title} accepts the enemy\'s surrender.\n"{victory_line}"',
            f'Victory for {title}\'s forces.\n"{victory_line}"',
        ]
        return rng.choice(templates)

    def narrate_defeat(self, rng: Optional[random.Random] = None) -> str:
        """Narrate a battle defeat."""
        if rng is None:
            rng = random.Random()

        title = f"{self.commander.title} {self.commander.name}"
        defeat_line = self.commander.get_voice_line("defeat", rng)

        templates = [
            f'{title}\'s forces break. The battle is lost.\n"{defeat_line}"',
            f'Defeat for {title}.\n"{defeat_line}"',
            f'{title} orders the retreat.\n"{defeat_line}"',
        ]
        return rng.choice(templates)


# Convenience function to generate a random commander
def generate_commander(archetype: Optional[str] = None) -> CommanderPersonality:
    """Generate a random commander, optionally of a specific archetype."""
    if archetype:
        return CommanderPersonality.create(archetype)
    else:
        arch = random.choice(list(CommanderArchetype))
        return CommanderPersonality.create(arch)
