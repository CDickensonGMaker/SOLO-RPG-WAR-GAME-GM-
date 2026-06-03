"""
Warhammer: The Old World Rules Engine.

Implements the rules for The Old World (2024), which is a refined
version of the classic Warhammer Fantasy Battle system:
- WS vs WS chart for melee to-hit
- BS chart for shooting to-hit
- Strength vs Toughness wound chart
- Armor saves with strength modifiers
- Combat resolution (wounds + ranks + standards + charging)
- Break tests and fleeing
- Rally mechanics
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

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
class CombatResolution:
    """Result of combat resolution calculation."""

    side_a_score: int
    side_b_score: int
    side_a_wounds: int
    side_b_wounds: int
    side_a_bonuses: list[tuple[str, int]]
    side_b_bonuses: list[tuple[str, int]]
    winner: str  # "a", "b", "draw"
    margin: int


class OldWorldRulesEngine(RulesEngine):
    """
    Rules engine for Warhammer: The Old World.

    Classic rank-and-flank with combat resolution, ranks bonuses,
    and the famous S vs T wound chart.
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """Initialize the Old World rules engine."""
        super().__init__(dice_roller)
        self._load_charts()

    def _load_charts(self) -> None:
        """Load charts from TOML data file."""
        # Default charts (The Old World uses similar charts to Oldhammer)
        self._charts = {
            # WS chart: "attacker.defender" -> to-hit
            "ws_chart": {
                "1.1": 4, "1.2": 4, "1.3": 5, "1.4": 5, "1.5": 5,
                "2.1": 3, "2.2": 4, "2.3": 4, "2.4": 4, "2.5": 5,
                "3.1": 3, "3.2": 3, "3.3": 4, "3.4": 4, "3.5": 4,
                "4.1": 3, "4.2": 3, "4.3": 3, "4.4": 4, "4.5": 4,
                "5.1": 3, "5.2": 3, "5.3": 3, "5.4": 3, "5.5": 4,
            },
            # BS chart
            "bs_chart": {
                "1": 6, "2": 5, "3": 4, "4": 3, "5": 2, "6": 1,
            },
            # Wound chart: S - T difference -> target
            "wound_chart": {
                "2": 2, "1": 3, "0": 4, "-1": 5, "-2": 6,
            },
            # Armor save modifiers
            "armor_modifiers": {
                "3": 0, "4": -1, "5": -2, "6": -3, "7": -4,
            },
        }

    @property
    def system_name(self) -> str:
        return "Warhammer: The Old World"

    @property
    def system_id(self) -> str:
        return "old_world"

    # =========================================================================
    # TO-HIT CALCULATIONS
    # =========================================================================

    def get_ws_to_hit(self, attacker_ws: int, defender_ws: int) -> int:
        """
        Get to-hit target from WS vs WS chart.

        The Old World uses a simplified chart compared to older editions.
        """
        ws_chart = self._charts.get("ws_chart", {})

        # Clamp values to chart range
        att_ws = max(1, min(5, attacker_ws))
        def_ws = max(1, min(5, defender_ws))

        key = f"{att_ws}.{def_ws}"
        return ws_chart.get(key, 4)

    def get_bs_to_hit(self, bs: int) -> int:
        """Get to-hit target from BS chart."""
        bs_chart = self._charts.get("bs_chart", {})
        return bs_chart.get(str(bs), 4)

    def get_to_hit(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        is_melee: bool = False,
    ) -> int:
        """Calculate to-hit based on melee or shooting."""
        if is_melee:
            att_ws = attacker.get_stat("WS", 3)
            def_ws = target.get_stat("WS", 3)
            if isinstance(att_ws, str):
                att_ws = int(att_ws)
            if isinstance(def_ws, str):
                def_ws = int(def_ws)
            return self.get_ws_to_hit(att_ws, def_ws)
        else:
            bs = attacker.get_stat("BS", 3)
            if isinstance(bs, str):
                bs = int(bs)
            return self.get_bs_to_hit(bs)

    # =========================================================================
    # TO-WOUND CALCULATIONS
    # =========================================================================

    def get_to_wound(self, strength: int, toughness: int) -> int:
        """
        Get to-wound target from S vs T chart.

        Standard Fantasy wound chart:
        - S = T: 4+
        - S > T: easier (3+ or 2+)
        - S < T: harder (5+ or 6+)
        """
        diff = strength - toughness

        # Clamp to chart range
        if diff >= 2:
            return 2
        elif diff == 1:
            return 3
        elif diff == 0:
            return 4
        elif diff == -1:
            return 5
        else:
            return 6

    # =========================================================================
    # ARMOR SAVES
    # =========================================================================

    def get_armor_modifier(self, strength: int) -> int:
        """Get armor save modifier based on strength."""
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

        In The Old World, strength affects armor saves similar to
        classic Warhammer.
        """
        base_save = target.get_stat("AS", target.get_stat("Sv", 7))
        if isinstance(base_save, str):
            base_save = int(base_save.replace("+", ""))

        # Apply strength modifier
        strength_mod = self.get_armor_modifier(strength)
        modified = base_save - strength_mod

        # Apply additional AP
        modified += ap

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
        Resolve a shooting attack using Old World rules.

        Flow:
        1. Roll BS to hit
        2. Roll S vs T to wound
        3. Roll armor save (modified by S)
        """
        modifiers = modifiers or {}
        effects = []

        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon.get("name", "Unknown Weapon"),
        )

        # Get weapon stats
        strength = int(weapon.get("strength", weapon.get("S", 3)))
        shots = weapon.get("shots", weapon.get("A", 1))
        if isinstance(shots, str):
            shots = int(shots)
        ap = int(weapon.get("ap", 0))
        special = weapon.get("special", [])

        # Models shooting = unit size (each model fires)
        models = attacker.models_current or 1
        total_shots = shots * models

        # Calculate to-hit
        to_hit = self.get_to_hit(attacker, target, weapon, is_melee=False)

        # Apply modifiers
        if modifiers.get("long_range"):
            to_hit += 1
            effects.append("Long range: -1 to hit")
        if modifiers.get("cover"):
            to_hit += 1
            effects.append("Cover: -1 to hit")
        if modifiers.get("moved"):
            to_hit += 1
            effects.append("Moved: -1 to hit")

        to_hit = max(2, min(6, to_hit))

        # Roll to hit
        to_hit_rolls = self.dice.roll_check(total_shots, to_hit)
        result.to_hit_rolls = to_hit_rolls
        result.hits = sum(1 for r in to_hit_rolls if r.success)

        if result.hits == 0:
            result.effects = effects
            return result

        # Roll to wound
        target_t = target.get_stat("T", 3)
        if isinstance(target_t, str):
            target_t = int(target_t)

        to_wound = self.get_to_wound(strength, target_t)
        to_wound_rolls = self.dice.roll_check(result.hits, to_wound)
        result.to_wound_rolls = to_wound_rolls
        result.wounds_caused = sum(1 for r in to_wound_rolls if r.success)

        if result.wounds_caused == 0:
            result.effects = effects
            return result

        # Armor saves
        save_target = self.get_armor_save(target, strength, ap)

        # Check for rules that ignore armor
        if "killing blow" in str(special).lower():
            # Killing Blow on 6s to wound
            killing_blows = sum(1 for r in to_wound_rolls if r.critical)
            if killing_blows > 0:
                effects.append(f"Killing Blow! {killing_blows} auto-wounds")

        if save_target is None:
            result.saves_failed = result.wounds_caused
        else:
            save_rolls = self.dice.roll_check(result.wounds_caused, save_target)
            result.save_rolls = save_rolls
            result.saves_made = sum(1 for r in save_rolls if r.success)
            result.saves_failed = result.wounds_caused - result.saves_made

        # Calculate casualties
        result.damage_dealt = result.saves_failed

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
    # MELEE RESOLUTION
    # =========================================================================

    def resolve_melee(
        self,
        attacker: RosterUnit,
        defender: RosterUnit,
        modifiers: dict[str, int] | None = None,
    ) -> MeleeResult:
        """
        Resolve melee combat using Old World rules.

        In The Old World, combat is simultaneous by initiative,
        then combat resolution determines winner.
        """
        modifiers = modifiers or {}

        # Get stats
        att_ws = attacker.get_stat("WS", 3)
        att_s = attacker.get_stat("S", 3)
        att_a = attacker.get_stat("A", 1)
        att_i = attacker.get_stat("I", 3)
        if isinstance(att_ws, str):
            att_ws = int(att_ws)
        if isinstance(att_s, str):
            att_s = int(att_s)
        if isinstance(att_a, str):
            att_a = int(att_a)
        if isinstance(att_i, str):
            att_i = int(att_i)

        def_ws = defender.get_stat("WS", 3)
        def_s = defender.get_stat("S", 3)
        def_a = defender.get_stat("A", 1)
        def_i = defender.get_stat("I", 3)
        def_t = defender.get_stat("T", 3)
        if isinstance(def_ws, str):
            def_ws = int(def_ws)
        if isinstance(def_s, str):
            def_s = int(def_s)
        if isinstance(def_a, str):
            def_a = int(def_a)
        if isinstance(def_i, str):
            def_i = int(def_i)
        if isinstance(def_t, str):
            def_t = int(def_t)

        att_t = attacker.get_stat("T", 3)
        if isinstance(att_t, str):
            att_t = int(att_t)

        # Models attacking
        att_models = attacker.models_current or 1
        def_models = defender.models_current or 1

        # Total attacks
        total_att_attacks = att_a * att_models
        total_def_attacks = def_a * def_models

        # Resolve by initiative order
        # Higher I strikes first
        if att_i >= def_i:
            # Attacker strikes first
            attacker_result = self._resolve_melee_attacks(
                attacker, defender, att_ws, def_ws, att_s, def_t, total_att_attacks
            )

            # Defender casualties reduce their attacks
            remaining_defenders = def_models - attacker_result.models_killed
            if remaining_defenders > 0:
                adjusted_def_attacks = def_a * remaining_defenders
                defender_result = self._resolve_melee_attacks(
                    defender, attacker, def_ws, att_ws, def_s, att_t, adjusted_def_attacks
                )
            else:
                defender_result = None
        else:
            # Defender strikes first
            defender_result = self._resolve_melee_attacks(
                defender, attacker, def_ws, att_ws, def_s, att_t, total_def_attacks
            )

            remaining_attackers = att_models - (
                defender_result.models_killed if defender_result else 0
            )
            if remaining_attackers > 0:
                adjusted_att_attacks = att_a * remaining_attackers
                attacker_result = self._resolve_melee_attacks(
                    attacker, defender, att_ws, def_ws, att_s, def_t, adjusted_att_attacks
                )
            else:
                attacker_result = AttackResult(
                    attacker_name=attacker.name,
                    target_name=defender.name,
                    weapon_name="Close Combat",
                )

        # Combat resolution
        combat_res = self._calculate_combat_resolution(
            attacker, defender, attacker_result, defender_result, modifiers
        )

        return MeleeResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attacker_result=attacker_result,
            defender_result=defender_result,
            attacker_combat_res=combat_res.side_a_score,
            defender_combat_res=combat_res.side_b_score,
            winner={"a": "attacker", "b": "defender", "draw": "draw"}[combat_res.winner],
            margin=combat_res.margin,
        )

    def _resolve_melee_attacks(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        att_ws: int,
        def_ws: int,
        strength: int,
        toughness: int,
        num_attacks: int,
    ) -> AttackResult:
        """Resolve one side's melee attacks."""
        result = AttackResult(
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name="Close Combat",
        )

        # Roll to hit
        to_hit = self.get_ws_to_hit(att_ws, def_ws)
        to_hit_rolls = self.dice.roll_check(num_attacks, to_hit)
        result.to_hit_rolls = to_hit_rolls
        result.hits = sum(1 for r in to_hit_rolls if r.success)

        if result.hits == 0:
            return result

        # Roll to wound
        to_wound = self.get_to_wound(strength, toughness)
        to_wound_rolls = self.dice.roll_check(result.hits, to_wound)
        result.to_wound_rolls = to_wound_rolls
        result.wounds_caused = sum(1 for r in to_wound_rolls if r.success)

        if result.wounds_caused == 0:
            return result

        # Armor saves
        save_target = self.get_armor_save(target, strength)

        if save_target is None:
            result.saves_failed = result.wounds_caused
        else:
            save_rolls = self.dice.roll_check(result.wounds_caused, save_target)
            result.save_rolls = save_rolls
            result.saves_made = sum(1 for r in save_rolls if r.success)
            result.saves_failed = result.wounds_caused - result.saves_made

        # Calculate casualties
        result.damage_dealt = result.saves_failed

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

        return result

    def _calculate_combat_resolution(
        self,
        attacker: RosterUnit,
        defender: RosterUnit,
        att_result: AttackResult,
        def_result: AttackResult | None,
        modifiers: dict[str, int],
    ) -> CombatResolution:
        """Calculate combat resolution score."""
        # Wounds caused
        att_wounds = att_result.saves_failed if att_result else 0
        def_wounds = def_result.saves_failed if def_result else 0

        att_bonuses = [("Wounds caused", att_wounds)]
        def_bonuses = [("Wounds caused", def_wounds)]

        att_score = att_wounds
        def_score = def_wounds

        # Charging bonus
        if modifiers.get("charging"):
            att_bonuses.append(("Charging", 1))
            att_score += 1

        # Rank bonus (up to +3)
        att_ranks = attacker.get_stat("ranks", 0)
        def_ranks = defender.get_stat("ranks", 0)
        if isinstance(att_ranks, str):
            att_ranks = int(att_ranks)
        if isinstance(def_ranks, str):
            def_ranks = int(def_ranks)

        if att_ranks > 0:
            rank_bonus = min(3, att_ranks - 1)
            if rank_bonus > 0:
                att_bonuses.append(("Ranks", rank_bonus))
                att_score += rank_bonus

        if def_ranks > 0:
            rank_bonus = min(3, def_ranks - 1)
            if rank_bonus > 0:
                def_bonuses.append(("Ranks", rank_bonus))
                def_score += rank_bonus

        # Standard bearer
        if attacker.get_stat("standard", False):
            att_bonuses.append(("Standard", 1))
            att_score += 1
        if defender.get_stat("standard", False):
            def_bonuses.append(("Standard", 1))
            def_score += 1

        # Determine winner
        if att_score > def_score:
            winner = "a"
            margin = att_score - def_score
        elif def_score > att_score:
            winner = "b"
            margin = def_score - att_score
        else:
            winner = "draw"
            margin = 0

        return CombatResolution(
            side_a_score=att_score,
            side_b_score=def_score,
            side_a_wounds=att_wounds,
            side_b_wounds=def_wounds,
            side_a_bonuses=att_bonuses,
            side_b_bonuses=def_bonuses,
            winner=winner,
            margin=margin,
        )

    # =========================================================================
    # MORALE (BREAK TESTS)
    # =========================================================================

    def check_morale(
        self,
        unit: RosterUnit,
        casualties: int,
        test_type: str = "break",
        modifiers: dict[str, int] | None = None,
    ) -> MoraleResult:
        """
        Check morale using Old World rules.

        Break test after losing combat:
        - Roll 2d6 <= Ld to pass
        - Add combat result margin to roll
        """
        modifiers = modifiers or {}

        ld = unit.get_stat("Ld", 7)
        if isinstance(ld, str):
            ld = int(ld)

        # Roll 2d6
        roll_result = self.dice.roll_2d6()

        mod_list = []
        total_mod = 0

        # Combat resolution modifier
        combat_margin = modifiers.get("combat_margin", 0)
        if combat_margin > 0:
            mod_list.append(("Lost combat by", combat_margin))
            total_mod += combat_margin

        # Outnumbered
        if modifiers.get("outnumbered"):
            mod_list.append(("Outnumbered", 1))
            total_mod += 1

        modified_roll = roll_result + total_mod

        roll = DiceRoll(
            die_type=6,
            result=roll_result,
            target=ld,
            success=modified_roll <= ld,
            critical=roll_result == 2,
            fumble=roll_result == 12,
        )

        passed = modified_roll <= ld

        # Stubborn units can re-roll
        if not passed and unit.get_stat("stubborn", False):
            # Re-roll
            roll_result = self.dice.roll_2d6()
            modified_roll = roll_result + total_mod
            passed = modified_roll <= ld
            mod_list.append(("Stubborn re-roll", 0))

        # Determine consequence
        if test_type == "break":
            if passed:
                consequence = "Holds the line!"
            else:
                consequence = "Breaks and flees!"
        elif test_type == "rally":
            if passed:
                consequence = "Rallies!"
            else:
                consequence = "Continues to flee!"
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
