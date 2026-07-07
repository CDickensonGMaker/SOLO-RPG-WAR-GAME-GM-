"""
Meaning Tables - Mythic-style Action + Subject combinations.

Generates surprising, specific interpretations for oracle results by combining
action verbs with subject nouns. This creates emergent narrative that feels
discovered rather than authored.

Example:
    "Is the door locked?" -> YES, AND...
    Rolls: "Reveals" + "The Enemy"
    Interpretation: "Yes, and as you check the lock, you notice fresh
    scratches - someone else has been trying to get in. The enemy knows
    about this place."

Usage:
    reader = MeaningTableReader()
    action, subject = reader.roll_meaning(context="exploration")
    interpretation = reader.interpret(action, subject, situation)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any, TYPE_CHECKING
import tomllib

if TYPE_CHECKING:
    from oracle.gm.memory import SessionMemory


@dataclass
class MeaningEntry:
    """A single action or subject entry from the meaning tables."""
    word: str
    category: List[str]
    weight: int = 1
    synonyms: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class MeaningRoll:
    """Result of rolling on meaning tables."""
    action: MeaningEntry
    subject: MeaningEntry
    raw_combination: str  # e.g., "Reveals + The Secret"
    interpreted: str = ""  # Filled in by interpret()


class MeaningTableReader:
    """
    Loads and rolls on Mythic-style meaning tables.

    Combines Action verbs with Subject nouns to generate surprising
    interpretations for oracle results. Context filtering ensures
    combat questions get combat-relevant meanings, etc.
    """

    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize the meaning table reader.

        Args:
            data_path: Path to data directory. Defaults to oracle/data/core/meaning_tables/
        """
        if data_path is None:
            data_path = Path(__file__).parent.parent / "data" / "core" / "meaning_tables"

        self.data_path = data_path
        self.actions: List[MeaningEntry] = []
        self.subjects: List[MeaningEntry] = []
        self._load_tables()

    def _load_tables(self) -> None:
        """Load action and subject tables from TOML files."""
        actions_path = self.data_path / "actions.toml"
        subjects_path = self.data_path / "subjects.toml"

        if actions_path.exists():
            self.actions = self._load_table(actions_path, "actions")

        if subjects_path.exists():
            self.subjects = self._load_table(subjects_path, "subjects")

    def _load_table(self, path: Path, key: str) -> List[MeaningEntry]:
        """Load a single meaning table from TOML."""
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            entries = []
            for item in data.get(key, []):
                entry = MeaningEntry(
                    word=item.get("word", ""),
                    category=item.get("category", ["core"]),
                    weight=item.get("weight", 1),
                    synonyms=item.get("synonyms", []),
                    examples=item.get("examples", []),
                )
                entries.append(entry)
            return entries

        except Exception as e:
            print(f"Warning: Could not load meaning table {path}: {e}")
            return []

    def roll_meaning(
        self,
        context: Optional[str] = None,
        rng: Optional[random.Random] = None
    ) -> MeaningRoll:
        """
        Roll on meaning tables to get an Action + Subject combination.

        Args:
            context: Optional context to weight results ("combat", "social", "exploration")
            rng: Optional random generator for testing

        Returns:
            MeaningRoll with action, subject, and raw combination string
        """
        if rng is None:
            rng = random.Random()

        action = self._weighted_choice(self.actions, context, rng)
        subject = self._weighted_choice(self.subjects, context, rng)

        return MeaningRoll(
            action=action,
            subject=subject,
            raw_combination=f"{action.word} + {subject.word}",
        )

    def _weighted_choice(
        self,
        entries: List[MeaningEntry],
        context: Optional[str],
        rng: random.Random
    ) -> MeaningEntry:
        """
        Choose an entry with weighting, optionally filtered by context.

        Entries matching the context get their weight doubled.
        """
        if not entries:
            # Fallback if tables didn't load
            return MeaningEntry(word="Changes", category=["core"])

        # Calculate weights - boost entries matching context
        weights = []
        for entry in entries:
            weight = entry.weight
            if context and context in entry.category:
                weight *= 2  # Double weight for matching context
            weights.append(weight)

        return rng.choices(entries, weights=weights, k=1)[0]

    def interpret(
        self,
        meaning: MeaningRoll,
        situation: str = "",
        memory: Optional["SessionMemory"] = None,
    ) -> str:
        """
        Generate an interpretation of the meaning roll for the situation.

        This is the key creative step - taking abstract Action + Subject
        and grounding it in the current fiction.

        Args:
            meaning: The MeaningRoll to interpret
            situation: The current situation/question being answered
            memory: Optional session memory for fiction-aware interpretation

        Returns:
            A narrative interpretation string
        """
        action = meaning.action.word.lower()
        subject = meaning.subject.word

        # Build context from memory if available
        context_elements = []
        if memory:
            # Get active NPCs
            present_npcs = [e.name for e in memory.entities.values()
                           if e.entity_type == "npc" and e.attributes.get("present", False)]
            if present_npcs:
                context_elements.append(f"NPCs present: {', '.join(present_npcs[:3])}")

            # Get active plot threads
            active_threads = [t.name for t in memory.threads.values()
                            if t.status == "active"]
            if active_threads:
                context_elements.append(f"Active threads: {', '.join(active_threads[:2])}")

            # Current location
            if memory.current_scene.get("location"):
                context_elements.append(f"Location: {memory.current_scene['location']}")

        # Generate interpretation prompt (for future LLM enhancement)
        # For now, return a structured hint for the player to interpret
        interpretation = f"[{meaning.raw_combination}]"

        # Add synonyms for variety
        if meaning.action.synonyms:
            alt_action = random.choice(meaning.action.synonyms)
            interpretation += f" ({alt_action})"

        return interpretation

    def get_elaboration(
        self,
        oracle_result: str,
        context: str = "",
        memory: Optional["SessionMemory"] = None,
    ) -> Dict[str, Any]:
        """
        Generate a full elaboration for an oracle result.

        This is the main entry point - call this when you need to
        elaborate on YES_AND, YES_BUT, etc.

        Args:
            oracle_result: The oracle answer (yes_and, yes_but, no_and, no_but)
            context: Current context (combat, social, exploration)
            memory: Session memory for fiction-aware elaboration

        Returns:
            Dictionary with meaning roll and suggested elaboration
        """
        meaning = self.roll_meaning(context=context)

        # Determine elaboration tone based on oracle result
        if oracle_result in ["yes_and", "no_but"]:
            tone = "favorable"  # Things improve or get complicated in interesting ways
        elif oracle_result in ["yes_but", "no_and"]:
            tone = "complication"  # Things get harder or have catches
        else:
            tone = "neutral"

        # Build elaboration
        elaboration = {
            "meaning": meaning,
            "action": meaning.action.word,
            "subject": meaning.subject.word,
            "combination": meaning.raw_combination,
            "tone": tone,
            "context": context,
        }

        # Add fiction-specific elements if memory available
        if memory:
            elaboration["fiction_elements"] = self._get_fiction_elements(
                meaning, memory, tone
            )

        return elaboration

    def _get_fiction_elements(
        self,
        meaning: MeaningRoll,
        memory: "SessionMemory",
        tone: str
    ) -> Dict[str, Any]:
        """
        Pull relevant fiction elements that could be affected by this meaning.

        Looks at the action/subject and finds NPCs, locations, or threads
        that could reasonably be connected.
        """
        elements = {
            "suggested_npcs": [],
            "suggested_threads": [],
            "suggested_locations": [],
        }

        action_word = meaning.action.word.lower()
        subject_word = meaning.subject.word.lower()

        # Find NPCs that might be relevant
        for entity in memory.entities.values():
            if entity.entity_type != "npc":
                continue

            # Check if NPC traits/role match the subject
            npc_text = f"{entity.name} {entity.description} {' '.join(entity.traits)}".lower()

            # Subject matching
            if "enemy" in subject_word and entity.disposition < -20:
                elements["suggested_npcs"].append(entity.name)
            elif "ally" in subject_word and entity.disposition > 20:
                elements["suggested_npcs"].append(entity.name)
            elif "stranger" in subject_word and not entity.attributes.get("known", True):
                elements["suggested_npcs"].append(entity.name)
            elif "authority" in subject_word and any(
                role in npc_text for role in ["lord", "captain", "priest", "ruler", "king", "queen"]
            ):
                elements["suggested_npcs"].append(entity.name)

            # Action matching
            if "betray" in action_word and entity.attributes.get("trusted", False):
                elements["suggested_npcs"].append(entity.name)
            elif "reveal" in action_word and entity.attributes.get("knows_secret", False):
                elements["suggested_npcs"].append(entity.name)

        # Find relevant plot threads
        for thread in memory.threads.values():
            if thread.status != "active":
                continue

            thread_text = f"{thread.name} {thread.description}".lower()

            if "secret" in subject_word and "secret" in thread_text:
                elements["suggested_threads"].append(thread.name)
            elif "promise" in subject_word and any(
                word in thread_text for word in ["promise", "oath", "vow", "deal"]
            ):
                elements["suggested_threads"].append(thread.name)
            elif "war" in subject_word and any(
                word in thread_text for word in ["war", "battle", "conflict", "fight"]
            ):
                elements["suggested_threads"].append(thread.name)

        # Deduplicate
        elements["suggested_npcs"] = list(set(elements["suggested_npcs"]))[:3]
        elements["suggested_threads"] = list(set(elements["suggested_threads"]))[:2]

        return elements

    def format_for_display(self, elaboration: Dict[str, Any]) -> str:
        """
        Format an elaboration dictionary for display to the player.

        Args:
            elaboration: Result from get_elaboration()

        Returns:
            Formatted string for display
        """
        lines = []

        # Main meaning
        lines.append(f"Meaning: {elaboration['combination']}")

        # Tone indicator
        tone_emoji = {
            "favorable": "+",
            "complication": "!",
            "neutral": "~",
        }
        lines.append(f"Tone: {tone_emoji.get(elaboration['tone'], '?')} {elaboration['tone']}")

        # Fiction connections
        if "fiction_elements" in elaboration:
            fe = elaboration["fiction_elements"]
            if fe.get("suggested_npcs"):
                lines.append(f"Connected NPCs: {', '.join(fe['suggested_npcs'])}")
            if fe.get("suggested_threads"):
                lines.append(f"Related threads: {', '.join(fe['suggested_threads'])}")

        return "\n".join(lines)


# Convenience function for quick rolls
def roll_meaning(context: Optional[str] = None) -> MeaningRoll:
    """Quick function to roll on meaning tables."""
    reader = MeaningTableReader()
    return reader.roll_meaning(context=context)
