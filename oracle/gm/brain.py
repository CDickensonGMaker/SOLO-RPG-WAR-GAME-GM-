"""
Game Master Brain - Central intelligence for the Oracle GM.

Coordinates personality, memory, and response generation to provide
a coherent, contextual Game Master experience.
"""

from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import random
import re

from oracle.gm.personality import GMPersonality, GMTone, GMStyle, PERSONALITIES
from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread
from oracle.gm.responder import NarrativeResponder


@dataclass
class OracleResult:
    """Result from an oracle query."""
    question: str
    answer: str           # yes_and, yes, yes_but, no_but, no, no_and
    answer_text: str      # Human readable
    roll: int
    chaos_factor: int
    interpretation: str   # GM's narrative interpretation
    random_event: bool    # Did this trigger a random event?
    random_event_text: str = ""


@dataclass
class DiceResult:
    """Result from a dice roll."""
    notation: str
    rolls: List[int]
    total: int
    description: str


class GameMasterBrain:
    """
    The central GM intelligence.

    Coordinates all subsystems to provide an intelligent, contextual
    Game Master that can:
    - Answer oracle questions with narrative flair
    - Track and remember session context
    - Generate appropriate NPCs, scenes, and events
    - Adapt tone and style to the game mood
    - Manage plot threads and story progression
    """

    def __init__(self, personality: GMPersonality = None,
                 memory: SessionMemory = None):
        self.personality = personality or PERSONALITIES["classic"]
        self.memory = memory or SessionMemory()
        self.responder = NarrativeResponder(self.personality)

        # Mode-specific handlers
        self._mode_handlers: Dict[str, Callable] = {}

        # Table data cache (loaded from TOML files)
        self._tables: Dict[str, Any] = {}

        # Event listeners
        self._listeners: Dict[str, List[Callable]] = {
            "oracle_result": [],
            "scene_change": [],
            "npc_interaction": [],
            "chaos_change": [],
            "thread_update": [],
        }

    # =========================================================================
    # Core Oracle System
    # =========================================================================

    def ask_oracle(self, question: str, likelihood: str = "even") -> OracleResult:
        """
        Ask a yes/no question to the oracle.

        Args:
            question: The yes/no question
            likelihood: Probability modifier (impossible, unlikely, even, likely, certain)

        Returns:
            OracleResult with answer and interpretation
        """
        # Record the question
        self.memory.add_message(f"[Oracle] {question}", "user")

        # Calculate roll
        roll = random.randint(1, 100)

        # Likelihood modifiers
        modifiers = {
            "impossible": -40,
            "very_unlikely": -20,
            "unlikely": -10,
            "even": 0,
            "likely": 10,
            "very_likely": 20,
            "certain": 40,
        }
        modifier = modifiers.get(likelihood, 0)

        # Chaos modifier
        chaos_mod = (self.memory.chaos_factor - 5) * 3

        modified_roll = roll + modifier + chaos_mod

        # Determine answer
        if modified_roll <= 10:
            answer = "no_and"
            answer_text = "NO, and..."
        elif modified_roll <= 30:
            answer = "no"
            answer_text = "NO"
        elif modified_roll <= 45:
            answer = "no_but"
            answer_text = "NO, but..."
        elif modified_roll <= 55:
            answer = "yes_but"
            answer_text = "YES, but..."
        elif modified_roll <= 75:
            answer = "yes"
            answer_text = "YES"
        else:
            answer = "yes_and"
            answer_text = "YES, and..."

        # Check for random event (extreme rolls)
        random_event = roll <= 5 or roll >= 95
        random_event_text = ""

        if random_event:
            # Determine event type based on the answer
            if answer in ["yes", "yes_and"]:
                event_type = random.choice(["positive", "neutral"])
            elif answer in ["no", "no_and"]:
                event_type = random.choice(["negative", "neutral"])
            else:
                event_type = "neutral"

            random_event_text = self.responder.random_event(event_type, self.memory)

        # Generate interpretation
        interpretation = self.responder.interpret_oracle(answer, question, self.memory)

        # Update chaos based on answer extremity
        if answer in ["yes_and", "no_and"]:
            self._adjust_chaos(1)
        elif answer in ["yes", "no"]:
            self._adjust_chaos(-1)

        result = OracleResult(
            question=question,
            answer=answer,
            answer_text=answer_text,
            roll=roll,
            chaos_factor=self.memory.chaos_factor,
            interpretation=interpretation,
            random_event=random_event,
            random_event_text=random_event_text
        )

        # Record the answer
        response = f"{answer_text}\n{interpretation}"
        if random_event:
            response += f"\n\n[Random Event!] {random_event_text}"

        self.memory.add_gm_response(response, {
            "type": "oracle",
            "answer": answer,
            "roll": roll
        })

        # Notify listeners
        self._emit("oracle_result", result)

        return result

    def _adjust_chaos(self, amount: int):
        """Adjust chaos factor with bounds."""
        old_chaos = self.memory.chaos_factor
        self.memory.chaos_factor = max(1, min(9, self.memory.chaos_factor + amount))

        if old_chaos != self.memory.chaos_factor:
            self._emit("chaos_change", self.memory.chaos_factor)
            self.personality.set_tone_from_context(self.memory.chaos_factor)

    # =========================================================================
    # Dice Rolling
    # =========================================================================

    def roll_dice(self, notation: str) -> DiceResult:
        """
        Roll dice using standard notation.

        Args:
            notation: Dice notation like "2d6+3", "1d20", "4d6kh3"

        Returns:
            DiceResult with rolls and total
        """
        # Parse notation
        match = re.match(r'(\d+)d(\d+)(?:(kh|kl)(\d+))?([+-]\d+)?', notation.lower())

        if not match:
            return DiceResult(notation, [0], 0, "Invalid notation")

        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        keep_type = match.group(3)
        keep_num = int(match.group(4)) if match.group(4) else None
        modifier = int(match.group(5)) if match.group(5) else 0

        # Roll the dice
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]

        # Apply keep highest/lowest
        working_rolls = rolls.copy()
        if keep_type == "kh" and keep_num:
            working_rolls = sorted(rolls, reverse=True)[:keep_num]
        elif keep_type == "kl" and keep_num:
            working_rolls = sorted(rolls)[:keep_num]

        total = sum(working_rolls) + modifier

        # Generate description
        rolls_str = ", ".join(str(r) for r in rolls)
        if keep_type:
            kept_str = ", ".join(str(r) for r in working_rolls)
            desc = f"Rolled [{rolls_str}], kept [{kept_str}]"
        else:
            desc = f"Rolled [{rolls_str}]"

        if modifier != 0:
            desc += f" {modifier:+d}"
        desc += f" = {total}"

        result = DiceResult(notation, rolls, total, desc)

        # Record the roll
        self.memory.add_roll("dice", result.description)

        return result

    # =========================================================================
    # Scene Management
    # =========================================================================

    def set_scene(self, location: str, description: str = "",
                  mood: str = "neutral", npcs: List[str] = None) -> str:
        """
        Set the current scene.

        Returns a narrative description of the scene.
        """
        self.memory.set_scene(
            location=location,
            description=description,
            mood=mood,
            npcs=npcs or []
        )

        # Update personality tone based on mood
        mood_to_tone = {
            "peaceful": GMTone.HOPEFUL,
            "tense": GMTone.URGENT,
            "dangerous": GMTone.OMINOUS,
            "mysterious": GMTone.MYSTERIOUS,
            "neutral": GMTone.NEUTRAL,
        }
        self.personality.current_tone = mood_to_tone.get(mood, GMTone.NEUTRAL)

        # Generate scene description
        response = self.responder.describe_scene(location, mood, "arrival")

        self.memory.add_gm_response(response, {"type": "scene_change"})
        self._emit("scene_change", self.memory.current_scene)

        return response

    def describe_current_scene(self) -> str:
        """Get a description of the current scene."""
        scene = self.memory.current_scene
        return self.responder.describe_scene(
            scene["location"],
            scene["mood"],
            "transition"
        )

    # =========================================================================
    # NPC Management
    # =========================================================================

    def introduce_npc(self, name: str, description: str = "",
                      traits: List[str] = None, disposition: int = 0) -> str:
        """
        Introduce a new NPC to the session.

        Returns a narrative introduction.
        """
        # Track the NPC
        entity = self.memory.track_entity(
            name=name,
            entity_type="npc",
            description=description,
            traits=traits,
            disposition=disposition
        )

        # Add to current scene
        current_npcs = self.memory.current_scene.get("present_npcs", [])
        if name not in current_npcs:
            current_npcs.append(name)
            self.memory.current_scene["present_npcs"] = current_npcs

        # Generate introduction
        response = self.responder.npc_interaction(name, disposition, "greeting")

        self.memory.add_gm_response(response, {"type": "npc_intro", "npc": name})
        self._emit("npc_interaction", entity)

        return response

    def npc_speaks(self, npc_name: str, topic: str = "") -> str:
        """Generate NPC dialogue on a topic."""
        entity = self.memory.get_entity(npc_name)
        disposition = entity.disposition if entity else 0

        response = self.responder.npc_interaction(npc_name, disposition, "greeting")

        self.memory.add_gm_response(response, {"type": "npc_dialogue", "npc": npc_name})

        return response

    def adjust_npc_disposition(self, npc_name: str, amount: int,
                               reason: str = "") -> str:
        """Adjust NPC disposition toward the player."""
        entity = self.memory.get_entity(npc_name)
        if entity:
            old_disp = entity.disposition
            entity.disposition = max(-100, min(100, entity.disposition + amount))

            if reason:
                entity.notes.append(f"[{amount:+d}] {reason}")

            # Generate reaction
            if amount > 0:
                response = self.responder.npc_interaction(npc_name, entity.disposition, "reaction_positive")
            else:
                response = self.responder.npc_interaction(npc_name, entity.disposition, "reaction_negative")

            self.memory.add_gm_response(response)
            return response

        return f"Unknown NPC: {npc_name}"

    # =========================================================================
    # Thread/Plot Management
    # =========================================================================

    def add_thread(self, name: str, description: str, importance: int = 5) -> str:
        """Add a new plot thread."""
        thread = self.memory.add_thread(name, description, importance)

        response = f"New thread established: {name}. {description}"
        self.memory.add_gm_response(response, {"type": "thread_add"})
        self._emit("thread_update", thread)

        return response

    def advance_thread(self, name: str, development: str) -> str:
        """Advance a plot thread with new development."""
        self.memory.update_thread(name, development)

        response = f"Thread '{name}' advances: {development}"
        self.memory.add_gm_response(response, {"type": "thread_advance"})

        return response

    def resolve_thread(self, name: str, resolution: str = "") -> str:
        """Mark a plot thread as resolved."""
        self.memory.resolve_thread(name)

        response = f"Thread '{name}' resolved. {resolution}"
        self.memory.add_gm_response(response, {"type": "thread_resolve"})

        # Adjust chaos down for resolution
        self._adjust_chaos(-1)

        return response

    # =========================================================================
    # Conversation Interface
    # =========================================================================

    def process_input(self, user_input: str) -> str:
        """
        Process user input and generate appropriate response.

        This is the main conversational interface.
        """
        # Record user input
        self.memory.add_message(user_input, "user")

        input_lower = user_input.lower().strip()

        # Check for specific commands/intents
        # Oracle questions (questions ending with ?)
        if input_lower.endswith("?") and not input_lower.startswith("/"):
            # Determine if it's a yes/no question
            yes_no_starters = ["is", "are", "do", "does", "did", "will", "would",
                               "could", "can", "should", "has", "have", "was", "were"]
            first_word = input_lower.split()[0] if input_lower.split() else ""

            if first_word in yes_no_starters:
                result = self.ask_oracle(user_input.rstrip("?"))
                return f"**{result.answer_text}**\n\n{result.interpretation}"

        # Look/describe commands
        if any(cmd in input_lower for cmd in ["look", "describe", "where am i"]):
            return self.describe_current_scene()

        # Status/summary commands
        if any(cmd in input_lower for cmd in ["status", "summary", "what's happening"]):
            return self._get_status_summary()

        # Chaos adjustment
        if "increase chaos" in input_lower:
            self._adjust_chaos(1)
            return f"Chaos increased to {self.memory.chaos_factor}. The fates grow more uncertain."

        if "decrease chaos" in input_lower:
            self._adjust_chaos(-1)
            return f"Chaos decreased to {self.memory.chaos_factor}. Order reasserts itself."

        # General conversation - use responder
        response = self.responder.generate_response(user_input, self.memory)
        self.memory.add_gm_response(response)

        return response

    def _get_status_summary(self) -> str:
        """Generate a status summary."""
        parts = []

        # Scene
        scene = self.memory.current_scene
        parts.append(f"**Location:** {scene['location']}")
        parts.append(f"**Mood:** {scene['mood'].title()}")
        parts.append(f"**Time:** {scene['time_of_day'].title()}, {scene['weather'].title()}")

        # Present NPCs
        if scene.get("present_npcs"):
            parts.append(f"**Present:** {', '.join(scene['present_npcs'])}")

        # Active threads
        threads = self.memory.get_active_threads()
        if threads:
            thread_list = [f"- {t.name}" for t in threads[:5]]
            parts.append(f"**Active Threads:**\n" + "\n".join(thread_list))

        # Chaos
        parts.append(f"**Chaos Factor:** {self.memory.chaos_factor}")

        return "\n".join(parts)

    # =========================================================================
    # Greeting and Session Management
    # =========================================================================

    def greet(self) -> str:
        """Generate a greeting for session start."""
        greeting = self.personality.get_greeting()
        self.memory.add_gm_response(greeting, {"type": "greeting"})
        return greeting

    def get_mode(self) -> str:
        """Get current game mode."""
        return self.memory.mode

    def set_mode(self, mode: str):
        """Set game mode (rpg, wargame, birthright)."""
        self.memory.mode = mode

        # Adjust personality for mode
        if mode == "wargame":
            self.personality = PERSONALITIES.get("war_commander", self.personality)
        elif mode == "birthright":
            self.personality = PERSONALITIES.get("classic", self.personality)
        else:
            self.personality = PERSONALITIES.get("classic", self.personality)

        self.responder = NarrativeResponder(self.personality)

    def set_setting(self, setting: str):
        """Set the game setting."""
        self.memory.setting = setting

    # =========================================================================
    # Event System
    # =========================================================================

    def on(self, event: str, callback: Callable):
        """Register event listener."""
        if event in self._listeners:
            self._listeners[event].append(callback)

    def _emit(self, event: str, data: Any):
        """Emit event to listeners."""
        for callback in self._listeners.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Event handler error: {e}")

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_session(self, path: str):
        """Save the current session."""
        self.memory.save(path)

    def load_session(self, path: str):
        """Load a saved session."""
        self.memory = SessionMemory.load(path)
        self.responder = NarrativeResponder(self.personality)

    def get_history(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        entries = self.memory.get_recent_context(count)
        return [e.to_dict() for e in entries]
