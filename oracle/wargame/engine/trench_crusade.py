"""
Trench Crusade Rules Engine.

Implements the dark WWI-meets-religious-horror skirmish game:
- 2d6-based system (roll 2 dice, add together, aim for 7+)
- ±Dice modifiers (roll extra dice, take highest/lowest 2)
- Action Point activations
- Blood markers and Injury Table
- Risky Actions with critical success/failure
- Glory and Damnation mechanics

Core mechanics:
- Roll 2d6, add results, compare to 7
- 2-6 = Failure, 7-11 = Success, 12 = Critical Success
- +Dice: roll extra d6s, take 2 highest
- -Dice: roll extra d6s, take 2 lowest
- Injury Table: 2d6 -> 2-6 Blood, 7-8 Downed, 9-12 Out
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .base import (
    AttackResult,
    DiceRoll,
    DiceRoller,
    MeleeResult,
    MoraleResult,
    RulesEngine,
)

if TYPE_CHECKING:
    from oracle.roster import RosterUnit


@dataclass
class TrenchCrusadeResult:
    """Extended result for Trench Crusade specific mechanics."""

    base_result: AttackResult
    blood_markers_inflicted: int = 0
    downed: bool = False
    out_of_action: bool = False
    critical_hit: bool = False
    critical_fail: bool = False
    glory_earned: int = 0
    damnation_earned: int = 0
    special_effects: list[str] = field(default_factory=list)


@dataclass
class TCDiceResult:
    """Result of a Trench Crusade 2d6 roll with ±Dice modifiers."""

    dice_rolled: list[int]  # All dice rolled
    dice_kept: list[int]    # The 2 dice that count
    total: int              # Sum of kept dice
    success: bool           # total >= 7
    critical: bool          # total == 12
    fumble: bool            # total == 2 (snake eyes)
    plus_dice: int = 0      # How many +Dice were used
    minus_dice: int = 0     # How many -Dice were used


class TrenchCrusadeEngine(RulesEngine):
    """
    Rules engine for Trench Crusade.

    Trench Crusade uses 2d6 with ±Dice modifiers.
    All rolls aim to beat 7. Critical on 12, Fumble on 2.

    Models have Blood markers instead of wounds, and combat
    emphasizes the grimdark horror of trench warfare.
    """

    # Target number (always 7 in TC)
    BASE_TARGET = 7

    # Action costs
    ACTION_MOVE = 1
    ACTION_SHOOT = 1
    ACTION_CHARGE = 2
    ACTION_AIM = 1  # Grants +1 Dice to next shot

    # Injury thresholds
    INJURY_BLOOD_MIN = 2
    INJURY_BLOOD_MAX = 6
    INJURY_DOWNED_MIN = 7
    INJURY_DOWNED_MAX = 8
    INJURY_OUT_MIN = 9
    INJURY_OUT_MAX = 12

    def __init__(self, dice_roller: DiceRoller | None = None):
        """Initialize the Trench Crusade rules engine."""
        super().__init__(dice_roller)
        self._die_type = 6

    @property
    def system_name(self) -> str:
        return "Trench Crusade"

    @property
    def system_id(self) -> str:
        return "trench_crusade"

    # =========================================================================
    # 2D6 ROLLING WITH ±DICE
    # =========================================================================

    def roll_2d6_with_modifiers(
        self,
        plus_dice: int = 0,
        minus_dice: int = 0,
    ) -> TCDiceResult:
        """
        Roll 2d6 with ±Dice modifiers.

        The core mechanic: roll 2 + plus_dice - minus_dice d6s.
        If plus_dice > 0: take the 2 highest.
        If minus_dice > 0: take the 2 lowest.
        If both: plus and minus cancel out first.

        Args:
            plus_dice: Number of +Dice (roll extra, keep highest 2)
            minus_dice: Number of -Dice (roll extra, keep lowest 2)

        Returns:
            TCDiceResult with all dice info
        """
        # Cancel out +/- dice
        net_plus = max(0, plus_dice - minus_dice)
        net_minus = max(0, minus_dice - plus_dice)

        # Roll 2 + net modifier dice
        num_dice = 2 + net_plus + net_minus
        all_dice = [self.dice._rng.randint(1, 6) for _ in range(num_dice)]

        # Sort to find highest/lowest
        sorted_dice = sorted(all_dice, reverse=True)

        if net_plus > 0:
            # Take 2 highest
            kept = sorted_dice[:2]
        elif net_minus > 0:
            # Take 2 lowest
            kept = sorted_dice[-2:]
        else:
            # Just take the 2 dice rolled
            kept = all_dice[:2]

        total = sum(kept)

        return TCDiceResult(
            dice_rolled=all_dice,
            dice_kept=kept,
            total=total,
            success=total >= self.BASE_TARGET,
            critical=total == 12,
            fumble=total == 2,
            plus_dice=plus_dice,
            minus_dice=minus_dice,
        )

    def roll_action(
        self,
        plus_dice: int = 0,
        minus_dice: int = 0,
    ) -> TCDiceResult:
        """
        Roll a standard action check (2d6 vs 7).

        Args:
            plus_dice: Bonus dice (take highest 2)
            minus_dice: Penalty dice (take lowest 2)

        Returns:
            TCDiceResult with success/critical info
        """
        return self.roll_2d6_with_modifiers(plus_dice, minus_dice)

    def roll_risky_action(
        self,
        plus_dice: int = 0,
        minus_dice: int = 0,
    ) -> tuple[TCDiceResult, str]:
        """
        Roll a Risky Action (2d6 with special failure consequences).

        12 = Critical Success - bonus effect
        7-11 = Success
        3-6 = Failure - activation ends
        2 = Critical Failure - something bad happens

        Returns:
            (TCDiceResult, outcome_description)
        """
        result = self.roll_action(plus_dice, minus_dice)

        if result.critical:
            outcome = "CRITICAL SUCCESS! Action succeeds with bonus effect."
        elif result.fumble:
            outcome = "CRITICAL FAILURE! Disaster strikes - roll on mishap table."
        elif result.success:
            outcome = "Success."
        else:
            outcome = "Failed. Activation ends."

        return result, outcome

    # =========================================================================
    # INJURY TABLE
    # =========================================================================

    def roll_injury(
        self,
        plus_dice: int = 0,
        minus_dice: int = 0,
    ) -> tuple[TCDiceResult, str, str]:
        """
        Roll on the Injury Table.

        2d6 result determines injury severity:
        - 2-6: Blood Marker (wounded but fighting)
        - 7-8: Downed (incapacitated, may recover)
        - 9-12: Out of Action (removed from play)

        Returns:
            (TCDiceResult, injury_type, description)
        """
        result = self.roll_2d6_with_modifiers(plus_dice, minus_dice)

        if result.total <= self.INJURY_BLOOD_MAX:
            injury_type = "blood"
            description = "Blood Marker - Model is wounded but continues fighting."
        elif result.total <= self.INJURY_DOWNED_MAX:
            injury_type = "downed"
            description = "DOWNED! Model is incapacitated. May recover in End Phase."
        else:
            injury_type = "out"
            description = "OUT OF ACTION! Model is removed from play."

        return result, injury_type, description

    # =========================================================================
    # STAT PARSING
    # =========================================================================

    def get_stat(self, unit: RosterUnit, stat_name: str, default: int = 0) -> int:
        """Get a stat value, handling various formats."""
        value = unit.get_stat(stat_name, unit.get_stat(stat_name.upper(), default))
        if isinstance(value, str):
            value = int(value.replace("+", "").replace("-", ""))
        return int(value) if value else default

    def get_ranged_skill(self, unit: RosterUnit) -> int:
        """Get ranged skill modifier (becomes +Dice)."""
        return self.get_stat(unit, "ranged", self.get_stat(unit, "RS", 0))

    def get_melee_skill(self, unit: RosterUnit) -> int:
        """Get melee skill modifier (becomes +Dice)."""
        return self.get_stat(unit, "melee", self.get_stat(unit, "MS", 0))

    def get_armour(self, unit: RosterUnit) -> int:
        """Get armour value (adds -Dice to injury rolls against this model)."""
        return self.get_stat(unit, "armour", self.get_stat(unit, "ARM", 0))

    # =========================================================================
    # SHOOTING
    # =========================================================================

    def resolve_shooting(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Resolve a shooting attack using Trench Crusade rules.

        Flow:
        1. Roll 2d6 ±Dice vs 7 to hit
        2. On hit, roll Injury (2d6 modified by weapon/armour)
        3. Injury result determines Blood/Downed/Out

        Args:
            attacker: The attacking model
            target: The target model
            weapon: Weapon profile dict
            modifiers: Situational modifiers (as ±Dice)

        Returns:
            AttackResult with complete breakdown
        """
        modifiers = modifiers or {}
        effects = []

        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon.get("name", "Unknown Weapon"),
        )

        # Get weapon stats
        shots = weapon.get("shots", weapon.get("rof", 1))
        if isinstance(shots, str):
            shots = int(shots)

        # Weapon grants ±Dice to injury rolls
        weapon_injury_bonus = weapon.get("injury_dice", weapon.get("damage", 0))
        if isinstance(weapon_injury_bonus, str):
            weapon_injury_bonus = int(weapon_injury_bonus)

        ap = weapon.get("ap", weapon.get("AP", 0))
        if isinstance(ap, str):
            ap = int(ap.replace("-", ""))

        # Get skill as +Dice
        skill_dice = self.get_ranged_skill(attacker)

        # Calculate total ±Dice for to-hit
        plus_dice = skill_dice
        minus_dice = 0

        if modifiers.get("aimed"):
            plus_dice += 1
            effects.append("Aimed (+1 Dice)")
        if modifiers.get("cover"):
            minus_dice += 1
            effects.append("Target in cover (-1 Dice)")
        if modifiers.get("moving"):
            minus_dice += 1
            effects.append("Firing while moving (-1 Dice)")
        if modifiers.get("long_range"):
            minus_dice += 1
            effects.append("Long range (-1 Dice)")

        # Existing blood markers can be spent for -Dice
        blood_spent = modifiers.get("blood_spent", 0)
        if blood_spent > 0:
            minus_dice += blood_spent
            effects.append(f"Blood markers spent (-{blood_spent} Dice)")

        # Roll to hit
        to_hit_rolls = []
        hits = 0
        criticals = 0

        for _ in range(shots):
            roll = self.roll_action(plus_dice, minus_dice)

            # Convert to DiceRoll for compatibility
            dice_roll = DiceRoll(
                die_type=6,
                result=roll.total,
                target=self.BASE_TARGET,
                success=roll.success,
                critical=roll.critical,
                fumble=roll.fumble,
            )
            to_hit_rolls.append(dice_roll)

            if roll.fumble:
                effects.append(f"FUMBLE! [{roll.dice_kept[0]}+{roll.dice_kept[1]}=2] Weapon jams!")
            elif roll.critical:
                hits += 1
                criticals += 1
                effects.append(f"CRITICAL HIT! [{roll.dice_kept[0]}+{roll.dice_kept[1]}=12]")
            elif roll.success:
                hits += 1
                effects.append(f"Hit [{roll.dice_kept[0]}+{roll.dice_kept[1]}={roll.total}]")
            else:
                effects.append(f"Miss [{roll.dice_kept[0]}+{roll.dice_kept[1]}={roll.total}]")

        result.to_hit_rolls = to_hit_rolls
        result.hits = hits

        if hits == 0:
            result.effects = effects
            return result

        # Roll injuries for each hit
        target_armour = self.get_armour(target)
        injury_plus = weapon_injury_bonus + criticals  # Crits add +1 injury dice
        injury_minus = max(0, target_armour - ap)  # Armour reduces, AP counters

        blood_markers = 0
        downed = 0
        out_of_action = 0

        for i in range(hits):
            is_crit = i < criticals
            extra_plus = 1 if is_crit else 0

            injury_roll, injury_type, _ = self.roll_injury(
                plus_dice=injury_plus + extra_plus,
                minus_dice=injury_minus
            )

            if injury_type == "blood":
                blood_markers += 1
                effects.append(f"Injury [{injury_roll.total}]: Blood marker")
            elif injury_type == "downed":
                downed += 1
                effects.append(f"Injury [{injury_roll.total}]: DOWNED!")
            else:
                out_of_action += 1
                effects.append(f"Injury [{injury_roll.total}]: OUT OF ACTION!")

        result.wounds_caused = hits
        result.damage_dealt = blood_markers + (downed * 2) + (out_of_action * 3)
        result.saves_failed = hits  # No save roll in TC
        result.models_killed = out_of_action

        result.effects = effects
        return result

    # =========================================================================
    # MELEE
    # =========================================================================

    def resolve_melee(
        self,
        attacker: RosterUnit,
        defender: RosterUnit,
        modifiers: dict[str, int] | None = None,
    ) -> MeleeResult:
        """
        Resolve melee combat using Trench Crusade rules.

        Both fighters roll 2d6 ±Dice. Charger may get bonus.
        Winner inflicts injury on loser.
        """
        modifiers = modifiers or {}

        # Get melee weapon
        melee_weapon = {"name": "Bayonet/Knife", "injury_dice": 0, "ap": 0}
        for w in attacker.weapons:
            w_type = str(w.get("type", "")).lower()
            if w_type in ("melee", "ccw", "close_combat"):
                melee_weapon = w
                break

        # Attacker's roll
        attacker_skill = self.get_melee_skill(attacker)
        plus_dice = attacker_skill
        minus_dice = 0

        if modifiers.get("charging"):
            plus_dice += 1

        attacker_result = self._resolve_melee_attack(
            attacker, defender, melee_weapon, plus_dice, minus_dice
        )

        # Defender strikes back unless incapacitated
        defender_result = None
        if attacker_result.models_killed == 0:
            def_weapon = {"name": "Bayonet/Knife", "injury_dice": 0, "ap": 0}
            for w in defender.weapons:
                w_type = str(w.get("type", "")).lower()
                if w_type in ("melee", "ccw", "close_combat"):
                    def_weapon = w
                    break

            defender_skill = self.get_melee_skill(defender)
            defender_result = self._resolve_melee_attack(
                defender, attacker, def_weapon, defender_skill, 0
            )

        return MeleeResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attacker_result=attacker_result,
            defender_result=defender_result,
        )

    def _resolve_melee_attack(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        plus_dice: int,
        minus_dice: int,
    ) -> AttackResult:
        """Resolve a single melee attack."""
        effects = []

        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon.get("name", "Melee"),
        )

        # Roll to hit (2d6 vs 7)
        roll = self.roll_action(plus_dice, minus_dice)

        dice_roll = DiceRoll(
            die_type=6,
            result=roll.total,
            target=self.BASE_TARGET,
            success=roll.success,
            critical=roll.critical,
            fumble=roll.fumble,
        )
        result.to_hit_rolls = [dice_roll]

        if roll.fumble:
            effects.append(f"FUMBLE! [{roll.total}] Left yourself open!")
            result.hits = 0
            result.effects = effects
            return result

        if not roll.success:
            effects.append(f"Miss [{roll.total}]")
            result.hits = 0
            result.effects = effects
            return result

        effects.append(f"Hit! [{roll.total}]" + (" CRITICAL!" if roll.critical else ""))
        result.hits = 1

        # Roll injury
        weapon_bonus = weapon.get("injury_dice", weapon.get("damage", 0))
        if isinstance(weapon_bonus, str):
            weapon_bonus = int(weapon_bonus)

        ap = weapon.get("ap", 0)
        if isinstance(ap, str):
            ap = int(ap.replace("-", ""))

        target_armour = self.get_armour(target)
        injury_plus = weapon_bonus + (1 if roll.critical else 0)
        injury_minus = max(0, target_armour - ap)

        injury_roll, injury_type, desc = self.roll_injury(injury_plus, injury_minus)
        effects.append(f"Injury [{injury_roll.total}]: {injury_type.upper()}")

        result.wounds_caused = 1
        if injury_type == "out":
            result.models_killed = 1
            result.damage_dealt = 3
        elif injury_type == "downed":
            result.damage_dealt = 2
        else:
            result.damage_dealt = 1

        result.saves_failed = 1
        result.effects = effects
        return result

    # =========================================================================
    # MORALE / HORROR
    # =========================================================================

    def check_morale(
        self,
        unit: RosterUnit,
        casualties: int,
        test_type: str = "morale",
        modifiers: dict[str, int] | None = None,
    ) -> MoraleResult:
        """
        Check morale using Trench Crusade rules.

        Roll 2d6 ±Dice vs 7. Success = hold, Fail = Shaken, Fumble = Broken.

        TC uses Morale tests when:
        - Model takes Blood markers
        - Friendly model incapacitated nearby
        - Facing terrifying enemies
        """
        modifiers = modifiers or {}

        morale_stat = self.get_stat(unit, "morale", self.get_stat(unit, "MOR", 0))

        # Build ±Dice
        plus_dice = morale_stat
        minus_dice = 0

        if casualties >= 2:
            minus_dice += 1
        if modifiers.get("terrifying"):
            minus_dice += 2
        if modifiers.get("faithful_nearby"):
            plus_dice += 1

        roll = self.roll_action(plus_dice, minus_dice)

        dice_roll = DiceRoll(
            die_type=6,
            result=roll.total,
            target=self.BASE_TARGET,
            success=roll.success,
            critical=roll.critical,
            fumble=roll.fumble,
        )

        if roll.fumble:
            passed = False
            consequence = "BROKEN! Model flees in terror!"
        elif roll.critical:
            passed = True
            consequence = "RESOLUTE! Model stands firm with renewed faith!"
        elif roll.success:
            passed = True
            consequence = "Model holds position."
        else:
            passed = False
            consequence = "SHAKEN! Model must fall back and recover."

        return MoraleResult(
            unit_name=unit.name,
            test_type=test_type,
            leadership=morale_stat,
            roll=dice_roll,
            modifiers=[],
            passed=passed,
            consequence=consequence,
        )

    # =========================================================================
    # SPECIAL MECHANICS
    # =========================================================================

    def roll_horror_check(
        self,
        unit: RosterUnit,
        horror_level: int = 1,
    ) -> MoraleResult:
        """
        Roll a Horror check when facing demonic entities.

        Horror levels add -Dice to the roll.
        """
        morale = self.get_stat(unit, "morale", 0)

        roll = self.roll_action(plus_dice=morale, minus_dice=horror_level)

        dice_roll = DiceRoll(
            die_type=6,
            result=roll.total,
            target=self.BASE_TARGET,
            success=roll.success,
            critical=roll.critical,
            fumble=roll.fumble,
        )

        if roll.fumble:
            consequence = "MADNESS! Model is overcome with terror, loses next activation."
        elif not roll.success:
            consequence = "SHAKEN! Model must retreat from the horror."
        elif roll.critical:
            consequence = "DEFIANT! Model steels themselves against the darkness."
        else:
            consequence = "Model withstands the horror."

        return MoraleResult(
            unit_name=unit.name,
            test_type="horror",
            leadership=morale,
            roll=dice_roll,
            modifiers=[f"Horror Level {horror_level}"],
            passed=roll.success,
            consequence=consequence,
        )

    def roll_faith_action(
        self,
        unit: RosterUnit,
        difficulty_dice: int = 0,
    ) -> tuple[TCDiceResult, str]:
        """
        Roll for a Faith-based action (prayers, blessings, etc.).

        Standard 2d6 vs 7, Faith stat adds +Dice.
        Some prayers are harder (add -Dice as difficulty).
        """
        faith = self.get_stat(unit, "faith", self.get_stat(unit, "FAI", 0))

        roll = self.roll_action(plus_dice=faith, minus_dice=difficulty_dice)

        if roll.critical:
            result_text = "MIRACULOUS! Divine power manifests with great effect!"
        elif roll.fumble:
            result_text = "FORSAKEN! The darkness notices your prayers..."
        elif roll.success:
            result_text = "Prayer answered. Faith action succeeds."
        else:
            result_text = "Silence. The heavens do not respond."

        return roll, result_text
