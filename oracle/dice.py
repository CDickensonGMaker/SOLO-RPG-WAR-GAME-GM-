"""Dice parser and roller with support for complex notation."""

import random
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DiceResult:
    """Result of a dice roll."""
    total: int
    rolls: list[int]
    dropped: list[int]
    modifier: int
    expression: str
    successes: Optional[int] = None

    def __str__(self) -> str:
        parts = []

        if self.dropped:
            roll_strs = []
            all_rolls = self.rolls + self.dropped
            for r in all_rolls:
                if r in self.dropped and self.dropped.count(r) > roll_strs.count(f"({r})"):
                    roll_strs.append(f"({r})")
                else:
                    roll_strs.append(str(r))
            parts.append(f"[{', '.join(roll_strs)}]")
        else:
            parts.append(f"[{', '.join(map(str, self.rolls))}]")

        if self.modifier > 0:
            parts.append(f"+ {self.modifier}")
        elif self.modifier < 0:
            parts.append(f"- {abs(self.modifier)}")

        if self.successes is not None:
            return f"{self.total} {' '.join(parts)} → {self.successes} successes"

        return f"{self.total} {' '.join(parts)}"


class DiceRoller:
    """Parser and roller for dice notation."""

    # Regex patterns for dice notation
    BASIC_PATTERN = re.compile(
        r'^(\d+)?d(\d+)'  # XdY
        r'(kh\d+|kl\d+)?'  # keep highest/lowest
        r'(!)?'  # exploding
        r'(t\d+)?'  # target number
        r'([+-]\d+)?$',  # modifier
        re.IGNORECASE
    )

    ADV_PATTERN = re.compile(r'^(\d+)?d(\d+)\s*(adv|dis)$', re.IGNORECASE)

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def roll(self, expression: str) -> DiceResult:
        """Parse and roll a dice expression."""
        expression = expression.strip()

        # Check for advantage/disadvantage
        adv_match = self.ADV_PATTERN.match(expression)
        if adv_match:
            return self._roll_advantage(adv_match)

        # Check for basic dice notation
        basic_match = self.BASIC_PATTERN.match(expression)
        if basic_match:
            return self._roll_basic(basic_match, expression)

        raise ValueError(f"Invalid dice expression: {expression}")

    def _roll_basic(self, match: re.Match, expression: str) -> DiceResult:
        """Roll basic dice notation."""
        num_dice = int(match.group(1) or 1)
        sides = int(match.group(2))
        keep_spec = match.group(3)
        exploding = match.group(4) is not None
        target_spec = match.group(5)
        modifier_spec = match.group(6)

        # Roll the dice
        rolls = [self.rng.randint(1, sides) for _ in range(num_dice)]

        # Handle exploding dice
        if exploding:
            extra_rolls = []
            for r in rolls:
                current = r
                while current == sides:
                    new_roll = self.rng.randint(1, sides)
                    extra_rolls.append(new_roll)
                    current = new_roll
            rolls.extend(extra_rolls)

        # Handle keep highest/lowest
        dropped = []
        if keep_spec:
            keep_count = int(keep_spec[2:])
            sorted_rolls = sorted(rolls, reverse=keep_spec[:2].lower() == 'kh')
            kept = sorted_rolls[:keep_count]
            dropped = sorted_rolls[keep_count:]
            rolls = kept

        # Handle modifier
        modifier = int(modifier_spec) if modifier_spec else 0

        # Handle target number (count successes)
        successes = None
        if target_spec:
            target = int(target_spec[1:])
            successes = sum(1 for r in rolls if r >= target)

        total = sum(rolls) + modifier

        return DiceResult(
            total=total,
            rolls=rolls,
            dropped=dropped,
            modifier=modifier,
            expression=expression,
            successes=successes
        )

    def _roll_advantage(self, match: re.Match) -> DiceResult:
        """Roll with advantage or disadvantage."""
        num_dice = int(match.group(1) or 1)
        sides = int(match.group(2))
        mode = match.group(3).lower()

        # Roll twice
        roll1 = self.rng.randint(1, sides)
        roll2 = self.rng.randint(1, sides)

        if mode == 'adv':
            kept = max(roll1, roll2)
            dropped = min(roll1, roll2)
        else:
            kept = min(roll1, roll2)
            dropped = max(roll1, roll2)

        return DiceResult(
            total=kept,
            rolls=[kept],
            dropped=[dropped],
            modifier=0,
            expression=f"{num_dice}d{sides} {mode}"
        )

    def roll_simple(self, num_dice: int, sides: int) -> list[int]:
        """Roll simple dice without notation parsing."""
        return [self.rng.randint(1, sides) for _ in range(num_dice)]

    def d100(self) -> int:
        """Roll a d100."""
        return self.rng.randint(1, 100)

    def d20(self) -> int:
        """Roll a d20."""
        return self.rng.randint(1, 20)

    def d6(self) -> int:
        """Roll a d6."""
        return self.rng.randint(1, 6)


# Module-level roller instance
_roller = DiceRoller()

def roll(expression: str) -> DiceResult:
    """Roll dice using the default roller."""
    return _roller.roll(expression)

def d100() -> int:
    """Roll a d100 using the default roller."""
    return _roller.d100()

def d20() -> int:
    """Roll a d20 using the default roller."""
    return _roller.d20()

def d6() -> int:
    """Roll a d6 using the default roller."""
    return _roller.d6()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        expr = " ".join(sys.argv[1:])
        try:
            result = roll(expr)
            print(result)
        except ValueError as e:
            print(f"Error: {e}")
    else:
        print("Oracle Dice Roller")
        print("Usage: python -m oracle.dice <expression>")
        print("Examples:")
        print("  python -m oracle.dice 2d6+3")
        print("  python -m oracle.dice 4d6kh3")
        print("  python -m oracle.dice 1d20 adv")
