"""
Enhanced Narrative Responder - Integrates all improvement systems.

This module extends NarrativeResponder with:
- Meaning tables for surprising oracle interpretations
- Fiction-aware complications that reference active NPCs/threads
- Pacing engine for dramatic rhythm
- NPC memory for relationship-aware dialogue

Usage:
    responder = EnhancedResponder(memory)
    response = responder.interpret_oracle_enhanced("yes_but", "Is the door locked?")
    # Returns: "Yes, but Grimjaw's eyes narrow - he knows about this place."
"""

from __future__ import annotations

import random
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from oracle.gm.responder import NarrativeResponder
from oracle.gm.meaning import MeaningTableReader, MeaningRoll
from oracle.gm.complication_generator import ComplicationGenerator, Complication
from oracle.gm.pacing import PacingEngine, BeatType
from oracle.gm.npc_memory import NPCMemoryTracker
from oracle.gm.personality import GMPersonality

if TYPE_CHECKING:
    from oracle.gm.memory import SessionMemory


class EnhancedResponder(NarrativeResponder):
    """
    Enhanced narrative responder with full system integration.

    Combines all the new systems:
    - MeaningTableReader for oracle elaborations
    - ComplicationGenerator for fiction-aware complications
    - PacingEngine for dramatic rhythm
    - NPCMemoryTracker for relationship context
    """

    def __init__(
        self,
        memory: "SessionMemory",
        personality: Optional[GMPersonality] = None,
    ):
        super().__init__(personality)
        self.memory = memory

        # Initialize enhancement systems
        self.meaning_reader = MeaningTableReader()
        self.complication_gen = ComplicationGenerator(memory)
        self.pacing = PacingEngine()
        self.npc_tracker = NPCMemoryTracker(memory)

    def interpret_oracle_enhanced(
        self,
        answer: str,
        question: str,
        context: str = "",
    ) -> str:
        """
        Generate an enhanced oracle interpretation using all systems.

        This replaces the generic "there's a catch" elaborations with
        specific, fiction-aware interpretations that reference active
        NPCs, plot threads, and use meaning table combinations.

        Args:
            answer: Oracle result (yes_and, yes, yes_but, no_but, no, no_and)
            question: The question that was asked
            context: Current context (combat, social, exploration)

        Returns:
            Rich narrative interpretation
        """
        # Get base template
        templates = self.oracle_templates.get(answer, self.oracle_templates["yes"])
        base = random.choice(templates)

        # Determine context from question if not provided
        if not context:
            context = self._infer_context(question)

        # Generate elaboration based on answer type
        elaboration_text = ""

        if answer in ["yes_and", "yes_but", "no_but", "no_and"]:
            # Use meaning tables for the core concept
            meaning = self.meaning_reader.roll_meaning(context=context)

            # Use complication generator for fiction-aware details
            complication = self.complication_gen.generate(
                oracle_result=answer,
                context=context,
                question=question,
            )

            # Combine meaning + complication into elaboration
            elaboration_text = self._combine_meaning_and_complication(
                meaning, complication, answer
            )

            # Log pacing beat
            if answer in ["yes_and", "no_and"]:
                self.pacing.log_beat(BeatType.PUSH, tension_delta=1)
            elif answer in ["yes_but", "no_but"]:
                self.pacing.log_beat(BeatType.PULL, tension_delta=0)
        else:
            # Simple yes/no - log as pause
            self.pacing.log_beat(BeatType.PAUSE, tension_delta=0)

        # Build response
        response = base

        # Apply elaboration
        if answer == "yes_and":
            response = response.replace("{elaboration}", elaboration_text)
        elif answer == "yes_but":
            response = response.replace("{complication}", elaboration_text)
        elif answer == "no_but":
            response = response.replace("{silver_lining}", elaboration_text)
        elif answer == "no_and":
            response = response.replace("{escalation}", elaboration_text)

        # Apply personality formatting
        response = self.personality.format_response(response)

        return response

    def _infer_context(self, question: str) -> str:
        """Infer context from the question."""
        question_lower = question.lower()

        combat_words = ["attack", "fight", "hit", "shoot", "kill", "wound", "damage", "battle"]
        social_words = ["talk", "convince", "persuade", "ask", "tell", "lie", "trust", "friend"]
        exploration_words = ["find", "search", "look", "open", "trap", "hidden", "lock", "door"]

        if any(word in question_lower for word in combat_words):
            return "combat"
        elif any(word in question_lower for word in social_words):
            return "social"
        elif any(word in question_lower for word in exploration_words):
            return "exploration"

        return "core"

    def _combine_meaning_and_complication(
        self,
        meaning: MeaningRoll,
        complication: Complication,
        answer: str,
    ) -> str:
        """
        Combine meaning table roll with fiction-aware complication.

        Creates a layered elaboration that uses the abstract meaning
        (Action + Subject) to guide the specific complication.
        """
        # Get the complication description
        comp_text = complication.description

        # If complication involves known NPCs, it's already fiction-aware
        if complication.involved_npcs or complication.involved_threads:
            # Add meaning table hint as flavor
            if meaning.action.word and meaning.subject.word:
                action = meaning.action.word.lower()
                subject = meaning.subject.word

                # Weave meaning into complication
                if "reveal" in action or "discover" in action:
                    comp_text = f"{comp_text} Something is revealed about {subject.lower()}."
                elif "betray" in action or "deceive" in action:
                    comp_text = f"{comp_text} Trust regarding {subject.lower()} is at stake."
                elif "protect" in action or "defend" in action:
                    comp_text = f"{comp_text} {subject} must be protected."

        else:
            # Generic complication - use meaning to make it specific
            action = meaning.action.word.lower()
            subject = meaning.subject.word

            # Build meaning-based elaboration
            meaning_elaboration = f"[{meaning.action.word} + {meaning.subject.word}] - "

            if answer in ["yes_and", "no_but"]:
                # Positive - something helps
                meaning_elaboration += f"Something about {subject.lower()} works in your favor"
            else:
                # Negative - something complicates
                meaning_elaboration += f"Something about {subject.lower()} complicates things"

            comp_text = f"{comp_text} {meaning_elaboration}."

        return comp_text

    def npc_interaction_enhanced(
        self,
        npc_name: str,
        interaction_type: str = "greeting",
    ) -> str:
        """
        Generate an NPC interaction with relationship memory.

        Uses NPCMemoryTracker to reference past interactions,
        unfulfilled promises, discovered lies, etc.

        Args:
            npc_name: The NPC's name
            interaction_type: Type of interaction (greeting, dialogue, etc.)

        Returns:
            Context-aware NPC response
        """
        # Get relationship context
        context = self.npc_tracker.get_relationship_context(npc_name)

        # Get entity for disposition
        entity = self.memory.get_entity(npc_name)
        disposition = entity.disposition if entity else 0

        # First meeting
        if not context["known"]:
            # Log the meeting
            self.npc_tracker.log_meeting(npc_name)
            return super().npc_interaction(npc_name, disposition, interaction_type)

        # Returning interaction - add memory context
        response_parts = []

        # Base interaction
        base = super().npc_interaction(npc_name, disposition, interaction_type)
        response_parts.append(base)

        # Add memory-based context
        if context["times_met"] == 1:
            # Second meeting
            memory_lines = [
                f"{npc_name} remembers you from before.",
                f"Recognition crosses {npc_name}'s face.",
                f"\"We meet again,\" {npc_name} notes.",
            ]
            response_parts.append(random.choice(memory_lines))

        # Check for unfulfilled promises
        if context["unfulfilled_promises"]:
            promise = context["unfulfilled_promises"][0]
            promise_lines = [
                f"\"About that matter you promised...\" {npc_name} trails off.",
                f"{npc_name} gives you a pointed look. \"{promise}?\"",
                f"\"I haven't forgotten your promise,\" {npc_name} says.",
            ]
            response_parts.append(random.choice(promise_lines))

        # Check for discovered lies
        if context["discovered_lies"]:
            lie_lines = [
                f"{npc_name}'s eyes narrow with distrust.",
                f"There's coldness in {npc_name}'s demeanor. They haven't forgotten your deception.",
                f"\"I know what you really are,\" {npc_name} says quietly.",
            ]
            response_parts.append(random.choice(lie_lines))

        # Trust issues
        if context["has_trust_issues"] and not context["discovered_lies"]:
            trust_lines = [
                f"{npc_name} seems guarded.",
                f"There's wariness in {npc_name}'s posture.",
                f"{npc_name} keeps their distance.",
            ]
            response_parts.append(random.choice(trust_lines))

        return " ".join(response_parts)

    def describe_scene_enhanced(
        self,
        location: str,
        mood: str = "neutral",
        scene_type: str = "arrival",
    ) -> str:
        """
        Generate an enhanced scene description with dramatic opening.

        Uses PacingEngine to add scene bangs when appropriate.

        Args:
            location: Scene location
            mood: Scene mood
            scene_type: Type of scene (arrival, combat, social, etc.)

        Returns:
            Dramatic scene description
        """
        # Check if we should add a scene bang
        suggestion = self.pacing.suggest_next_beat()
        use_bang = suggestion["recommended"] != BeatType.PAUSE

        parts = []

        # Add scene bang if appropriate
        if use_bang:
            bang = self.pacing.generate_scene_bang(scene_type, mood)
            parts.append(bang)

        # Base scene description
        base = super().describe_scene(location, mood, scene_type)
        parts.append(base)

        # Note the new scene
        self.pacing.new_scene(initial_tension=self.memory.tension_level)

        return "\n".join(parts)

    def get_pacing_suggestion(self) -> str:
        """Get a pacing suggestion for the current session state."""
        return self.pacing.format_status()

    def log_npc_promise(self, npc_name: str, promise: str) -> None:
        """Log a promise made to an NPC."""
        self.npc_tracker.log_promise(npc_name, promise)

    def log_npc_lie(self, npc_name: str, lie: str, truth: str = "") -> None:
        """Log a lie told to an NPC."""
        self.npc_tracker.log_lie(npc_name, lie, truth)

    def log_npc_conversation(
        self,
        npc_name: str,
        topic: str,
        summary: str = "",
        disposition_change: int = 0,
    ) -> None:
        """Log a conversation with an NPC."""
        self.npc_tracker.log_conversation(npc_name, topic, summary, disposition_change)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize enhanced responder state."""
        return {
            "npc_tracker": self.npc_tracker.to_dict(),
            "pacing_state": {
                "tension_level": self.pacing.state.tension_level,
                "current_beat": self.pacing.state.current_beat_type.value,
                "beats_since_pause": self.pacing.state.beats_since_pause,
                "total_beats": self.pacing.state.total_beats,
            },
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        memory: "SessionMemory",
        personality: Optional[GMPersonality] = None,
    ) -> "EnhancedResponder":
        """Deserialize enhanced responder state."""
        responder = cls(memory, personality)

        # Restore NPC tracker
        if "npc_tracker" in data:
            responder.npc_tracker = NPCMemoryTracker.from_dict(
                data["npc_tracker"], memory
            )

        # Restore pacing state
        if "pacing_state" in data:
            ps = data["pacing_state"]
            responder.pacing.state.tension_level = ps.get("tension_level", 3)
            responder.pacing.state.beats_since_pause = ps.get("beats_since_pause", 0)
            responder.pacing.state.total_beats = ps.get("total_beats", 0)
            beat_str = ps.get("current_beat", "pause")
            responder.pacing.state.current_beat_type = BeatType(beat_str)

        return responder
