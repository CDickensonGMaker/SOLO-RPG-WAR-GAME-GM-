"""
OnePageRules (OPR) Rules Engine.

Implements the streamlined OPR rules used in:
- Grimdark Future (40K-style)
- Age of Fantasy (Fantasy Battle-style)
- Firefight (Kill Team-style)
- Skirmish (Warcry-style)

Core mechanics:
- Quality stat for to-hit (roll >= Quality)
- Defense stat for saves (roll >= Defense)
- AP(X) reduces Defense by X
- Special rules: Furious, Rending, Poison, Deadly(X), Blast(X), etc.
"""

from __future__ import annotations

import re
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
class SpecialRule:
    """A parsed special rule with parameters."""

    name: str
    value: int | None = None  # For rules like Deadly(3), AP(2)

    @classmethod
    def parse(cls, rule_str: str) -> "SpecialRule":
        """Parse a rule string like 'Deadly(3)' or 'Rending'."""
        # Match patterns like "Name(X)" or just "Name"
        match = re.match(r"(\w+)(?:\((\d+)\))?", rule_str)
        if match:
            name = match.group(1).lower()
            value = int(match.group(2)) if match.group(2) else None
            return cls(name=name, value=value)
        return cls(name=rule_str.lower())


class OPRRulesEngine(RulesEngine):
    """
    Rules engine for OnePageRules game systems.

    OPR uses a streamlined Quality/Defense system:
    - Quality determines to-hit (roll >= Quality)
    - Defense determines save (roll >= Defense - AP)
    - Special rules add tactical depth
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """Initialize the OPR rules engine."""
        super().__init__(dice_roller)

    @property
    def system_name(self) -> str:
        return "OnePageRules"

    @property
    def system_id(self) -> str:
        return "opr"

    # =========================================================================
    # STAT PARSING
    # =========================================================================

    def parse_quality(self, quality: int | str) -> int:
        """
        Parse quality stat into target number.

        Args:
            quality: Quality value (e.g., 3, "3+", "3")

        Returns:
            Target number for d6
        """
        if isinstance(quality, str):
            quality = int(quality.replace("+", ""))
        return quality

    def parse_defense(self, defense: int | str) -> int:
        """
        Parse defense stat into base save target.

        Args:
            defense: Defense value (e.g., 4, "4+", "4")

        Returns:
            Base save target for d6
        """
        if isinstance(defense, str):
            defense = int(defense.replace("+", ""))
        return defense

    def parse_special_rules(
        self, rules: list[str] | None
    ) -> list[SpecialRule]:
        """Parse a list of special rule strings."""
        if not rules:
            return []
        # Filter out None and empty strings
        valid_rules = [r for r in rules if r and isinstance(r, str)]
        return [SpecialRule.parse(r) for r in valid_rules]

    def get_ap(self, weapon: dict[str, Any]) -> int:
        """Get AP value from weapon profile."""
        ap = weapon.get("ap", weapon.get("AP", 0))
        if isinstance(ap, str):
            # Handle "AP(2)" format
            match = re.search(r"(\d+)", ap)
            if match:
                return int(match.group(1))
            return 0
        return int(ap)

    # =========================================================================
    # SPECIAL RULES
    # =========================================================================

    def has_rule(self, rules: list[SpecialRule], name: str) -> SpecialRule | None:
        """Check if a rule is present and return it."""
        name_lower = name.lower()
        for rule in rules:
            if rule.name == name_lower:
                return rule
        return None

    def get_rule_value(
        self, rules: list[SpecialRule], name: str, default: int = 0
    ) -> int:
        """Get the value of a rule, or default if not present."""
        rule = self.has_rule(rules, name)
        if rule and rule.value is not None:
            return rule.value
        return default

    # =========================================================================
    # TO-HIT AND SAVES
    # =========================================================================

    def get_to_hit(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        is_melee: bool = False,
    ) -> int:
        """
        Get to-hit target from Quality stat.

        In OPR, to-hit is always just the Quality stat.
        """
        quality = attacker.get_stat("quality", attacker.get_stat("Q", "4+"))
        return self.parse_quality(quality)

    def get_to_wound(self, strength: int, toughness: int) -> int:
        """
        OPR doesn't have separate wound rolls.

        If hit, roll defense. This method returns 2 (auto-wound on hit).
        """
        return 2  # Always "wounds" on a hit

    def get_armor_save(
        self,
        target: RosterUnit,
        strength: int,
        ap: int = 0,
    ) -> int | None:
        """
        Calculate modified defense save.

        Args:
            target: Unit making the save
            strength: Not used in OPR
            ap: Armor Piercing value

        Returns:
            Modified defense target (7+ means no save)
        """
        defense = target.get_stat("defense", target.get_stat("D", "4+"))
        base = self.parse_defense(defense)
        modified = base + ap

        if modified > 6:
            return None
        return max(2, modified)

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
        Resolve a shooting attack using OPR rules.

        OPR flow:
        1. Roll Quality to hit
        2. Roll Defense to save (modified by AP)
        3. Apply wounds (1 per failed save, or more with Deadly)

        Args:
            attacker: The attacking unit
            target: The target unit
            weapon: Weapon profile dict
            modifiers: Situational modifiers

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

        # Parse weapon
        shots = weapon.get("shots", weapon.get("A", 1))
        if isinstance(shots, str):
            if "d6" in shots.lower():
                if shots.lower() == "d6":
                    shots = self.dice.roll_d6()
                elif "2d6" in shots.lower():
                    shots = self.dice.roll_2d6()
                else:
                    shots = 1
            else:
                shots = int(shots)

        ap = self.get_ap(weapon)
        special = weapon.get("special", weapon.get("abilities", []))
        if isinstance(special, str):
            special = [special]
        rules = self.parse_special_rules(special)

        # Check for Blast
        blast_rule = self.has_rule(rules, "blast")
        if blast_rule and blast_rule.value:
            # Blast(X) generates X hits automatically
            shots = blast_rule.value
            effects.append(f"Blast({blast_rule.value})!")

        # Roll to hit (Quality test)
        quality = self.get_to_hit(attacker, target, weapon, is_melee=False)
        to_hit_rolls = self.dice.roll_check(shots, quality)
        result.to_hit_rolls = to_hit_rolls

        # Count hits
        hits = sum(1 for r in to_hit_rolls if r.success)

        # Rending: 6s to hit auto-wound (ignore save)
        rending = self.has_rule(rules, "rending")
        rending_wounds = 0
        if rending:
            rending_wounds = sum(1 for r in to_hit_rolls if r.critical)
            hits -= rending_wounds  # These don't need saves
            if rending_wounds > 0:
                effects.append(f"Rending: {rending_wounds} auto-wounds!")

        result.hits = hits + rending_wounds

        if result.hits == 0:
            result.effects = effects
            return result

        # Poison: Always wounds, just need to hit
        # (OPR doesn't have separate wound rolls anyway)

        # Defense saves (only for non-rending hits)
        save_target = self.get_armor_save(target, 0, ap)

        if save_target is None:
            result.saves_failed = hits
        else:
            if hits > 0:
                save_rolls = self.dice.roll_check(hits, save_target)
                result.save_rolls = save_rolls
                result.saves_made = sum(1 for r in save_rolls if r.success)
                result.saves_failed = hits - result.saves_made

        # Add rending wounds (no save)
        result.saves_failed += rending_wounds

        # Calculate damage
        # Deadly(X) does X damage per wound instead of 1
        deadly = self.get_rule_value(rules, "deadly", 1)
        damage_per_wound = deadly

        result.wounds_caused = result.saves_failed
        result.damage_dealt = result.saves_failed * damage_per_wound

        # Calculate casualties (wounds vs Tough)
        tough = target.get_stat("tough", target.get_stat("Tough", 1))
        if isinstance(tough, str):
            tough = int(tough)

        if tough <= 1:
            result.models_killed = result.saves_failed
        else:
            # Multi-wound models
            remaining_damage = result.damage_dealt
            current_wounds = target.wounds_current or tough
            kills = 0

            while remaining_damage >= current_wounds:
                remaining_damage -= current_wounds
                kills += 1
                current_wounds = tough

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
        Resolve melee combat using OPR rules.

        In OPR, melee is resolved similarly to shooting but uses
        melee weapons and may have Furious bonus.
        """
        modifiers = modifiers or {}

        # Get attacks
        attacks = attacker.get_stat("A", attacker.get_stat("attacks", 1))
        if isinstance(attacks, str):
            attacks = int(attacks)

        # Get melee weapon or default
        melee_weapon = {"name": "Close Combat", "shots": attacks, "ap": 0}
        for w in attacker.weapons:
            w_type = str(w.get("type", "")).lower()
            if w_type in ("melee", "ccw"):
                melee_weapon = w
                melee_weapon["shots"] = attacks  # Use unit's attack stat
                break

        # Check for Furious (extra attack on charge)
        rules = self.parse_special_rules(
            attacker.special_rules if hasattr(attacker, "special_rules") else []
        )
        if modifiers.get("charging") and self.has_rule(rules, "furious"):
            melee_weapon["shots"] = attacks + 1

        # Resolve attacker's attacks
        attacker_result = self.resolve_shooting(
            attacker, defender, melee_weapon, modifiers
        )
        attacker_result.weapon_name = melee_weapon.get("name", "Close Combat")

        # Defender strikes back
        defender_result = None
        if defender.models_current and defender.models_current > attacker_result.models_killed:
            defender_attacks = defender.get_stat("A", 1)
            if isinstance(defender_attacks, str):
                defender_attacks = int(defender_attacks)

            defender_weapon = {"name": "Close Combat", "shots": defender_attacks, "ap": 0}
            for w in defender.weapons:
                w_type = str(w.get("type", "")).lower()
                if w_type in ("melee", "ccw"):
                    defender_weapon = w
                    defender_weapon["shots"] = defender_attacks
                    break

            defender_result = self.resolve_shooting(
                defender, attacker, defender_weapon
            )
            defender_result.weapon_name = defender_weapon.get("name", "Close Combat")

        return MeleeResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attacker_result=attacker_result,
            defender_result=defender_result,
        )

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
        Check morale using OPR rules.

        In OPR, units take morale tests when they lose half their models.
        Roll Quality - if failed, unit is Shaken.
        """
        modifiers = modifiers or {}

        quality = unit.get_stat("quality", unit.get_stat("Q", 4))
        if isinstance(quality, str):
            quality = int(quality.replace("+", ""))

        # Roll morale (same as Quality test)
        roll_result = self.dice.roll_d6()
        roll = DiceRoll(
            die_type=6,
            result=roll_result,
            target=quality,
            success=roll_result >= quality,
            critical=roll_result == 6,
            fumble=roll_result == 1,
        )

        passed = roll.success

        # Fearless units auto-pass
        rules = self.parse_special_rules(
            unit.special_rules if hasattr(unit, "special_rules") else []
        )
        if self.has_rule(rules, "fearless"):
            passed = True

        if passed:
            consequence = "Unit holds!"
        else:
            consequence = "Unit is Shaken! -1 to hit until rallied."

        return MoraleResult(
            unit_name=unit.name,
            test_type=test_type,
            leadership=quality,
            roll=roll,
            modifiers=[],
            passed=passed,
            consequence=consequence,
        )
