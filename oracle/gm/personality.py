"""
GM Personality - Defines how the Game Master communicates and behaves.

The personality system allows the GM to adapt its tone, verbosity,
and style based on the current game mode and user preferences.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import random


class GMStyle(Enum):
    """Communication style of the GM."""
    TERSE = "terse"           # Brief, to the point
    STANDARD = "standard"     # Balanced responses
    VERBOSE = "verbose"       # Detailed, descriptive
    DRAMATIC = "dramatic"     # Theatrical, intense
    CASUAL = "casual"         # Friendly, relaxed


class GMTone(Enum):
    """Emotional tone of the GM."""
    NEUTRAL = "neutral"
    OMINOUS = "ominous"
    HOPEFUL = "hopeful"
    MYSTERIOUS = "mysterious"
    URGENT = "urgent"
    PLAYFUL = "playful"


@dataclass
class GMPersonality:
    """
    Defines the Game Master's personality and communication style.

    The personality affects how the GM phrases responses, interprets
    oracle results, and describes scenes and events.
    """

    # Core personality traits
    style: GMStyle = GMStyle.STANDARD
    formality: float = 0.5  # 0 = very casual, 1 = very formal
    verbosity: float = 0.5  # 0 = terse, 1 = verbose
    drama: float = 0.5      # 0 = understated, 1 = dramatic

    # Dynamic tone (changes based on game state)
    current_tone: GMTone = GMTone.NEUTRAL

    # Name/identity
    name: str = "The Oracle"

    # Response templates by category
    greetings: List[str] = field(default_factory=lambda: [
        "Greetings, traveler. What tale shall we weave today?",
        "Welcome back. The fates await your questions.",
        "I am here. Speak, and the Oracle shall answer.",
        "The threads of destiny stir. How may I guide you?",
    ])

    affirmations: List[str] = field(default_factory=lambda: [
        "It is done.",
        "So it shall be.",
        "The fates have spoken.",
        "As you wish.",
        "Very well.",
    ])

    uncertainty_phrases: List[str] = field(default_factory=lambda: [
        "The mists obscure the answer...",
        "Even the Oracle cannot see all ends.",
        "The threads tangle here.",
        "Fate is uncertain on this matter.",
    ])

    # Transition phrases for narrative flow
    transitions: Dict[str, List[str]] = field(default_factory=lambda: {
        "meanwhile": [
            "Meanwhile...",
            "Elsewhere...",
            "At the same time...",
            "As this unfolds...",
        ],
        "later": [
            "Time passes...",
            "Later...",
            "After a time...",
            "When next we look...",
        ],
        "consequence": [
            "And so it follows that...",
            "The consequences ripple outward...",
            "This sets in motion...",
            "From this action springs...",
        ],
        "revelation": [
            "But wait—",
            "However...",
            "Yet something more lurks beneath...",
            "But there is more to this tale...",
        ],
    })

    def get_greeting(self) -> str:
        """Get a random greeting."""
        return random.choice(self.greetings)

    def get_affirmation(self) -> str:
        """Get a random affirmation."""
        return random.choice(self.affirmations)

    def get_uncertainty(self) -> str:
        """Get a random uncertainty phrase."""
        return random.choice(self.uncertainty_phrases)

    def get_transition(self, transition_type: str) -> str:
        """Get a transition phrase of the specified type."""
        phrases = self.transitions.get(transition_type, ["..."])
        return random.choice(phrases)

    def adjust_for_tone(self, text: str) -> str:
        """Adjust text based on current tone."""
        if self.current_tone == GMTone.OMINOUS:
            # Add ominous flavor
            prefixes = ["Darkly, ", "Ominously, ", "With foreboding, "]
            if random.random() < 0.3:
                text = random.choice(prefixes) + text.lower()
        elif self.current_tone == GMTone.URGENT:
            # Add urgency
            if not text.endswith("!"):
                text = text.rstrip(".") + "!"
        elif self.current_tone == GMTone.MYSTERIOUS:
            # Add mystery
            suffixes = ["...", " But is that the whole truth?", " Or so it seems."]
            if random.random() < 0.3:
                text = text.rstrip(".") + random.choice(suffixes)

        return text

    def format_response(self, text: str) -> str:
        """Format a response according to personality settings."""
        # Adjust verbosity
        if self.verbosity < 0.3 and len(text) > 100:
            # Truncate verbose responses for terse personality
            sentences = text.split(". ")
            text = ". ".join(sentences[:2]) + "."

        # Apply tone adjustment
        text = self.adjust_for_tone(text)

        # Adjust formality
        if self.formality < 0.3:
            # Make more casual
            text = text.replace("You observe", "You see")
            text = text.replace("It appears that", "Looks like")
            text = text.replace("Indeed", "Yeah")
        elif self.formality > 0.7:
            # Make more formal
            text = text.replace("yeah", "indeed")
            text = text.replace("ok", "very well")
            text = text.replace("sure", "certainly")

        return text

    def set_tone_from_context(self, chaos: int, danger_level: int = 0,
                              mystery_level: int = 0):
        """Automatically set tone based on game context."""
        if danger_level > 7 or chaos > 7:
            self.current_tone = GMTone.URGENT
        elif danger_level > 4:
            self.current_tone = GMTone.OMINOUS
        elif mystery_level > 5:
            self.current_tone = GMTone.MYSTERIOUS
        elif chaos < 3:
            self.current_tone = GMTone.HOPEFUL
        else:
            self.current_tone = GMTone.NEUTRAL


# Preset personalities
PERSONALITIES = {
    "classic": GMPersonality(
        name="The Oracle",
        style=GMStyle.STANDARD,
        formality=0.6,
        verbosity=0.5,
        drama=0.5
    ),
    "dark_narrator": GMPersonality(
        name="The Dark Narrator",
        style=GMStyle.DRAMATIC,
        formality=0.7,
        verbosity=0.7,
        drama=0.9,
        current_tone=GMTone.OMINOUS
    ),
    "tavern_keeper": GMPersonality(
        name="Old Bartok",
        style=GMStyle.CASUAL,
        formality=0.2,
        verbosity=0.6,
        drama=0.3,
        greetings=[
            "Ah, back again! Pull up a chair.",
            "Well met, friend! What brings you?",
            "Hah! I knew you'd return. What's the news?",
        ]
    ),
    "war_commander": GMPersonality(
        name="Marshal",
        style=GMStyle.TERSE,
        formality=0.8,
        verbosity=0.2,
        drama=0.4,
        greetings=[
            "Report.",
            "Status update required.",
            "The battlefield awaits. Proceed.",
        ]
    ),
    "mystical_seer": GMPersonality(
        name="The Seer",
        style=GMStyle.VERBOSE,
        formality=0.5,
        verbosity=0.8,
        drama=0.7,
        current_tone=GMTone.MYSTERIOUS,
        greetings=[
            "The threads of fate shimmer before me... I sense your presence.",
            "Ah, seeker of truth, the veil parts for you once more.",
            "The stars whispered of your coming. Ask, and perhaps see.",
        ]
    ),
}
