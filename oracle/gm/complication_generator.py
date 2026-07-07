"""
Fiction-Aware Complication Generator.

Generates complications and elaborations for oracle results that are connected
to the current fiction - active NPCs, plot threads, locations, and context.

Instead of generic "there's a catch" responses, this generates specific
complications like "Grimjaw recognizes you from the Blackmoor raid" or
"The artifact you're seeking is already in the hands of House Diem."

Usage:
    generator = ComplicationGenerator(memory)
    complication = generator.generate("yes_but", context="social")
    # Returns: "Yes, but the merchant's eyes narrow - he knows you owe
    #          a debt to the Thieves' Guild, and they have ears everywhere."
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread


class ComplicationType(Enum):
    """Types of complications that can arise."""
    NPC_INTERFERENCE = "npc_interference"       # An NPC complicates things
    THREAD_ESCALATION = "thread_escalation"     # A plot thread advances/worsens
    RESOURCE_COST = "resource_cost"             # Something is used up or lost
    TIME_PRESSURE = "time_pressure"             # Clock starts ticking
    REVELATION = "revelation"                   # Truth comes to light
    RELATIONSHIP_SHIFT = "relationship_shift"   # Someone's disposition changes
    ENVIRONMENTAL = "environmental"             # Location/situation changes
    CONSEQUENCE = "consequence"                 # Past action comes back


@dataclass
class Complication:
    """A generated complication with full context."""
    type: ComplicationType
    description: str
    involved_npcs: List[str] = field(default_factory=list)
    involved_threads: List[str] = field(default_factory=list)
    severity: str = "moderate"  # minor, moderate, major
    is_positive: bool = False   # True for "AND" elaborations that help


class ComplicationGenerator:
    """
    Generates fiction-aware complications for oracle results.

    Pulls from session memory to create complications that reference
    active NPCs, plot threads, and established fiction rather than
    generic obstacles.
    """

    def __init__(self, memory: Optional["SessionMemory"] = None):
        """
        Initialize the generator.

        Args:
            memory: Session memory for fiction context. If None, generates generic complications.
        """
        self.memory = memory

    def generate(
        self,
        oracle_result: str,
        context: str = "",
        question: str = "",
        rng: Optional[random.Random] = None
    ) -> Complication:
        """
        Generate a complication appropriate for the oracle result.

        Args:
            oracle_result: The oracle answer (yes_and, yes_but, no_and, no_but)
            context: Current context (combat, social, exploration)
            question: The original question asked
            rng: Optional random generator for testing

        Returns:
            A Complication with description and metadata
        """
        if rng is None:
            rng = random.Random()

        # Determine if this is positive or negative
        is_positive = oracle_result in ["yes_and", "no_but"]

        # Choose complication type based on context and available fiction
        comp_type = self._choose_type(context, is_positive, rng)

        # Generate the complication
        if self.memory:
            return self._generate_fiction_aware(comp_type, is_positive, context, question, rng)
        else:
            return self._generate_generic(comp_type, is_positive, context, rng)

    def _choose_type(
        self,
        context: str,
        is_positive: bool,
        rng: random.Random
    ) -> ComplicationType:
        """Choose a complication type weighted by context and available fiction."""
        # Base weights for each type
        weights = {
            ComplicationType.NPC_INTERFERENCE: 3,
            ComplicationType.THREAD_ESCALATION: 2,
            ComplicationType.RESOURCE_COST: 2,
            ComplicationType.TIME_PRESSURE: 2,
            ComplicationType.REVELATION: 2,
            ComplicationType.RELATIONSHIP_SHIFT: 2,
            ComplicationType.ENVIRONMENTAL: 1,
            ComplicationType.CONSEQUENCE: 2,
        }

        # Boost weights based on context
        if context == "combat":
            weights[ComplicationType.RESOURCE_COST] += 2
            weights[ComplicationType.TIME_PRESSURE] += 2
            weights[ComplicationType.ENVIRONMENTAL] += 2
        elif context == "social":
            weights[ComplicationType.NPC_INTERFERENCE] += 3
            weights[ComplicationType.RELATIONSHIP_SHIFT] += 3
            weights[ComplicationType.REVELATION] += 2
        elif context == "exploration":
            weights[ComplicationType.ENVIRONMENTAL] += 3
            weights[ComplicationType.TIME_PRESSURE] += 2
            weights[ComplicationType.REVELATION] += 2

        # Boost weights based on available fiction
        if self.memory:
            # More NPCs = more likely NPC complications
            npc_count = len([e for e in self.memory.entities.values()
                           if e.entity_type == "npc"])
            weights[ComplicationType.NPC_INTERFERENCE] += min(npc_count, 3)

            # More active threads = more likely thread escalation
            thread_count = len([t for t in self.memory.threads.values()
                              if t.status == "active"])
            weights[ComplicationType.THREAD_ESCALATION] += min(thread_count, 3)

        types = list(weights.keys())
        type_weights = [weights[t] for t in types]
        return rng.choices(types, weights=type_weights, k=1)[0]

    def _generate_fiction_aware(
        self,
        comp_type: ComplicationType,
        is_positive: bool,
        context: str,
        question: str,
        rng: random.Random
    ) -> Complication:
        """Generate a complication that references active fiction."""
        generators = {
            ComplicationType.NPC_INTERFERENCE: self._gen_npc_interference,
            ComplicationType.THREAD_ESCALATION: self._gen_thread_escalation,
            ComplicationType.RESOURCE_COST: self._gen_resource_cost,
            ComplicationType.TIME_PRESSURE: self._gen_time_pressure,
            ComplicationType.REVELATION: self._gen_revelation,
            ComplicationType.RELATIONSHIP_SHIFT: self._gen_relationship_shift,
            ComplicationType.ENVIRONMENTAL: self._gen_environmental,
            ComplicationType.CONSEQUENCE: self._gen_consequence,
        }

        generator = generators.get(comp_type, self._gen_generic_complication)
        return generator(is_positive, context, rng)

    def _gen_npc_interference(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate complication involving an NPC."""
        npcs = [e for e in self.memory.entities.values() if e.entity_type == "npc"]

        if not npcs:
            return self._gen_generic_complication(is_positive, context, rng)

        # Choose an NPC - prefer present NPCs, then by disposition
        present_npcs = [n for n in npcs if n.attributes.get("present", False)]
        if present_npcs:
            npc = rng.choice(present_npcs)
        else:
            npc = rng.choice(npcs)

        npc_name = npc.name
        disposition = npc.disposition

        if is_positive:
            # Helpful interference
            if disposition > 0:
                templates = [
                    f"{npc_name} steps in to help - they have information you need",
                    f"{npc_name} offers unexpected assistance",
                    f"{npc_name} remembers a favor they owe you",
                    f"{npc_name} reveals they share a common enemy",
                ]
            else:
                templates = [
                    f"{npc_name}'s plans align with yours, for now",
                    f"Even {npc_name} sees the benefit in helping this once",
                    f"{npc_name} has their own reasons for wanting this to succeed",
                ]
        else:
            # Unhelpful interference
            if disposition < 0:
                templates = [
                    f"{npc_name} is watching - they'll use this against you",
                    f"{npc_name} has already moved against you",
                    f"{npc_name} knows what you're planning",
                    f"This plays right into {npc_name}'s hands",
                ]
            else:
                templates = [
                    f"{npc_name} needs your help first before they can assist",
                    f"{npc_name} has unknowingly complicated things",
                    f"{npc_name} is caught in the middle and needs protection",
                    f"This will test your relationship with {npc_name}",
                ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.NPC_INTERFERENCE,
            description=description,
            involved_npcs=[npc_name],
            is_positive=is_positive,
        )

    def _gen_thread_escalation(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate complication from an active plot thread."""
        threads = [t for t in self.memory.threads.values() if t.status == "active"]

        if not threads:
            return self._gen_generic_complication(is_positive, context, rng)

        thread = rng.choice(threads)
        thread_name = thread.name

        if is_positive:
            templates = [
                f"This advances {thread_name} in your favor",
                f"A breakthrough in {thread_name} - new opportunity opens",
                f"The {thread_name} situation takes a turn for the better",
                f"This gives you leverage in {thread_name}",
            ]
        else:
            templates = [
                f"{thread_name} escalates - the timeline just accelerated",
                f"This complicates {thread_name} significantly",
                f"The stakes of {thread_name} just got higher",
                f"{thread_name} intersects with this in the worst way",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.THREAD_ESCALATION,
            description=description,
            involved_threads=[thread_name],
            is_positive=is_positive,
        )

    def _gen_resource_cost(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate a resource-related complication."""
        if is_positive:
            templates = [
                "You find additional supplies in the process",
                "This saves significant resources",
                "You discover something valuable along the way",
                "An unexpected asset becomes available",
            ]
        else:
            templates = [
                "This will cost more than expected",
                "Something important is used up or damaged",
                "You'll need to sacrifice something to proceed",
                "The price is higher than anticipated",
                "Equipment fails at a critical moment",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.RESOURCE_COST,
            description=description,
            is_positive=is_positive,
            severity="minor" if is_positive else "moderate",
        )

    def _gen_time_pressure(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate a time-related complication."""
        if is_positive:
            templates = [
                "You have more time than you thought",
                "The deadline isn't as urgent as believed",
                "Events elsewhere buy you breathing room",
                "The opposition is delayed",
            ]
        else:
            templates = [
                "The clock is ticking - faster than expected",
                "Someone else is racing toward the same goal",
                "Delay now means losing everything",
                "Events are accelerating beyond control",
                "You're already late - consequences are building",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.TIME_PRESSURE,
            description=description,
            is_positive=is_positive,
            severity="moderate" if not is_positive else "minor",
        )

    def _gen_revelation(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate a revelation complication."""
        # Try to connect to an existing NPC or thread
        involved_npcs = []
        involved_threads = []

        npcs = list(self.memory.entities.values())
        threads = list(self.memory.threads.values())

        if is_positive:
            templates = [
                "You learn something crucial you didn't know before",
                "A hidden truth works in your favor",
                "The real situation is better than you feared",
                "Your suspicions were wrong - in a good way",
            ]
            if npcs:
                npc = rng.choice([n for n in npcs if n.entity_type == "npc"] or npcs)
                templates.append(f"You discover {npc.name}'s true intentions - they can be trusted")
                involved_npcs.append(npc.name)
        else:
            templates = [
                "The truth is worse than you suspected",
                "A comforting lie is exposed",
                "What you thought you knew was wrong",
                "Someone has been deceiving you",
            ]
            if npcs:
                npc = rng.choice([n for n in npcs if n.entity_type == "npc"] or npcs)
                templates.append(f"You discover {npc.name} has been hiding something")
                involved_npcs.append(npc.name)

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.REVELATION,
            description=description,
            involved_npcs=involved_npcs,
            involved_threads=involved_threads,
            is_positive=is_positive,
        )

    def _gen_relationship_shift(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate a relationship change complication."""
        npcs = [e for e in self.memory.entities.values() if e.entity_type == "npc"]

        if not npcs:
            return self._gen_generic_complication(is_positive, context, rng)

        npc = rng.choice(npcs)

        if is_positive:
            templates = [
                f"{npc.name}'s opinion of you improves",
                f"You earn {npc.name}'s respect",
                f"{npc.name} sees you in a new light",
                f"A bond forms with {npc.name}",
            ]
        else:
            templates = [
                f"{npc.name} is disappointed in you",
                f"Your relationship with {npc.name} is strained",
                f"{npc.name} begins to doubt you",
                f"Trust with {npc.name} is damaged",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.RELATIONSHIP_SHIFT,
            description=description,
            involved_npcs=[npc.name],
            is_positive=is_positive,
        )

    def _gen_environmental(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate an environmental complication."""
        location = self.memory.current_scene.get("location", "this place")

        if is_positive:
            templates = [
                f"The environment of {location} works in your favor",
                "The terrain provides an unexpected advantage",
                "Natural cover or concealment is available",
                "Environmental conditions improve",
            ]
        else:
            templates = [
                f"Something about {location} makes this harder",
                "The environment turns hostile",
                "Conditions deteriorate rapidly",
                "The terrain becomes treacherous",
                "Natural obstacles appear",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.ENVIRONMENTAL,
            description=description,
            is_positive=is_positive,
        )

    def _gen_consequence(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate a consequence from past actions."""
        if is_positive:
            templates = [
                "A past good deed pays dividends now",
                "Your reputation works in your favor",
                "Someone remembers your kindness",
                "Past preparation proves useful",
            ]
        else:
            templates = [
                "Past actions come back to haunt you",
                "Someone remembers what you did",
                "The consequences of earlier choices arrive",
                "A mistake from the past resurfaces",
                "Your reputation precedes you - and not favorably",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.CONSEQUENCE,
            description=description,
            is_positive=is_positive,
        )

    def _gen_generic_complication(
        self,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Fallback generic complication when no fiction is available."""
        if is_positive:
            templates = [
                "An unexpected advantage appears",
                "Fortune favors you in this moment",
                "Things are better than expected",
                "Help comes from an unlikely source",
            ]
        else:
            templates = [
                "An unforeseen obstacle emerges",
                "The situation is more complex than it appeared",
                "Success comes at a cost",
                "New complications arise",
            ]

        description = rng.choice(templates)

        return Complication(
            type=ComplicationType.NPC_INTERFERENCE if not is_positive else ComplicationType.REVELATION,
            description=description,
            is_positive=is_positive,
        )

    def _generate_generic(
        self,
        comp_type: ComplicationType,
        is_positive: bool,
        context: str,
        rng: random.Random
    ) -> Complication:
        """Generate without memory - fallback to generic complications."""
        return self._gen_generic_complication(is_positive, context, rng)

    def format_complication(self, complication: Complication) -> str:
        """Format a complication for display."""
        lines = [complication.description]

        if complication.involved_npcs:
            lines.append(f"  Involves: {', '.join(complication.involved_npcs)}")

        if complication.involved_threads:
            lines.append(f"  Thread: {', '.join(complication.involved_threads)}")

        return "\n".join(lines)
