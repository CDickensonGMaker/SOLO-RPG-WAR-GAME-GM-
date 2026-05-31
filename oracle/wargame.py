"""Tactical AI system for wargame mode."""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Aggression(Enum):
    """AI aggression levels affecting tactical decisions."""
    PASSIVE = ("Passive", -2)
    CAUTIOUS = ("Cautious", -1)
    BALANCED = ("Balanced", 0)
    AGGRESSIVE = ("Aggressive", 1)
    RECKLESS = ("Reckless", 2)

    def __init__(self, display: str, modifier: int):
        self.display = display
        self.modifier = modifier


class Doctrine(Enum):
    """Combat doctrine affecting unit behavior."""
    HORDE = ("Horde", "Overwhelm with numbers")
    ELITE = ("Elite", "Quality over quantity")
    DEFENSIVE = ("Defensive", "Hold and fortify")
    ALPHA_STRIKE = ("Alpha Strike", "Maximum initial damage")
    GUERRILLA = ("Guerrilla", "Hit and run tactics")

    def __init__(self, display: str, description: str):
        self.display = display
        self.description = description


class ThreatLevel(Enum):
    """Threat assessment levels."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ThreatAssessment:
    """Assessment of a potential threat."""
    target: str
    level: ThreatLevel
    reason: str

    def __str__(self) -> str:
        return f"[{self.level.value}] {self.target}: {self.reason}"


@dataclass
class TacticalOption:
    """A possible tactical action."""
    description: str
    weight: float
    modified_weight: float = 0.0
    action_type: str = ""

    def __post_init__(self):
        if self.modified_weight == 0.0:
            self.modified_weight = self.weight

    def __str__(self) -> str:
        return f"{self.description} (weight: {self.modified_weight:.1f})"


@dataclass
class TacticalDecision:
    """Result of tactical analysis and decision making."""
    threats: list[ThreatAssessment]
    options: list[TacticalOption]
    selected: TacticalOption
    doctrine: Doctrine
    aggression: Aggression

    def __str__(self) -> str:
        lines = [
            f"Doctrine: {self.doctrine.display} | Aggression: {self.aggression.display}",
            "",
            "Threat Assessment:",
        ]
        for threat in self.threats:
            lines.append(f"  {threat}")

        lines.append("")
        lines.append("Options Considered:")
        for opt in self.options[:5]:  # Top 5 options
            lines.append(f"  {opt}")

        lines.append("")
        lines.append(f"DECISION: {self.selected.description}")

        return "\n".join(lines)


# Threat keywords and their associated threat levels
THREAT_KEYWORDS: dict[str, tuple[ThreatLevel, str]] = {
    # High threats
    "tank": (ThreatLevel.HIGH, "Armored vehicle detected"),
    "armor": (ThreatLevel.HIGH, "Heavy armor present"),
    "artillery": (ThreatLevel.HIGH, "Indirect fire capability"),
    "sniper": (ThreatLevel.HIGH, "Precision threat"),
    "heavy weapon": (ThreatLevel.HIGH, "Heavy firepower"),
    "machine gun": (ThreatLevel.HIGH, "Suppression capability"),
    "flamer": (ThreatLevel.HIGH, "Area denial weapon"),
    "mech": (ThreatLevel.HIGH, "Heavy assault unit"),

    # Medium threats
    "squad": (ThreatLevel.MEDIUM, "Infantry formation"),
    "fireteam": (ThreatLevel.MEDIUM, "Small unit"),
    "cover": (ThreatLevel.MEDIUM, "Entrenched position"),
    "fortified": (ThreatLevel.MEDIUM, "Defensive position"),
    "veteran": (ThreatLevel.MEDIUM, "Experienced troops"),
    "elite": (ThreatLevel.MEDIUM, "Quality opposition"),
    "officer": (ThreatLevel.MEDIUM, "Leadership present"),
    "flanking": (ThreatLevel.MEDIUM, "Tactical maneuver"),

    # Low threats
    "open": (ThreatLevel.LOW, "Exposed position"),
    "scattered": (ThreatLevel.LOW, "Disorganized"),
    "retreating": (ThreatLevel.LOW, "Withdrawing"),
    "suppressed": (ThreatLevel.LOW, "Pinned down"),
    "wounded": (ThreatLevel.LOW, "Reduced effectiveness"),
    "militia": (ThreatLevel.LOW, "Irregular troops"),
    "conscript": (ThreatLevel.LOW, "Poorly trained"),
}

# Battle events table
BATTLE_EVENTS: list[tuple[int, int, str]] = [
    (1, 5, "Ammunition running low - reduce fire rate"),
    (6, 10, "Unexpected reinforcements arrive"),
    (11, 15, "Communication disrupted - command confusion"),
    (16, 20, "Fog of war - visibility reduced"),
    (21, 25, "Morale surge - troops fight harder"),
    (26, 30, "Equipment malfunction - weapon jams"),
    (31, 35, "Flanking opportunity discovered"),
    (36, 40, "Enemy reveals hidden position"),
    (41, 45, "Weather change affects visibility"),
    (46, 50, "Civilian presence complicates engagement"),
    (51, 55, "Intel update - enemy strength revised"),
    (56, 60, "Supply line secured - ammo restored"),
    (61, 65, "Enemy communications intercepted"),
    (66, 70, "Cover destroyed by enemy fire"),
    (71, 75, "Rally point established"),
    (76, 80, "Enemy falling back to secondary position"),
    (81, 85, "Air support available briefly"),
    (86, 90, "Medic tends to wounded - unit recovers"),
    (91, 95, "Smoke obscures battlefield"),
    (96, 100, "Critical moment - next action decisive"),
]

# Base tactical options
BASE_OPTIONS: list[tuple[str, float, str]] = [
    ("Focus fire on highest threat", 3.0, "focus_fire"),
    ("Split fire across multiple targets", 2.0, "split_fire"),
    ("Advance aggressively", 2.5, "advance"),
    ("Hold position and overwatch", 2.5, "hold"),
    ("Flank the enemy position", 2.0, "flank"),
    ("Tactical withdrawal", 1.5, "retreat"),
    ("Suppress and maneuver", 2.5, "suppress"),
    ("Concentrate on weak point", 2.0, "concentrate"),
    ("Defensive formation", 2.0, "defensive"),
    ("All-out assault", 1.5, "assault"),
]


class WargameAI:
    """Tactical AI for wargame decision making."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self._aggression = Aggression.BALANCED
        self._doctrine = Doctrine.ELITE

    @property
    def aggression(self) -> Aggression:
        """Current aggression level."""
        return self._aggression

    @aggression.setter
    def aggression(self, value: Aggression):
        """Set aggression level."""
        self._aggression = value

    @property
    def doctrine(self) -> Doctrine:
        """Current combat doctrine."""
        return self._doctrine

    @doctrine.setter
    def doctrine(self, value: Doctrine):
        """Set combat doctrine."""
        self._doctrine = value

    def analyze_threats(self, situation: str) -> list[ThreatAssessment]:
        """
        Parse situation string for keywords and assign threat levels.

        Args:
            situation: Description of the tactical situation

        Returns:
            List of threat assessments sorted by threat level
        """
        threats: list[ThreatAssessment] = []
        situation_lower = situation.lower()

        for keyword, (level, reason) in THREAT_KEYWORDS.items():
            if keyword in situation_lower:
                # Find the context around the keyword for target description
                idx = situation_lower.find(keyword)
                start = max(0, idx - 20)
                end = min(len(situation), idx + len(keyword) + 20)
                context = situation[start:end].strip()

                threats.append(ThreatAssessment(
                    target=keyword.title(),
                    level=level,
                    reason=reason
                ))

        # Sort by threat level (HIGH first)
        level_order = {ThreatLevel.HIGH: 0, ThreatLevel.MEDIUM: 1, ThreatLevel.LOW: 2}
        threats.sort(key=lambda t: level_order[t.level])

        # If no threats detected, add a generic assessment
        if not threats:
            threats.append(ThreatAssessment(
                target="Unknown",
                level=ThreatLevel.MEDIUM,
                reason="Situation unclear - maintain vigilance"
            ))

        return threats

    def generate_options(self, threats: list[ThreatAssessment]) -> list[TacticalOption]:
        """
        Generate tactical options based on threat assessment.

        Args:
            threats: List of assessed threats

        Returns:
            List of tactical options with base weights
        """
        options: list[TacticalOption] = []

        # Start with base options
        for desc, weight, action_type in BASE_OPTIONS:
            options.append(TacticalOption(
                description=desc,
                weight=weight,
                action_type=action_type
            ))

        # Modify weights based on threat levels present
        high_threat_count = sum(1 for t in threats if t.level == ThreatLevel.HIGH)
        low_threat_count = sum(1 for t in threats if t.level == ThreatLevel.LOW)

        for opt in options:
            if high_threat_count > 0:
                # Against high threats: favor defense and focus fire
                if opt.action_type in ("focus_fire", "suppress", "defensive"):
                    opt.weight += 1.0 * high_threat_count
                elif opt.action_type in ("advance", "assault"):
                    opt.weight -= 0.5 * high_threat_count

            if low_threat_count > 0:
                # Against low threats: favor aggressive actions
                if opt.action_type in ("advance", "assault", "flank"):
                    opt.weight += 0.5 * low_threat_count
                elif opt.action_type in ("retreat", "defensive"):
                    opt.weight -= 0.5 * low_threat_count

        return options

    def apply_modifiers(self, options: list[TacticalOption]) -> list[TacticalOption]:
        """
        Apply doctrine and aggression modifiers to tactical options.

        Args:
            options: List of tactical options with base weights

        Returns:
            Options with modified weights applied
        """
        for opt in options:
            opt.modified_weight = opt.weight

            # Apply doctrine modifiers
            if self.doctrine == Doctrine.HORDE:
                if opt.action_type in ("advance", "focus_fire", "assault"):
                    opt.modified_weight += 1.5
                elif opt.action_type in ("retreat", "defensive"):
                    opt.modified_weight -= 1.0

            elif self.doctrine == Doctrine.ELITE:
                if opt.action_type in ("suppress", "flank", "concentrate"):
                    opt.modified_weight += 1.0
                elif opt.action_type == "assault":
                    opt.modified_weight -= 0.5

            elif self.doctrine == Doctrine.DEFENSIVE:
                if opt.action_type in ("hold", "defensive", "suppress"):
                    opt.modified_weight += 2.0
                elif opt.action_type in ("advance", "assault", "flank"):
                    opt.modified_weight -= 1.0

            elif self.doctrine == Doctrine.ALPHA_STRIKE:
                if opt.action_type in ("assault", "focus_fire", "concentrate"):
                    opt.modified_weight += 2.0
                elif opt.action_type in ("hold", "retreat", "defensive"):
                    opt.modified_weight -= 1.5

            elif self.doctrine == Doctrine.GUERRILLA:
                if opt.action_type in ("flank", "retreat", "suppress"):
                    opt.modified_weight += 1.5
                elif opt.action_type in ("hold", "assault"):
                    opt.modified_weight -= 1.0

            # Apply aggression modifiers
            aggression_mod = self.aggression.modifier

            if opt.action_type in ("advance", "assault", "focus_fire"):
                opt.modified_weight += aggression_mod * 0.5
            elif opt.action_type in ("hold", "retreat", "defensive"):
                opt.modified_weight -= aggression_mod * 0.5

            # Ensure minimum weight
            opt.modified_weight = max(0.1, opt.modified_weight)

        # Sort by modified weight descending
        options.sort(key=lambda o: o.modified_weight, reverse=True)

        return options

    def decide(self, situation: str) -> TacticalDecision:
        """
        Execute full tactical decision pipeline.

        Args:
            situation: Description of the tactical situation

        Returns:
            Complete tactical decision with analysis
        """
        # Analyze threats
        threats = self.analyze_threats(situation)

        # Generate options based on threats
        options = self.generate_options(threats)

        # Apply doctrine and aggression modifiers
        options = self.apply_modifiers(options)

        # Select option using weighted random
        selected = self._weighted_select(options)

        return TacticalDecision(
            threats=threats,
            options=options,
            selected=selected,
            doctrine=self.doctrine,
            aggression=self.aggression
        )

    def _weighted_select(self, options: list[TacticalOption]) -> TacticalOption:
        """Select an option using weighted random selection."""
        total_weight = sum(opt.modified_weight for opt in options)
        roll = self.rng.random() * total_weight

        cumulative = 0.0
        for opt in options:
            cumulative += opt.modified_weight
            if roll <= cumulative:
                return opt

        # Fallback to first option (should not reach here)
        return options[0]

    def roll_priority(self, targets: list[str]) -> str:
        """
        Determine which target the enemy prioritizes.

        Args:
            targets: List of potential target descriptions

        Returns:
            The selected target
        """
        if not targets:
            return "No valid targets"

        # Assign weights based on threat keywords in target descriptions
        weighted_targets: list[tuple[str, float]] = []

        for target in targets:
            weight = 1.0
            target_lower = target.lower()

            # Higher priority for exposed/dangerous targets
            if "open" in target_lower or "exposed" in target_lower:
                weight += 2.0
            if "officer" in target_lower or "leader" in target_lower:
                weight += 1.5
            if "heavy weapon" in target_lower or "machine gun" in target_lower:
                weight += 1.5
            if "cover" in target_lower or "fortified" in target_lower:
                weight -= 0.5
            if "suppressed" in target_lower:
                weight -= 1.0

            # Aggression affects priority
            if self.aggression.modifier > 0:
                # Aggressive: target dangerous enemies
                if any(kw in target_lower for kw in ("heavy", "sniper", "officer")):
                    weight += self.aggression.modifier
            else:
                # Cautious: target easy kills
                if any(kw in target_lower for kw in ("exposed", "wounded", "open")):
                    weight += abs(self.aggression.modifier)

            weight = max(0.1, weight)
            weighted_targets.append((target, weight))

        # Weighted selection
        total = sum(w for _, w in weighted_targets)
        roll = self.rng.random() * total

        cumulative = 0.0
        for target, weight in weighted_targets:
            cumulative += weight
            if roll <= cumulative:
                return target

        return targets[0]

    def roll_morale(self, casualties_percent: float) -> str:
        """
        Check if unit breaks or rallies based on casualties and doctrine.

        Args:
            casualties_percent: Percentage of casualties (0.0 to 1.0)

        Returns:
            Morale status string
        """
        # Base morale threshold
        base_threshold = 50

        # Doctrine modifiers
        doctrine_mods = {
            Doctrine.HORDE: -10,      # More likely to break
            Doctrine.ELITE: 15,       # Less likely to break
            Doctrine.DEFENSIVE: 10,   # Stubborn
            Doctrine.ALPHA_STRIKE: -5,  # Committed but fragile
            Doctrine.GUERRILLA: 5,    # Know when to run
        }

        threshold = base_threshold + doctrine_mods.get(self.doctrine, 0)

        # Aggression affects morale
        threshold += self.aggression.modifier * 5

        # Casualties reduce effective morale
        casualty_penalty = int(casualties_percent * 100)

        effective_morale = threshold - casualty_penalty
        roll = self.rng.randint(1, 100)

        if roll <= effective_morale:
            if roll <= 10:
                return "INSPIRING: Unit rallies with renewed vigor!"
            elif roll <= effective_morale - 20:
                return "STEADY: Unit holds firm."
            else:
                return "WAVERING: Unit holds but morale shaky."
        else:
            if roll >= 95:
                return "ROUTED: Unit breaks and flees!"
            elif roll >= effective_morale + 20:
                return "BROKEN: Unit retreats in disorder."
            else:
                return "FALLING BACK: Unit withdraws under pressure."

    def roll_event(self) -> str:
        """
        Roll for a random battle event.

        Returns:
            Description of the battle event
        """
        roll = self.rng.randint(1, 100)

        for low, high, event in BATTLE_EVENTS:
            if low <= roll <= high:
                return f"[{roll}] {event}"

        return f"[{roll}] Situation unchanged"

    def render_decision(self, decision: TacticalDecision) -> str:
        """
        Render a tactical decision as formatted output.

        Args:
            decision: The tactical decision to render

        Returns:
            Formatted string representation
        """
        lines = [
            "=" * 50,
            "TACTICAL ANALYSIS",
            "=" * 50,
            f"Doctrine: {decision.doctrine.display}",
            f"Stance:   {decision.aggression.display}",
            "",
            "-" * 50,
            "THREAT ASSESSMENT",
            "-" * 50,
        ]

        for threat in decision.threats:
            icon = {"HIGH": "!!!", "MEDIUM": " ! ", "LOW": "   "}[threat.level.value]
            lines.append(f"  [{icon}] {threat.target}: {threat.reason}")

        lines.extend([
            "",
            "-" * 50,
            "OPTIONS EVALUATED",
            "-" * 50,
        ])

        for i, opt in enumerate(decision.options[:5], 1):
            bar_len = int(opt.modified_weight * 3)
            bar = "#" * bar_len
            lines.append(f"  {i}. {opt.description}")
            lines.append(f"     Weight: {opt.modified_weight:.1f} [{bar}]")

        lines.extend([
            "",
            "=" * 50,
            f">>> DECISION: {decision.selected.description.upper()}",
            "=" * 50,
        ])

        return "\n".join(lines)


# Module-level AI instance
_ai = WargameAI()


def decide(situation: str) -> TacticalDecision:
    """Make a tactical decision using the default AI."""
    return _ai.decide(situation)


def analyze(situation: str) -> list[ThreatAssessment]:
    """Analyze threats in a situation using the default AI."""
    return _ai.analyze_threats(situation)


def roll_event() -> str:
    """Roll for a battle event using the default AI."""
    return _ai.roll_event()


def roll_priority(targets: list[str]) -> str:
    """Roll target priority using the default AI."""
    return _ai.roll_priority(targets)


def roll_morale(casualties: float) -> str:
    """Roll morale check using the default AI."""
    return _ai.roll_morale(casualties)


def set_doctrine(doctrine: Doctrine) -> Doctrine:
    """Set the AI doctrine."""
    _ai.doctrine = doctrine
    return _ai.doctrine


def set_aggression(aggression: Aggression) -> Aggression:
    """Set the AI aggression level."""
    _ai.aggression = aggression
    return _ai.aggression


def render(decision: TacticalDecision) -> str:
    """Render a decision using the default AI."""
    return _ai.render_decision(decision)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if not args:
        print("Oracle Wargame Tactical AI")
        print()
        print("Usage: python -m oracle.wargame [options] <situation>")
        print()
        print("Options:")
        print("  --doctrine <type>    Set doctrine (horde/elite/defensive/alpha/guerrilla)")
        print("  --aggression <level> Set aggression (passive/cautious/balanced/aggressive/reckless)")
        print("  --event              Roll a random battle event")
        print("  --morale <percent>   Check morale at given casualty percentage")
        print()
        print("Examples:")
        print("  python -m oracle.wargame Enemy has infantry in cover and tank in open")
        print("  python -m oracle.wargame --doctrine horde --aggression aggressive Facing elite troops")
        print("  python -m oracle.wargame --event")
        print("  python -m oracle.wargame --morale 40")
    else:
        doctrine = Doctrine.DEFENSIVE  # Default doctrine
        aggression = Aggression.BALANCED

        i = 0
        situation_parts = []
        while i < len(args):
            arg = args[i]
            if arg == "--doctrine" and i + 1 < len(args):
                try:
                    doctrine = Doctrine[args[i + 1].upper()]
                except KeyError:
                    pass
                i += 2
            elif arg == "--aggression" and i + 1 < len(args):
                try:
                    aggression = Aggression[args[i + 1].upper()]
                except KeyError:
                    pass
                i += 2
            elif arg == "--event":
                print(roll_event())
                sys.exit(0)
            elif arg == "--morale" and i + 1 < len(args):
                try:
                    pct = float(args[i + 1])
                    result = check_morale(pct)
                    print(f"Morale check at {pct}% casualties: {result}")
                except ValueError:
                    print("Invalid casualty percentage")
                sys.exit(0)
            else:
                situation_parts.append(arg)
                i += 1

        if situation_parts:
            set_doctrine(doctrine)
            set_aggression(aggression)
            situation = " ".join(situation_parts)
            decision = decide(situation)
            print(decision)
