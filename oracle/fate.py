"""Oracle system for yes/no decision making with chaos mechanics."""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# A plain player action may trigger a random event. The chance scales with
# chaos (chaos / ACTION_EVENT_DIVISOR) but is capped so high-chaos sessions
# don't drown the fiction in event spam (uncapped, chaos 9 would be 50%).
ACTION_EVENT_DIVISOR = 18
ACTION_EVENT_CHANCE_CAP = 0.25


def action_event_chance(chaos: int) -> float:
    """Probability (0.0-1.0) that a plain player action triggers a random event."""
    return min(ACTION_EVENT_CHANCE_CAP, chaos / ACTION_EVENT_DIVISOR)


class Likelihood(Enum):
    """Likelihood levels for oracle questions."""
    IMPOSSIBLE = ("Impossible", 10)
    UNLIKELY = ("Unlikely", 25)
    EVEN = ("50/50", 50)
    LIKELY = ("Likely", 75)
    CERTAIN = ("Certain", 90)

    def __init__(self, display: str, base_percent: int):
        self.display = display
        self.base_percent = base_percent


class Answer(Enum):
    """Possible oracle answers."""
    NO_AND = "NO, AND..."
    NO = "NO"
    NO_BUT = "NO, BUT..."
    YES_BUT = "YES, BUT..."
    YES = "YES"
    YES_AND = "YES, AND..."


@dataclass
class OracleResult:
    """Result of an oracle question."""
    roll: int
    threshold: int
    chaos: int
    likelihood: Likelihood
    answer: Answer
    random_event: bool = False
    question: str = ""

    def __str__(self) -> str:
        parts = [
            f"Rolling... {self.roll} (Chaos: {self.chaos}, Likelihood: {self.likelihood.display})",
            self.answer.value
        ]
        if self.random_event:
            parts.append("⚡ RANDOM EVENT TRIGGERED!")
        return "\n".join(parts)


class Oracle:
    """The fate oracle for answering yes/no questions."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self._chaos = 5  # Default chaos level (1-9)

    @property
    def chaos(self) -> int:
        """Current chaos factor."""
        return self._chaos

    @chaos.setter
    def chaos(self, value: int):
        """Set chaos factor, clamped to 1-9."""
        self._chaos = max(1, min(9, value))

    def chaos_up(self) -> int:
        """Increase chaos factor."""
        self.chaos += 1
        return self.chaos

    def chaos_down(self) -> int:
        """Decrease chaos factor."""
        self.chaos -= 1
        return self.chaos

    def end_scene(self, in_control: bool) -> int:
        """Mythic end-of-scene adjustment.

        Chaos falls when the player stayed in control of the scene,
        and rises when events ran away from them. Returns new chaos.
        """
        return self.chaos_down() if in_control else self.chaos_up()

    def ask(
        self,
        question: str = "",
        likelihood: Likelihood = Likelihood.EVEN
    ) -> OracleResult:
        """Ask the oracle a yes/no question."""
        # Calculate threshold with chaos modifier
        base = likelihood.base_percent
        chaos_mod = self._calculate_chaos_modifier(likelihood)
        threshold = base + chaos_mod

        # Roll d100
        roll = self.rng.randint(1, 100)

        # Determine answer
        answer = self._determine_answer(roll, threshold)

        # Check for random event (critical extremes)
        random_event = roll <= 5 or roll >= 95

        return OracleResult(
            roll=roll,
            threshold=threshold,
            chaos=self.chaos,
            likelihood=likelihood,
            answer=answer,
            random_event=random_event,
            question=question
        )

    def _calculate_chaos_modifier(self, likelihood: Likelihood) -> int:
        """Calculate chaos modifier based on likelihood."""
        chaos_diff = self.chaos - 5  # Deviation from neutral

        if likelihood == Likelihood.EVEN:
            return 0  # No modifier for 50/50

        if likelihood in (Likelihood.IMPOSSIBLE, Likelihood.UNLIKELY):
            # Higher chaos makes unlikely things more likely
            return chaos_diff * 2

        if likelihood in (Likelihood.LIKELY, Likelihood.CERTAIN):
            # Higher chaos makes certain things less certain
            return -chaos_diff * 2

        return 0

    def _determine_answer(self, roll: int, threshold: int) -> Answer:
        """Determine the oracle answer based on roll and threshold."""
        success = roll <= threshold

        # Check for extreme modifiers
        if roll <= 10:
            return Answer.YES_AND if success else Answer.NO_BUT
        elif roll >= 90:
            return Answer.NO_AND if not success else Answer.YES_BUT
        else:
            return Answer.YES if success else Answer.NO

    def coin_flip(self) -> bool:
        """Simple 50/50 coin flip."""
        return self.rng.random() < 0.5

    def choose(self, options: list[str]) -> str:
        """Randomly choose from a list of options."""
        return self.rng.choice(options)


# Module-level oracle instance
_oracle = Oracle()

def ask(question: str = "", likelihood: Likelihood = Likelihood.EVEN) -> OracleResult:
    """Ask the oracle using the default instance."""
    return _oracle.ask(question, likelihood)

def get_chaos() -> int:
    """Get current chaos level."""
    return _oracle.chaos

def set_chaos(value: int) -> int:
    """Set chaos level."""
    _oracle.chaos = value
    return _oracle.chaos

def chaos_up() -> int:
    """Increase chaos."""
    return _oracle.chaos_up()

def chaos_down() -> int:
    """Decrease chaos."""
    return _oracle.chaos_down()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if not args:
        print("Oracle Fate System")
        print("Usage: python -m oracle.fate [--likely|--unlikely|--certain|--impossible] <question>")
        print("Examples:")
        print("  python -m oracle.fate Is the door locked?")
        print("  python -m oracle.fate --likely Does the guard notice me?")
    else:
        likelihood = Likelihood.EVEN
        question_parts = []

        for arg in args:
            if arg == "--likely":
                likelihood = Likelihood.LIKELY
            elif arg == "--unlikely":
                likelihood = Likelihood.UNLIKELY
            elif arg == "--certain":
                likelihood = Likelihood.CERTAIN
            elif arg == "--impossible":
                likelihood = Likelihood.IMPOSSIBLE
            else:
                question_parts.append(arg)

        question = " ".join(question_parts)
        result = ask(question, likelihood)
        print(result)
