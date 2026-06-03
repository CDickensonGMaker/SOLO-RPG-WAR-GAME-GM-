"""
Pacing Engine - Dramatic rhythm for solo RPG sessions.

Tracks narrative tension, scene energy states, and suggests dramatic beats
to create the natural ebb and flow of a good story. Based on TTRPG pacing
techniques: Push/Pause/Pull rhythm, tension ladders, and scene bangs.

Key Concepts:
- PUSH: Action, pressure, stakes rising - things are happening NOW
- PAUSE: Breathing room, character moments, recovery
- PULL: Revelation, mystery deepens, new hooks draw players forward

The 3:1 Rule: For dramatic scenes, roughly 3 tension beats per rest beat.

Usage:
    engine = PacingEngine()
    engine.log_beat("push", tension_delta=1)
    suggestion = engine.suggest_next_beat()
    bang = engine.generate_scene_bang("arrival", context="combat")
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any
import tomllib


class BeatType(Enum):
    """Scene energy states following Push/Pause/Pull pacing."""
    PUSH = "push"    # Action, pressure, stakes rising
    PAUSE = "pause"  # Breathing room, character moments
    PULL = "pull"    # Revelation, mystery, new hooks


class ScenePhase(Enum):
    """Where we are in the dramatic arc of a scene."""
    OPENING = "opening"       # Scene just started
    RISING = "rising"         # Building toward something
    CLIMAX = "climax"         # Peak tension moment
    FALLING = "falling"       # After the climax
    RESOLUTION = "resolution" # Wrapping up


@dataclass
class Beat:
    """A single dramatic beat in the session."""
    beat_type: BeatType
    tension_delta: int  # How much this changed tension (-2 to +2)
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PacingState:
    """Current pacing state for the session."""
    tension_level: int = 3          # 1-5 scale (1=calm, 5=critical)
    current_beat_type: BeatType = BeatType.PAUSE
    scene_phase: ScenePhase = ScenePhase.OPENING
    beats_since_pause: int = 0      # Track how long since rest
    beats_since_push: int = 0       # Track how long since action
    total_beats: int = 0
    beat_history: List[Beat] = field(default_factory=list)


class PacingEngine:
    """
    Manages dramatic pacing for solo RPG sessions.

    Tracks tension, suggests beat types, generates scene bangs,
    and helps maintain the Push/Pause/Pull rhythm that makes
    stories feel dynamic rather than monotonous.
    """

    # Tension level descriptions
    TENSION_DESCRIPTIONS = {
        1: "Calm - safe moment, low stakes",
        2: "Watchful - something could happen",
        3: "Tense - active situation, stakes present",
        4: "Critical - major stakes, pressure mounting",
        5: "Crisis - everything on the line, no margin for error",
    }

    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize the pacing engine.

        Args:
            data_path: Path to pacing.toml. Defaults to oracle/data/core/pacing.toml
        """
        self.state = PacingState()

        if data_path is None:
            data_path = Path(__file__).parent.parent / "data" / "core" / "pacing.toml"

        self.data_path = data_path
        self.scene_bangs: Dict[str, List[str]] = {}
        self.transitions: Dict[str, List[str]] = {}
        self._load_pacing_data()

    def _load_pacing_data(self) -> None:
        """Load scene bangs and transitions from TOML."""
        if not self.data_path.exists():
            self._use_defaults()
            return

        try:
            with open(self.data_path, "rb") as f:
                data = tomllib.load(f)

            # Load scene bangs
            if "scene_bangs" in data:
                for category, entries in data["scene_bangs"].items():
                    if isinstance(entries, list):
                        self.scene_bangs[category] = entries

            # Load transitions
            if "transitions" in data:
                for trans_type, entries in data["transitions"].items():
                    if isinstance(entries, list):
                        self.transitions[trans_type] = entries

        except Exception as e:
            print(f"Warning: Could not load pacing data: {e}")
            self._use_defaults()

    def _use_defaults(self) -> None:
        """Use default scene bangs if TOML not available."""
        self.scene_bangs = {
            "combat": [
                "Weapons are already drawn when you arrive",
                "The first blow lands before you can react",
                "You walk into an ambush in progress",
            ],
            "social": [
                "An argument is already underway",
                "Someone important is leaving as you enter",
                "The room falls silent when they see you",
            ],
            "exploration": [
                "Something is wrong here - you sense it immediately",
                "Evidence of recent violence greets you",
                "The door was already open. It shouldn't be.",
            ],
            "arrival": [
                "You're not the first to arrive",
                "The place is not as you expected",
                "Something has changed since you were last here",
            ],
        }

        self.transitions = {
            "escalate": [
                "Things are about to get worse",
                "The situation intensifies",
                "No turning back now",
            ],
            "de_escalate": [
                "The immediate danger passes",
                "A moment to catch your breath",
                "The pressure eases, for now",
            ],
            "reveal": [
                "And then you see it",
                "The truth becomes clear",
                "Everything changes with this revelation",
            ],
        }

    def log_beat(
        self,
        beat_type: str | BeatType,
        tension_delta: int = 0,
        description: str = ""
    ) -> None:
        """
        Log a dramatic beat that just occurred.

        Args:
            beat_type: "push", "pause", or "pull" (or BeatType enum)
            tension_delta: How much tension changed (-2 to +2)
            description: Optional description of what happened
        """
        if isinstance(beat_type, str):
            beat_type = BeatType(beat_type.lower())

        # Clamp tension delta
        tension_delta = max(-2, min(2, tension_delta))

        # Create beat record
        beat = Beat(
            beat_type=beat_type,
            tension_delta=tension_delta,
            description=description,
        )
        self.state.beat_history.append(beat)
        self.state.total_beats += 1

        # Update tension level
        self.state.tension_level = max(1, min(5,
            self.state.tension_level + tension_delta
        ))

        # Update beat counters
        self.state.current_beat_type = beat_type
        if beat_type == BeatType.PAUSE:
            self.state.beats_since_pause = 0
        else:
            self.state.beats_since_pause += 1

        if beat_type == BeatType.PUSH:
            self.state.beats_since_push = 0
        else:
            self.state.beats_since_push += 1

        # Update scene phase based on pattern
        self._update_scene_phase()

    def _update_scene_phase(self) -> None:
        """Infer scene phase from recent beats."""
        if self.state.total_beats <= 2:
            self.state.scene_phase = ScenePhase.OPENING
        elif self.state.tension_level >= 5:
            self.state.scene_phase = ScenePhase.CLIMAX
        elif self.state.tension_level >= 4:
            self.state.scene_phase = ScenePhase.RISING
        elif self.state.current_beat_type == BeatType.PAUSE:
            if self.state.scene_phase == ScenePhase.CLIMAX:
                self.state.scene_phase = ScenePhase.FALLING
        elif self.state.tension_level <= 2:
            self.state.scene_phase = ScenePhase.RESOLUTION

    def suggest_next_beat(self) -> Dict[str, Any]:
        """
        Suggest what type of beat should come next based on pacing rules.

        Returns:
            Dictionary with suggested beat type, reasoning, and options
        """
        suggestion = {
            "recommended": BeatType.PUSH,
            "alternatives": [],
            "reasoning": "",
            "tension_suggestion": 0,
        }

        # 3:1 Rule - need a pause after sustained tension
        if self.state.beats_since_pause >= 3:
            suggestion["recommended"] = BeatType.PAUSE
            suggestion["reasoning"] = "Time for a breather - 3+ beats of tension"
            suggestion["tension_suggestion"] = -1
            suggestion["alternatives"] = [BeatType.PULL]
            return suggestion

        # Stuck in pause too long
        if self.state.beats_since_push >= 2 and self.state.current_beat_type == BeatType.PAUSE:
            suggestion["recommended"] = BeatType.PUSH
            suggestion["reasoning"] = "Action needed - scene is stalling"
            suggestion["tension_suggestion"] = 1
            suggestion["alternatives"] = [BeatType.PULL]
            return suggestion

        # Low tension - build it up
        if self.state.tension_level <= 2:
            suggestion["recommended"] = BeatType.PULL
            suggestion["reasoning"] = "Low tension - introduce mystery or hook"
            suggestion["tension_suggestion"] = 1
            suggestion["alternatives"] = [BeatType.PUSH]
            return suggestion

        # High tension - maintain or push to climax
        if self.state.tension_level >= 4:
            if self.state.scene_phase != ScenePhase.CLIMAX:
                suggestion["recommended"] = BeatType.PUSH
                suggestion["reasoning"] = "High tension - push toward climax"
                suggestion["tension_suggestion"] = 1
            else:
                suggestion["recommended"] = BeatType.PAUSE
                suggestion["reasoning"] = "At climax - resolution or breathing room"
                suggestion["tension_suggestion"] = -1
            return suggestion

        # Middle tension - variety is good
        if self.state.current_beat_type == BeatType.PUSH:
            suggestion["recommended"] = BeatType.PULL
            suggestion["reasoning"] = "After action, add mystery or revelation"
            suggestion["alternatives"] = [BeatType.PUSH, BeatType.PAUSE]
        elif self.state.current_beat_type == BeatType.PULL:
            suggestion["recommended"] = BeatType.PUSH
            suggestion["reasoning"] = "Mystery revealed - time for action"
            suggestion["alternatives"] = [BeatType.PAUSE]
        else:
            suggestion["recommended"] = BeatType.PUSH
            suggestion["reasoning"] = "After rest, resume action"
            suggestion["alternatives"] = [BeatType.PULL]

        return suggestion

    def generate_scene_bang(
        self,
        scene_type: str = "arrival",
        context: str = "",
        rng: Optional[random.Random] = None
    ) -> str:
        """
        Generate a dramatic opening hook for a scene.

        Scene bangs "frame past the entrance" - they skip boring setup
        and start at the interesting part.

        Args:
            scene_type: Type of scene (arrival, combat, social, exploration)
            context: Additional context for selection
            rng: Optional random generator

        Returns:
            A dramatic scene opening hook
        """
        if rng is None:
            rng = random.Random()

        # Try specific scene type first
        if scene_type in self.scene_bangs:
            return rng.choice(self.scene_bangs[scene_type])

        # Try context as fallback
        if context in self.scene_bangs:
            return rng.choice(self.scene_bangs[context])

        # Generic fallback
        all_bangs = []
        for bangs in self.scene_bangs.values():
            all_bangs.extend(bangs)

        if all_bangs:
            return rng.choice(all_bangs)

        return "Something is immediately wrong."

    def get_transition(
        self,
        transition_type: str = "escalate",
        rng: Optional[random.Random] = None
    ) -> str:
        """
        Get a transition phrase for scene shifts.

        Args:
            transition_type: "escalate", "de_escalate", or "reveal"
            rng: Optional random generator

        Returns:
            A transition phrase
        """
        if rng is None:
            rng = random.Random()

        if transition_type in self.transitions:
            return rng.choice(self.transitions[transition_type])

        return ""

    def get_tension_description(self) -> str:
        """Get a description of the current tension level."""
        return self.TENSION_DESCRIPTIONS.get(
            self.state.tension_level,
            f"Tension level {self.state.tension_level}"
        )

    def new_scene(self, initial_tension: int = 3) -> None:
        """
        Start a new scene, resetting beat counters but preserving history.

        Args:
            initial_tension: Starting tension level for the new scene (1-5)
        """
        self.state.tension_level = max(1, min(5, initial_tension))
        self.state.scene_phase = ScenePhase.OPENING
        self.state.beats_since_pause = 0
        self.state.beats_since_push = 0
        self.state.current_beat_type = BeatType.PAUSE

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current pacing state."""
        return {
            "tension_level": self.state.tension_level,
            "tension_description": self.get_tension_description(),
            "current_beat": self.state.current_beat_type.value,
            "scene_phase": self.state.scene_phase.value,
            "beats_since_pause": self.state.beats_since_pause,
            "beats_since_push": self.state.beats_since_push,
            "total_beats": self.state.total_beats,
            "needs_pause": self.state.beats_since_pause >= 3,
            "needs_action": self.state.beats_since_push >= 2,
        }

    def format_status(self) -> str:
        """Format current pacing status for display."""
        state = self.get_state_summary()
        suggestion = self.suggest_next_beat()

        lines = [
            f"Tension: {'*' * state['tension_level']}{'.' * (5 - state['tension_level'])} ({state['tension_description']})",
            f"Phase: {state['scene_phase'].replace('_', ' ').title()}",
            f"Last beat: {state['current_beat'].upper()}",
        ]

        if state['needs_pause']:
            lines.append("! Time for a breather")
        elif state['needs_action']:
            lines.append("! Scene needs action")

        lines.append(f"Suggested: {suggestion['recommended'].value.upper()} - {suggestion['reasoning']}")

        return "\n".join(lines)


# Add scene bangs to existing pacing.toml
SCENE_BANGS_TOML = '''
# Scene Bangs - Dramatic opening hooks that "frame past the entrance"
# Skip boring setup and start at the interesting part

[scene_bangs]
arrival = [
    "You're not the first to arrive",
    "The place is not as you expected",
    "Something has changed since you were last here",
    "The door stands open. It shouldn't be.",
    "Fresh tracks lead away from here",
    "The silence is wrong",
]

combat = [
    "Weapons are already drawn when you arrive",
    "The first blow lands before you can react",
    "You walk into an ambush in progress",
    "The bodies aren't cold yet",
    "Steel rings against steel somewhere close",
    "They were expecting you",
    "The trap springs before you see it",
]

social = [
    "An argument is already underway",
    "Someone important is leaving as you enter",
    "The room falls silent when they see you",
    "They've been talking about you",
    "A deal is being struck without you",
    "Tears are being shed",
    "The gathering has a funeral atmosphere",
]

exploration = [
    "Something is wrong here - you sense it immediately",
    "Evidence of recent violence greets you",
    "The path has been deliberately blocked",
    "Warning signs are everywhere, but too late",
    "Someone else has been here recently",
    "The map was wrong about this",
    "Nature has reclaimed this place violently",
]

chase = [
    "They've already spotted you",
    "The pursuit is already underway",
    "You hear them closing in",
    "The only exit is blocked",
    "You're being herded somewhere",
]

mystery = [
    "The clue is obvious now that you see it",
    "Someone left this for you to find",
    "The answer raises more questions",
    "Two pieces finally connect",
    "The pattern becomes clear",
]

[transitions]
escalate = [
    "Things are about to get worse",
    "The situation intensifies",
    "No turning back now",
    "And then it gets complicated",
    "But that's not the worst of it",
]

de_escalate = [
    "The immediate danger passes",
    "A moment to catch your breath",
    "The pressure eases, for now",
    "Silence returns",
    "The crisis point passes",
]

reveal = [
    "And then you see it",
    "The truth becomes clear",
    "Everything changes with this revelation",
    "Understanding dawns",
    "The pieces fall into place",
]

interrupt = [
    "But before you can act—",
    "Suddenly—",
    "Without warning—",
    "That's when everything changes",
    "But fate has other plans",
]
'''
