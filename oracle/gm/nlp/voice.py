"""
NPC Voice Differentiation - Makes NPCs Sound Distinct.

Generates dialogue framing and speech patterns based on NPC traits,
so a gruff soldier sounds different from a nervous merchant or
a haughty noble.

The voice system considers:
- Formality (formal, casual, crude)
- Verbosity (terse, normal, verbose)
- Mood words (characteristic interjections)
- Speech patterns (how they frame their dialogue)

Usage:
    generator = VoiceGenerator()

    # Generate voiced dialogue for an NPC
    dialogue = generator.generate_frame(
        npc_name="Grimjaw",
        traits=["gruff", "soldier", "veteran"],
        content="I know nothing of that artifact"
    )
    # Output: 'Grimjaw grunts. "Hmph, I know nothing of that artifact."'
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random


@dataclass
class NPCVoice:
    """
    Defines how an NPC speaks based on their traits.

    Attributes:
        formality: How formal the NPC speaks (formal, casual, crude)
        verbosity: How much the NPC says (terse, normal, verbose)
        mood_words: Characteristic interjections ("hmph", "friend", "perhaps")
        speech_patterns: Template patterns for framing dialogue
    """
    formality: str = "neutral"  # formal, neutral, casual, crude
    verbosity: str = "normal"   # terse, normal, verbose
    mood_words: List[str] = field(default_factory=list)
    speech_patterns: List[str] = field(default_factory=list)


class VoiceGenerator:
    """
    Generates NPC-appropriate dialogue framing based on traits.

    The generator maps NPC traits to voice characteristics and
    uses those to frame dialogue with appropriate speech patterns.

    Example:
        A "gruff veteran" might say:
        'Grimjaw grunts. "Hmph, never heard of it."'

        While a "cheerful merchant" might say:
        '"Ah, friend! Never heard of it," Aldric says with a smile.'
    """

    # Map traits to voice characteristics
    TRAIT_TO_VOICE: Dict[str, Dict] = {
        # Formality
        "noble": {"formality": "formal"},
        "royal": {"formality": "formal"},
        "aristocrat": {"formality": "formal"},
        "scholar": {"formality": "formal"},
        "priest": {"formality": "formal"},
        "courtier": {"formality": "formal"},
        "bureaucrat": {"formality": "formal"},

        "merchant": {"formality": "neutral"},
        "craftsman": {"formality": "neutral"},
        "soldier": {"formality": "neutral"},
        "guard": {"formality": "neutral"},
        "innkeeper": {"formality": "neutral"},

        "peasant": {"formality": "casual"},
        "farmer": {"formality": "casual"},
        "commoner": {"formality": "casual"},
        "worker": {"formality": "casual"},

        "thief": {"formality": "crude"},
        "criminal": {"formality": "crude"},
        "bandit": {"formality": "crude"},
        "pirate": {"formality": "crude"},
        "rogue": {"formality": "crude"},
        "thug": {"formality": "crude"},

        # Verbosity
        "terse": {"verbosity": "terse"},
        "silent": {"verbosity": "terse"},
        "stoic": {"verbosity": "terse"},
        "laconic": {"verbosity": "terse"},
        "quiet": {"verbosity": "terse"},
        "reserved": {"verbosity": "terse"},

        "chatty": {"verbosity": "verbose"},
        "talkative": {"verbosity": "verbose"},
        "nervous": {"verbosity": "verbose"},
        "anxious": {"verbosity": "verbose"},
        "excitable": {"verbosity": "verbose"},
        "dramatic": {"verbosity": "verbose"},

        # Mood words
        "gruff": {"mood_words": ["hmph", "bah", "*grunt*", "hrrm"]},
        "stern": {"mood_words": ["hmm", "indeed", "I see"]},
        "cheerful": {"mood_words": ["ha!", "friend", "wonderful", "ah!"]},
        "friendly": {"mood_words": ["friend", "well", "indeed"]},
        "suspicious": {"mood_words": ["hmm", "perhaps", "or so you say", "interesting"]},
        "paranoid": {"mood_words": ["*glances around*", "keep your voice down", "are we alone"]},
        "cowardly": {"mood_words": ["*gulps*", "please", "mercy", "*trembles*"]},
        "brave": {"mood_words": ["ha!", "bring it on", "no fear"]},
        "arrogant": {"mood_words": ["obviously", "of course", "naturally", "as expected"]},
        "humble": {"mood_words": ["if I may", "perhaps", "forgive me"]},
        "sarcastic": {"mood_words": ["oh, really", "how surprising", "imagine that"]},
        "bitter": {"mood_words": ["*scoffs*", "typical", "of course"]},
        "weary": {"mood_words": ["*sighs*", "very well", "if you must"]},
        "enthusiastic": {"mood_words": ["excellent!", "wonderful!", "fantastic!"]},

        # Veteran adds terse + gruff
        "veteran": {"verbosity": "terse", "mood_words": ["*grunt*", "hmph"]},
        "old": {"verbosity": "normal", "mood_words": ["in my day", "I remember when"]},
        "young": {"verbosity": "verbose", "mood_words": ["wow", "really?"]},
    }

    # Speech frames organized by formality
    SPEECH_FRAMES: Dict[str, List[str]] = {
        "formal": [
            '"{content}," {name} says with measured words.',
            '{name} inclines their head. "{content}."',
            '"Indeed, {content}," {name} replies formally.',
            '"{content}," {name} states with precision.',
            '{name} considers before speaking. "{content}."',
            '"If I may, {content}," {name} says courteously.',
        ],
        "neutral": [
            '"{content}," {name} says.',
            '{name} nods. "{content}."',
            '"{content}," says {name}.',
            '{name} replies, "{content}."',
            '"Well, {content}," {name} responds.',
            '{name} answers, "{content}."',
        ],
        "casual": [
            '"{content}," {name} says with a shrug.',
            '{name} scratches their chin. "{content}."',
            '"{content}." {name} waves a hand.',
            '"Look, {content}," {name} says plainly.',
            '{name} leans in. "{content}."',
            '"{content}," {name} offers.',
        ],
        "crude": [
            '"{content}," {name} growls.',
            '{name} spits. "{content}."',
            '"{content}!" {name} barks.',
            '{name} sneers. "{content}."',
            '"{content}," {name} says roughly.',
            '{name} scowls. "{content}."',
        ],
        "terse": [
            '{name} grunts. "{content}."',
            '"{content}." Nothing more.',
            '{name} nods once. "{content}."',
            '"{content}." {name} falls silent.',
            '{name}: "{content}."',
            '"{content}," {name} says flatly.',
        ],
    }

    # Action verbs for different contexts
    GREETING_ACTIONS: Dict[str, List[str]] = {
        "friendly": [
            "smiles warmly",
            "greets you with enthusiasm",
            "waves in welcome",
            "approaches with open arms",
        ],
        "neutral": [
            "nods in acknowledgment",
            "looks up as you approach",
            "turns to face you",
            "meets your gaze",
        ],
        "hostile": [
            "eyes you suspiciously",
            "tenses at your approach",
            "narrows their eyes",
            "crosses their arms",
        ],
    }

    def generate_frame(self, npc_name: str, traits: List[str],
                       content: str, context: str = "dialogue") -> str:
        """
        Generate voiced dialogue for an NPC.

        Args:
            npc_name: The NPC's name
            traits: List of NPC traits (e.g., ["gruff", "soldier", "veteran"])
            content: The dialogue content to frame
            context: Context for the dialogue (dialogue, greeting, whisper)

        Returns:
            Fully framed dialogue with voice characteristics
        """
        voice = self._derive_voice(traits)

        # Maybe add a mood word
        if voice.mood_words and random.random() > 0.5:
            mood = random.choice(voice.mood_words)
            # Add mood word to content
            content = f"{mood}, {content}"

        # Pick appropriate frame set
        if voice.verbosity == "terse":
            frame_set = self.SPEECH_FRAMES["terse"]
        else:
            frame_set = self.SPEECH_FRAMES.get(
                voice.formality,
                self.SPEECH_FRAMES["neutral"]
            )

        frame = random.choice(frame_set)
        return frame.format(name=npc_name, content=content)

    def generate_greeting(self, npc_name: str, traits: List[str],
                          disposition: int) -> str:
        """
        Generate a greeting action for an NPC.

        Args:
            npc_name: The NPC's name
            traits: List of NPC traits
            disposition: NPC disposition (-100 to 100)

        Returns:
            Greeting description
        """
        if disposition > 30:
            mood = "friendly"
        elif disposition < -30:
            mood = "hostile"
        else:
            mood = "neutral"

        action = random.choice(self.GREETING_ACTIONS[mood])
        return f"{npc_name} {action}."

    def generate_reaction(self, npc_name: str, traits: List[str],
                          reaction_type: str) -> str:
        """
        Generate a reaction description for an NPC.

        Args:
            npc_name: The NPC's name
            traits: List of NPC traits
            reaction_type: Type of reaction (positive, negative, surprised, etc.)

        Returns:
            Reaction description
        """
        voice = self._derive_voice(traits)

        reactions = {
            "positive": [
                "nods approvingly",
                "seems pleased",
                "relaxes visibly",
                "smiles slightly",
            ],
            "negative": [
                "frowns deeply",
                "shakes their head",
                "looks disappointed",
                "scowls",
            ],
            "surprised": [
                "raises an eyebrow",
                "looks taken aback",
                "blinks in surprise",
                "startles slightly",
            ],
            "thoughtful": [
                "considers this carefully",
                "pauses to think",
                "strokes their chin",
                "furrows their brow in thought",
            ],
            "dismissive": [
                "waves a hand dismissively",
                "shrugs",
                "looks away",
                "seems uninterested",
            ],
        }

        action_list = reactions.get(reaction_type, reactions["neutral"] if "neutral" in reactions else ["reacts"])
        if not action_list:
            action_list = ["reacts"]
        action = random.choice(action_list)

        # Add mood word for gruff/nervous types
        if voice.mood_words and random.random() > 0.7:
            mood = random.choice(voice.mood_words)
            return f"{npc_name} {action}. {mood.capitalize()}."

        return f"{npc_name} {action}."

    def _derive_voice(self, traits: List[str]) -> NPCVoice:
        """
        Derive voice settings from NPC traits.

        Combines multiple trait influences into a single voice profile.
        Later traits override earlier ones for conflicting settings.

        Args:
            traits: List of NPC trait strings

        Returns:
            NPCVoice with derived settings
        """
        voice = NPCVoice()

        for trait in traits:
            trait_lower = trait.lower().strip()

            if trait_lower in self.TRAIT_TO_VOICE:
                settings = self.TRAIT_TO_VOICE[trait_lower]

                # Apply each setting
                if "formality" in settings:
                    voice.formality = settings["formality"]
                if "verbosity" in settings:
                    voice.verbosity = settings["verbosity"]
                if "mood_words" in settings:
                    # Extend rather than replace mood words
                    voice.mood_words.extend(settings["mood_words"])
                if "speech_patterns" in settings:
                    voice.speech_patterns.extend(settings["speech_patterns"])

        # Deduplicate mood words while preserving order
        seen = set()
        unique_moods = []
        for word in voice.mood_words:
            if word not in seen:
                seen.add(word)
                unique_moods.append(word)
        voice.mood_words = unique_moods

        return voice

    def get_voice_summary(self, traits: List[str]) -> Dict[str, any]:
        """
        Get a summary of the voice derived from traits.

        Useful for debugging or displaying NPC speech style.

        Args:
            traits: List of NPC traits

        Returns:
            Dictionary with voice characteristics
        """
        voice = self._derive_voice(traits)
        return {
            "formality": voice.formality,
            "verbosity": voice.verbosity,
            "mood_words": voice.mood_words,
            "num_patterns": len(voice.speech_patterns),
        }
