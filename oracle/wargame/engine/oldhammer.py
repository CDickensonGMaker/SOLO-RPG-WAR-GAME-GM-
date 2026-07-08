"""
Oldhammer 2E (Warhammer 40,000 2nd Edition) Rules Engine.

Implements the classic crunchy 2nd Edition rules:
- BS chart for shooting
- WS vs WS chart for melee
- Strength vs Toughness wound chart
- Armor save modifiers by strength
- Sustained fire dice (jam on doubles!)
- Gets Hot! for plasma weapons
- Vehicle damage charts
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from oracle.tomlio import load_toml

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
class SustainedFireResult:
    """Result of sustained fire dice roll."""

    dice_rolled: list[int]
    jammed: bool
    extra_shots: int
    jam_dice: list[int] = field(default_factory=list)


@dataclass
class GetsHotResult:
    """Result of Gets Hot! check."""

    triggered: bool
    wound_roll: DiceRoll | None = None
    save_roll: DiceRoll | None = None
    wounded: bool = False


class OldhammerRulesEngine(RulesEngine):
    """
    Rules engine for Warhammer 40,000 2nd Edition.

    The classic edition with armor save modifiers, sustained fire,
    and all the crunchy goodness of early 90s wargaming.
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """Initialize the Oldhammer rules engine."""
        super().__init__(dice_roller)
        self._load_charts()

    def _load_charts(self) -> None:
        """Load charts from TOML data file."""
        data_path = Path(__file__).parent.parent / "data" / "oldhammer_charts.toml"

        charts = load_toml(data_path) if data_path.exists() else None
        # Fall back to hardcoded charts if the file is missing or unreadable
        self._charts = charts if charts is not None else self._default_charts()

    def _default_charts(self) -> dict:
        """Fallback charts if TOML not available."""
        return {
            "bs_chart": {
                "1": 6, "2": 5, "3": 4, "4": 3, "5": 2,
                "6": 2, "7": 2, "8": 2
            },
            "wound_chart": {
                "4": 2, "3": 2, "2": 2, "1": 3, "0": 4,
                "-1": 5, "-2": 6, "-3": 6, "-4": 6
            },
            "armor_modifiers": {
                "1": 0, "2": 0, "3": 0, "4": -1, "5": -2,
                "6": -3, "7": -4, "8": -5, "9": -6, "10": -6
            }
        }

    @property
    def system_name(self) -> str:
        return "Warhammer 40,000 2nd Edition"

    @property
    def system_id(self) -> str:
        return "oldhammer_2e"

    # =========================================================================
    # TO-HIT CALCULATIONS
    # =========================================================================

    def get_bs_to_hit(self, bs: int) -> int:
        """
        Get to-hit target from BS chart.

        Args:
            bs: Ballistic Skill value (1-10)

        Returns:
            Target number needed on d6
        """
        bs_chart = self._charts.get("bs_chart", {})
        return bs_chart.get(str(bs), 6)

    def get_ws_to_hit(self, attacker_ws: int, defender_ws: int) -> int:
        """
        Get to-hit target from WS vs WS chart.

        Args:
            attacker_ws: Attacker's Weapon Skill
            defender_ws: Defender's Weapon Skill

        Returns:
            Target number needed on d6
        """
        ws_chart = self._charts.get("ws_chart", {})
        key = f"{attacker_ws}.{defender_ws}"
        return ws_chart.get(key, 4)

    # =========================================================================
    # TO-WOUND CALCULATIONS
    # =========================================================================

    def get_to_wound(self, strength: int, toughness: int) -> int:
        """
        Get to-wound target from S vs T chart.

        Args:
            strength: Attacker's Strength
            toughness: Defender's Toughness

        Returns:
            Target number needed on d6 (0 = impossible)
        """
        # Cannot wound if strength is less than half toughness
        if strength < (toughness // 2):
            return 0  # Impossible to wound

        diff = strength - toughness
        # Clamp to chart range
        diff = max(-4, min(4, diff))

        wound_chart = self._charts.get("wound_chart", {})
        return wound_chart.get(str(diff), 4)

    # =========================================================================
    # ARMOR SAVES
    # =========================================================================

    def get_armor_modifier(self, strength: int) -> int:
        """
        Get armor save modifier based on weapon strength.

        Args:
            strength: Strength of the attack

        Returns:
            Modifier to armor save (negative makes saves harder)
        """
        armor_mods = self._charts.get("armor_modifiers", {})
        return armor_mods.get(str(strength), 0)

    def get_armor_save(
        self,
        target: RosterUnit,
        strength: int,
        ap: int = 0,
    ) -> int | None:
        """
        Calculate modified armor save.

        In 2nd Ed, strength affects saves, plus any additional AP.

        Args:
            target: Unit making the save
            strength: Strength of the attack
            ap: Additional armor piercing (e.g., power weapons)

        Returns:
            Modified save target, or None if no save allowed
        """
        base_save = target.get_stat("Sv", 7)

        # Parse save string if needed (e.g., "3+" -> 3)
        if isinstance(base_save, str):
            base_save = int(base_save.replace("+", ""))

        # Apply strength-based modifier
        strength_mod = self.get_armor_modifier(strength)
        modified = base_save - strength_mod  # Subtract negative = add

        # Apply additional AP (power weapons, etc.)
        modified += ap

        if modified > 6:
            return None  # No save possible
        return max(2, modified)  # Can't be better than 2+

    # =========================================================================
    # SUSTAINED FIRE
    # =========================================================================

    def roll_sustained_fire(self, dice_count: int) -> SustainedFireResult:
        """
        Roll sustained fire dice.

        In 2nd Ed, sustained fire weapons roll extra dice.
        Each die 2+ adds that many extra shots, but doubles jam!

        Args:
            dice_count: Number of sustained fire dice

        Returns:
            SustainedFireResult with jam status and extra shots
        """
        rolls = self.dice.roll_dice(dice_count)

        # Check for doubles (jam!)
        seen = set()
        jammed = False
        jam_dice = []

        for roll in rolls:
            if roll in seen:
                jammed = True
                jam_dice.append(roll)
            seen.add(roll)

        if jammed:
            return SustainedFireResult(
                dice_rolled=rolls,
                jammed=True,
                extra_shots=0,
                jam_dice=jam_dice,
            )

        # Count extra shots (each die showing 2+ adds that many shots)
        extra_shots = sum(r for r in rolls if r >= 2)

        return SustainedFireResult(
            dice_rolled=rolls,
            jammed=False,
            extra_shots=extra_shots,
        )

    # =========================================================================
    # GETS HOT!
    # =========================================================================

    def check_gets_hot(
        self,
        to_hit_rolls: list[DiceRoll],
        firer: RosterUnit,
    ) -> GetsHotResult:
        """
        Check for Gets Hot! (plasma weapon overheat).

        Any roll of 1 to hit causes an automatic wound.

        Args:
            to_hit_rolls: The to-hit dice that were rolled
            firer: The unit firing the plasma weapon

        Returns:
            GetsHotResult with wound outcome
        """
        ones = [r for r in to_hit_rolls if r.result == 1]

        if not ones:
            return GetsHotResult(triggered=False)

        # Gets Hot triggered! Roll save for each 1
        # Firer takes an automatic wound (can save)
        save_target = firer.get_stat("Sv", 7)
        if isinstance(save_target, str):
            save_target = int(save_target.replace("+", ""))

        # Gets Hot wounds are typically S4, so -1 modifier
        modified_save = save_target + 1  # -1 save mod

        if modified_save > 6:
            # No save possible
            return GetsHotResult(
                triggered=True,
                wounded=True,
            )

        save_roll = self.dice.roll_check(1, max(2, modified_save))[0]

        return GetsHotResult(
            triggered=True,
            save_roll=save_roll,
            wounded=not save_roll.success,
        )

    # =========================================================================
    # SHOOTING RESOLUTION
    # =========================================================================

    def resolve_shooting(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Resolve a shooting attack using 2nd Edition rules.

        Args:
            attacker: The attacking unit
            target: The target unit
            weapon: Weapon profile dict with range, strength, shots, etc.
            modifiers: Situational modifiers (cover, movement, etc.)

        Returns:
            AttackResult with complete dice breakdown
        """
        modifiers = modifiers or {}
        effects = []

        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon.get("name", "Unknown Weapon"),
        )

        # Get weapon stats
        weapon_strength = int(weapon.get("strength", weapon.get("S", 4)))
        base_shots = weapon.get("shots", "1")
        weapon_ap = int(weapon.get("ap", weapon.get("AP", 0)))
        special_rules = weapon.get("special", weapon.get("abilities", []))

        # Handle variable shots (e.g., "2d6", "d6")
        if isinstance(base_shots, str):
            if "d6" in base_shots.lower():
                if base_shots.lower() == "d6":
                    base_shots = self.dice.roll_d6()
                elif "2d6" in base_shots.lower():
                    base_shots = self.dice.roll_2d6()
                else:
                    # Try to parse "Xd6" format
                    try:
                        num = int(base_shots.lower().replace("d6", ""))
                        base_shots = sum(self.dice.roll_d6() for _ in range(num))
                    except ValueError:
                        base_shots = 1
            else:
                base_shots = int(base_shots)

        num_shots = base_shots

        # Sustained Fire
        sustained_fire = weapon.get("sustained_fire", 0)
        if sustained_fire > 0:
            sf_result = self.roll_sustained_fire(sustained_fire)
            if sf_result.jammed:
                effects.append(f"JAMMED! Rolled {sf_result.dice_rolled}, doubles on {sf_result.jam_dice}")
                result.effects = effects
                return result  # No shots fired
            else:
                num_shots += sf_result.extra_shots
                effects.append(f"Sustained Fire: {sf_result.dice_rolled} = +{sf_result.extra_shots} shots")

        # Calculate to-hit target
        bs = attacker.get_stat("BS", 3)
        if isinstance(bs, str):
            bs = int(bs.replace("+", ""))
        to_hit_target = self.get_bs_to_hit(bs)

        # Apply to-hit modifiers
        to_hit_mod = modifiers.get("to_hit", 0)
        if modifiers.get("target_in_cover"):
            to_hit_mod += 1
            effects.append("Cover: +1 to hit")
        if modifiers.get("moved"):
            to_hit_mod += 1
            effects.append("Moved: +1 to hit")

        modified_to_hit = min(6, max(2, to_hit_target + to_hit_mod))

        # Roll to hit
        to_hit_rolls = self.dice.roll_check(num_shots, modified_to_hit)
        result.to_hit_rolls = to_hit_rolls
        result.hits = len([r for r in to_hit_rolls if r.success])

        # Gets Hot! check for plasma weapons
        is_plasma = any("plasma" in str(r).lower() for r in special_rules) or \
                    "plasma" in weapon.get("name", "").lower()
        if is_plasma:
            gets_hot = self.check_gets_hot(to_hit_rolls, attacker)
            if gets_hot.triggered:
                if gets_hot.wounded:
                    effects.append("GETS HOT! Firer wounded!")
                else:
                    effects.append(f"Gets Hot! but saved on {gets_hot.save_roll.result}")

        if result.hits == 0:
            result.effects = effects
            return result

        # Roll to wound
        target_t = target.get_stat("T", 4)
        if isinstance(target_t, str):
            target_t = int(target_t)

        to_wound_target = self.get_to_wound(weapon_strength, target_t)

        if to_wound_target == 0:
            effects.append("Cannot wound! S too low vs T")
            result.effects = effects
            return result

        to_wound_rolls = self.dice.roll_check(result.hits, to_wound_target)
        result.to_wound_rolls = to_wound_rolls
        result.wounds_caused = len([r for r in to_wound_rolls if r.success])

        if result.wounds_caused == 0:
            result.effects = effects
            return result

        # Armor saves
        save_target = self.get_armor_save(target, weapon_strength, weapon_ap)

        # Check for ignoring armor (power weapons, rending 6s, etc.)
        ignores_armor = any("power" in str(r).lower() for r in special_rules)

        if ignores_armor:
            effects.append("Ignores armor saves!")
            result.saves_failed = result.wounds_caused
        elif save_target is None:
            effects.append("No save possible!")
            result.saves_failed = result.wounds_caused
        else:
            save_rolls = self.dice.roll_check(result.wounds_caused, save_target)
            result.save_rolls = save_rolls
            result.saves_made = len([r for r in save_rolls if r.success])
            result.saves_failed = result.wounds_caused - result.saves_made

        # Calculate damage and casualties
        damage_per_wound = int(weapon.get("damage", weapon.get("D", 1)))
        result.damage_dealt = result.saves_failed * damage_per_wound

        # Calculate models killed (based on wounds characteristic)
        target_wounds = target.get_stat("W", 1)
        if isinstance(target_wounds, str):
            target_wounds = int(target_wounds)

        if target_wounds == 1:
            result.models_killed = result.saves_failed
        else:
            # Multi-wound models - damage spills over
            remaining_damage = result.damage_dealt
            current_wounds = target.wounds_current or target_wounds
            kills = 0

            while remaining_damage >= current_wounds:
                remaining_damage -= current_wounds
                kills += 1
                current_wounds = target_wounds  # Next model at full wounds

            result.models_killed = kills

        result.effects = effects
        return result

    # =========================================================================
    # MELEE RESOLUTION
    # =========================================================================

    def resolve_melee(
        self,
        attacker: RosterUnit,
        defender: RosterUnit,
        modifiers: dict[str, int] | None = None,
    ) -> MeleeResult:
        """
        Resolve melee combat between two units.

        In 2nd Ed, combat is resolved by initiative order,
        but for simplicity we resolve attacker then defender.

        Args:
            attacker: The charging/attacking unit
            defender: The defending unit
            modifiers: Situational modifiers

        Returns:
            MeleeResult with both sides' attacks
        """
        modifiers = modifiers or {}

        # Get attacker stats
        attacker_ws = attacker.get_stat("WS", 3)
        attacker_s = attacker.get_stat("S", 3)
        attacker_a = attacker.get_stat("A", 1)
        if isinstance(attacker_ws, str):
            attacker_ws = int(attacker_ws)
        if isinstance(attacker_s, str):
            attacker_s = int(attacker_s)
        if isinstance(attacker_a, str):
            attacker_a = int(attacker_a)

        # Get defender stats
        defender_ws = defender.get_stat("WS", 3)
        defender_s = defender.get_stat("S", 3)
        defender_a = defender.get_stat("A", 1)
        defender_t = defender.get_stat("T", 3)
        if isinstance(defender_ws, str):
            defender_ws = int(defender_ws)
        if isinstance(defender_s, str):
            defender_s = int(defender_s)
        if isinstance(defender_a, str):
            defender_a = int(defender_a)
        if isinstance(defender_t, str):
            defender_t = int(defender_t)

        attacker_t = attacker.get_stat("T", 3)
        if isinstance(attacker_t, str):
            attacker_t = int(attacker_t)

        # Charging bonus
        if modifiers.get("charging"):
            attacker_a += 1

        # Get melee weapons (use first or default CCW)
        attacker_weapon = {"name": "Close Combat", "strength": attacker_s, "ap": 0}
        for w in attacker.weapons:
            if w.get("type", "").lower() in ("melee", "close combat", "ccw"):
                attacker_weapon = w
                break

        defender_weapon = {"name": "Close Combat", "strength": defender_s, "ap": 0}
        for w in defender.weapons:
            if w.get("type", "").lower() in ("melee", "close combat", "ccw"):
                defender_weapon = w
                break

        # Resolve attacker's attacks
        attacker_result = self._resolve_melee_attacks(
            attacker, defender, attacker_weapon,
            attacker_ws, defender_ws, attacker_a, defender_t
        )

        # Resolve defender's attacks (if still alive)
        defender_result = None
        defender_models_remaining = (defender.models_current or 1) - attacker_result.models_killed

        if defender_models_remaining > 0:
            # Scale attacks by remaining models
            defender_attacks = defender_a * defender_models_remaining
            defender_result = self._resolve_melee_attacks(
                defender, attacker, defender_weapon,
                defender_ws, attacker_ws, defender_attacks, attacker_t
            )

        return MeleeResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attacker_result=attacker_result,
            defender_result=defender_result,
        )

    def _resolve_melee_attacks(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        attacker_ws: int,
        defender_ws: int,
        num_attacks: int,
        target_t: int,
    ) -> AttackResult:
        """Helper to resolve one side's melee attacks."""
        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon.get("name", "Close Combat"),
        )

        effects = []
        weapon_strength = int(weapon.get("strength", weapon.get("S", attacker.get_stat("S", 3))))
        weapon_ap = int(weapon.get("ap", weapon.get("AP", 0)))
        special_rules = weapon.get("special", weapon.get("abilities", []))

        # Calculate to-hit
        to_hit_target = self.get_ws_to_hit(attacker_ws, defender_ws)

        # Roll to hit
        to_hit_rolls = self.dice.roll_check(num_attacks, to_hit_target)
        result.to_hit_rolls = to_hit_rolls
        result.hits = len([r for r in to_hit_rolls if r.success])

        if result.hits == 0:
            result.effects = effects
            return result

        # Roll to wound
        to_wound_target = self.get_to_wound(weapon_strength, target_t)

        if to_wound_target == 0:
            effects.append("Cannot wound!")
            result.effects = effects
            return result

        to_wound_rolls = self.dice.roll_check(result.hits, to_wound_target)
        result.to_wound_rolls = to_wound_rolls
        result.wounds_caused = len([r for r in to_wound_rolls if r.success])

        if result.wounds_caused == 0:
            result.effects = effects
            return result

        # Armor saves (melee weapon AP, no strength modifier in melee)
        # Power weapons ignore armor entirely
        ignores_armor = any("power" in str(r).lower() for r in special_rules)

        if ignores_armor:
            effects.append("Power weapon ignores armor!")
            result.saves_failed = result.wounds_caused
        else:
            save_target = self.get_armor_save(target, weapon_strength, weapon_ap)
            if save_target is None:
                result.saves_failed = result.wounds_caused
            else:
                save_rolls = self.dice.roll_check(result.wounds_caused, save_target)
                result.save_rolls = save_rolls
                result.saves_made = len([r for r in save_rolls if r.success])
                result.saves_failed = result.wounds_caused - result.saves_made

        # Calculate damage
        damage_per_wound = int(weapon.get("damage", weapon.get("D", 1)))
        result.damage_dealt = result.saves_failed * damage_per_wound

        # Calculate kills
        target_wounds = target.get_stat("W", 1)
        if isinstance(target_wounds, str):
            target_wounds = int(target_wounds)

        if target_wounds == 1:
            result.models_killed = result.saves_failed
        else:
            remaining = result.damage_dealt
            kills = 0
            current = target.wounds_current or target_wounds
            while remaining >= current:
                remaining -= current
                kills += 1
                current = target_wounds
            result.models_killed = kills

        result.effects = effects
        return result

    # =========================================================================
    # MORALE
    # =========================================================================

    def check_morale(
        self,
        unit: RosterUnit,
        casualties: int,
        test_type: str = "break",
        modifiers: dict[str, int] | None = None,
    ) -> MoraleResult:
        """
        Check unit morale (2nd Edition break test).

        Roll 2d6 <= Leadership to pass.

        Args:
            unit: The unit taking the test
            casualties: Number of casualties just suffered
            test_type: Type of test (break, rally, pinning)
            modifiers: Situational modifiers

        Returns:
            MoraleResult with outcome
        """
        modifiers = modifiers or {}

        ld = unit.get_stat("Ld", 7)
        if isinstance(ld, str):
            ld = int(ld)

        # Roll 2d6
        roll_result = self.dice.roll_2d6()
        roll = DiceRoll(
            die_type=6,
            result=roll_result,
            target=ld,
            success=roll_result <= ld,
            critical=roll_result == 2,
            fumble=roll_result == 12,
        )

        # Build modifier list
        mod_list = []
        total_mod = 0

        if casualties >= 3:
            mod = casualties - 2
            mod_list.append(("Heavy casualties", mod))
            total_mod += mod

        if modifiers.get("outnumbered"):
            mod_list.append(("Outnumbered", -1))
            total_mod -= 1

        if modifiers.get("in_cover"):
            mod_list.append(("In cover", 1))
            total_mod += 1

        if modifiers.get("near_banner"):
            mod_list.append(("Near banner", 1))
            total_mod += 1

        # Check if passed (roll + mods <= Ld)
        modified_result = roll_result + total_mod
        passed = modified_result <= ld

        # Determine consequence
        if test_type == "break":
            consequence = "Holds steady" if passed else "Falls back 2d6\""
        elif test_type == "rally":
            consequence = "Rallies!" if passed else "Continues to flee"
        elif test_type == "pinning":
            consequence = "Unpinned" if passed else "Remains pinned"
        else:
            consequence = "Passes" if passed else "Fails"

        return MoraleResult(
            unit_name=unit.name,
            test_type=test_type,
            leadership=ld,
            roll=roll,
            modifiers=mod_list,
            passed=passed,
            consequence=consequence,
        )
