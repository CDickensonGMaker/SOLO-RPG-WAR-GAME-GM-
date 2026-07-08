"""
Seeded characterization tests for the wargame rules engines.

These tests pin the CURRENT behavior of the four engines (OPR, Oldhammer 2E,
Old World, Trench Crusade) using injected, seeded DiceRollers:

    Engine(dice_roller=DiceRoller(rng=random.Random(seed)))

The expected values below were captured by running the engines once and
recording the output. They are NOT hand-derived from the tabletop rules.
Their purpose is to make a future refactor of the duplicated combat code
verifiable: if a refactor changes any of these numbers, behavior changed.

No GUI imports. Pure model/engine layer.
"""

import random

import pytest

from oracle.roster import RosterUnit, SlotType
from oracle.wargame.engine.base import DiceRoller, RollingMode
from oracle.wargame.engine.opr import OPRRulesEngine
from oracle.wargame.engine.oldhammer import OldhammerRulesEngine
from oracle.wargame.engine.old_world import OldWorldRulesEngine
from oracle.wargame.engine.trench_crusade import TrenchCrusadeEngine


# =============================================================================
# HELPERS
# =============================================================================

def seeded_roller(seed: int) -> DiceRoller:
    """A DiceRoller with a deterministic RNG."""
    return DiceRoller(rng=random.Random(seed))


def make_unit(name, stats, weapons=None, models=1, wounds=1, abilities=None):
    """Build a minimal RosterUnit directly (no RosterManager singleton)."""
    return RosterUnit(
        id=name.lower().replace(" ", "_"),
        name=name,
        slot_type=SlotType.TROOPS,
        stats=stats,
        weapons=weapons or [],
        abilities=abilities or [],
        wounds_current=wounds,
        wounds_max=wounds,
        models_current=models,
        models_max=models,
    )


def attack_snapshot(result):
    """Comparable snapshot of an AttackResult for determinism checks."""
    return (
        result.hits,
        result.wounds_caused,
        result.saves_made,
        result.saves_failed,
        result.damage_dealt,
        result.models_killed,
        [r.result for r in result.to_hit_rolls],
        [r.result for r in result.to_wound_rolls],
        [r.result for r in result.save_rolls],
        list(result.effects),
    )


def melee_snapshot(result):
    """Comparable snapshot of a MeleeResult."""
    return (
        attack_snapshot(result.attacker_result),
        attack_snapshot(result.defender_result) if result.defender_result else None,
        result.attacker_combat_res,
        result.defender_combat_res,
        result.winner,
        result.margin,
    )


# =============================================================================
# DICE ROLLER
# =============================================================================

class TestDiceRoller:
    """Seeded unit tests for the injectable DiceRoller."""

    def test_seeded_d6_sequence(self):
        roller = seeded_roller(42)
        assert [roller.roll_d6() for _ in range(5)] == [6, 1, 1, 6, 3]

    def test_seeded_2d6_and_roll_dice(self):
        roller = seeded_roller(42)
        # Consume the first five d6 so we continue the same stream
        for _ in range(5):
            roller.roll_d6()
        assert roller.roll_2d6() == 4
        assert roller.roll_dice(4) == [2, 6, 1, 6]

    def test_seeded_d10_and_d100(self):
        assert seeded_roller(42).roll_d10() == 2
        assert seeded_roller(42).roll_d100() == 82

    def test_roll_history_tracks_count_and_average(self):
        roller = seeded_roller(42)
        for _ in range(5):
            roller.roll_d6()
        roller.roll_2d6()      # +2 rolls
        roller.roll_dice(4)    # +4 rolls
        assert roller.roll_count == 11
        assert roller.recent_average == pytest.approx(3.2727, abs=1e-3)

    def test_roll_check_flags(self):
        roller = seeded_roller(99)
        checks = roller.roll_check(4, 4)
        assert [(c.result, c.success) for c in checks] == [
            (4, True), (4, True), (2, False), (5, True)
        ]
        assert all(not c.critical and not c.fumble for c in checks)

    def test_same_seed_same_stream(self):
        a = seeded_roller(7)
        b = seeded_roller(7)
        assert [a.roll_d6() for _ in range(20)] == [b.roll_d6() for _ in range(20)]

    def test_manual_mode_uses_callback(self):
        roller = DiceRoller(mode=RollingMode.MANUAL, rng=random.Random(1))
        roller.set_manual_callback(lambda count, sides: [6] * count)
        assert roller.roll_dice(3) == [6, 6, 6]


# =============================================================================
# OPR (OnePageRules)
# =============================================================================

class TestOPREngine:
    """Characterization tests for OPRRulesEngine (quality/defense system)."""

    @staticmethod
    def shooter():
        return make_unit("Storm Squad", {"quality": "3+", "defense": "4+"})

    @staticmethod
    def grunts():
        return make_unit(
            "Grunts", {"quality": "5+", "defense": "5+", "tough": 1}, models=5
        )

    def test_shooting_seed7(self):
        engine = OPRRulesEngine(dice_roller=seeded_roller(7))
        weapon = {"name": "Assault Rifle", "shots": 3, "ap": 1}
        result = engine.resolve_shooting(self.shooter(), self.grunts(), weapon)

        # Quality 3+, to-hit rolls [3, 2, 4] -> 2 hits.
        # Defense 5+ with AP1 -> 6+ save; save rolls [6, 1] -> 1 saved, 1 failed.
        assert [r.result for r in result.to_hit_rolls] == [3, 2, 4]
        assert result.hits == 2
        assert [r.result for r in result.save_rolls] == [6, 1]
        assert result.saves_made == 1
        assert result.saves_failed == 1
        assert result.wounds_caused == 1
        assert result.damage_dealt == 1
        assert result.models_killed == 1
        # OPR has no separate to-wound step
        assert result.to_wound_rolls == []

    def test_shooting_rending_and_deadly_seed13(self):
        engine = OPRRulesEngine(dice_roller=seeded_roller(13))
        weapon = {
            "name": "Heavy Claw",
            "shots": 4,
            "ap": 0,
            "special": ["Rending", "Deadly(3)"],
        }
        ogre = make_unit(
            "Ogre", {"quality": "4+", "defense": "5+", "tough": 3}, wounds=3
        )
        result = engine.resolve_shooting(self.shooter(), ogre, weapon)

        # To-hit [3, 3, 6, 6]: all 4 hit; the two 6s are Rending auto-wounds
        # (no save). Remaining 2 hits save on 5+ -> [2, 6] -> 1 failed.
        # 3 unsaved x Deadly(3) = 9 damage vs Tough 3 -> 3 models killed.
        assert result.hits == 4
        assert result.effects == ["Rending: 2 auto-wounds!"]
        assert [r.result for r in result.save_rolls] == [2, 6]
        assert result.saves_failed == 3
        assert result.damage_dealt == 9
        assert result.models_killed == 3

    def test_melee_seed11_with_charge(self):
        engine = OPRRulesEngine(dice_roller=seeded_roller(11))
        attacker = make_unit(
            "Berserkers",
            {"quality": "3+", "defense": "4+", "A": 2},
            weapons=[{"name": "Chain Axe", "type": "melee", "ap": 1}],
            models=3,
        )
        defender = make_unit(
            "Guardsmen", {"quality": "5+", "defense": "5+", "A": 1}, models=5
        )
        result = engine.resolve_melee(attacker, defender, modifiers={"charging": True})

        # Attacker: A=2, no Furious rule -> 2 attacks, to-hit [4, 5] = 2 hits;
        # defense 5+ +AP1 -> 6+, saves [4, 4] both fail -> 2 killed.
        att = result.attacker_result
        assert att.weapon_name == "Chain Axe"
        assert [r.result for r in att.to_hit_rolls] == [4, 5]
        assert att.hits == 2
        assert att.saves_failed == 2
        assert att.models_killed == 2

        # Defender survives (5 models > 2 killed) and strikes back:
        # 1 attack, to-hit [5] vs quality 5+ = hit; save [5] vs 4+ = saved.
        dfn = result.defender_result
        assert dfn is not None
        assert [r.result for r in dfn.to_hit_rolls] == [5]
        assert dfn.hits == 1
        assert dfn.saves_made == 1
        assert dfn.models_killed == 0

    def test_melee_mutates_attacker_weapon_dict(self):
        """
        Pin a known side effect: resolve_melee writes 'shots' into the
        attacker's own weapon dict (oracle/wargame/engine/opr.py:367).
        The engine mutates roster data in place. If a refactor removes
        this mutation deliberately, update this test.
        """
        engine = OPRRulesEngine(dice_roller=seeded_roller(11))
        weapon = {"name": "Chain Axe", "type": "melee", "ap": 1}
        attacker = make_unit(
            "Berserkers", {"quality": "3+", "defense": "4+", "A": 2},
            weapons=[weapon], models=3,
        )
        defender = make_unit("Guardsmen", {"quality": "5+", "defense": "5+"}, models=5)
        assert "shots" not in weapon
        engine.resolve_melee(attacker, defender)
        assert weapon.get("shots") == 2  # side effect on the unit's data

    def test_morale_seed3_fails_as_shaken(self):
        engine = OPRRulesEngine(dice_roller=seeded_roller(3))
        unit = make_unit("Grunts", {"quality": "4+"})
        result = engine.check_morale(unit, casualties=3)
        assert result.roll.result == 2
        assert result.passed is False
        assert result.consequence == "Unit is Shaken! -1 to hit until rallied."

    def test_morale_fearless_auto_passes(self):
        engine = OPRRulesEngine(dice_roller=seeded_roller(3))  # would roll a 2
        unit = make_unit("Zealots", {"quality": "4+"})
        unit.special_rules = ["Fearless"]  # engine reads this attr if present
        result = engine.check_morale(unit, casualties=3)
        assert result.roll.result == 2  # failed the die...
        assert result.passed is True    # ...but Fearless overrides


# =============================================================================
# OLDHAMMER (WH40K 2nd Edition)
# =============================================================================

class TestOldhammerEngine:
    """Characterization tests for OldhammerRulesEngine (BS/WS charts, S vs T)."""

    @staticmethod
    def marines(models=1):
        return make_unit(
            "Tactical Marines",
            {"WS": 4, "BS": 4, "S": 4, "T": 4, "A": 1, "Sv": "3+", "Ld": 8},
            models=models,
        )

    @staticmethod
    def orks(models=10):
        return make_unit(
            "Ork Boyz",
            {"WS": 4, "BS": 2, "S": 3, "T": 4, "A": 2, "Sv": "6+", "W": 1, "Ld": 7},
            models=models,
        )

    def test_shooting_seed42(self):
        engine = OldhammerRulesEngine(dice_roller=seeded_roller(42))
        weapon = {"name": "Boltgun", "strength": 4, "shots": 2, "ap": 0}
        result = engine.resolve_shooting(self.marines(), self.orks(), weapon)

        # BS4 -> 3+ to hit; rolls [6, 1] -> 1 hit.
        # S4 vs T4 -> 4+ to wound; roll [1] -> 0 wounds. Attack fizzles.
        assert [r.result for r in result.to_hit_rolls] == [6, 1]
        assert result.hits == 1
        assert [r.result for r in result.to_wound_rolls] == [1]
        assert result.wounds_caused == 0
        assert result.saves_failed == 0
        assert result.models_killed == 0

    def test_melee_seed21_with_charge(self):
        engine = OldhammerRulesEngine(dice_roller=seeded_roller(21))
        attacker = self.marines(models=5)
        defender = self.orks(models=10)
        result = engine.resolve_melee(attacker, defender, modifiers={"charging": True})

        # NOTE (current behavior, arguably a bug): the attacker's attacks are
        # NOT scaled by model count (A1 + 1 charge = 2 attacks for 5 models),
        # while the defender's ARE scaled (A2 x 9 survivors = 18 attacks).
        # See oracle/wargame/engine/oldhammer.py:559-575.
        att = result.attacker_result
        assert att.total_shots == 2
        assert [r.result for r in att.to_hit_rolls] == [2, 4]
        assert att.hits == 1
        assert [r.result for r in att.to_wound_rolls] == [6]
        assert att.wounds_caused == 1
        # S4 vs Sv6+: armor modifier -1 -> 7+, no save possible
        assert att.save_rolls == []
        assert att.saves_failed == 1
        assert att.models_killed == 1

        dfn = result.defender_result
        assert dfn is not None
        assert dfn.total_shots == 18
        assert dfn.hits == 9
        assert dfn.wounds_caused == 3
        assert [r.result for r in dfn.save_rolls] == [1, 3, 5]
        assert dfn.saves_made == 2
        assert dfn.saves_failed == 1
        assert dfn.models_killed == 1

    def test_morale_seed5_break_test_fails(self):
        engine = OldhammerRulesEngine(dice_roller=seeded_roller(5))
        unit = make_unit("Ork Boyz", {"Ld": 7})
        result = engine.check_morale(
            unit, casualties=4, modifiers={"outnumbered": True}
        )
        # 2d6 = 8; mods: heavy casualties +2, outnumbered -1 -> 9 vs Ld7 = fail
        assert result.roll.result == 8
        assert result.modifiers == [("Heavy casualties", 2), ("Outnumbered", -1)]
        assert result.passed is False
        assert result.consequence == 'Falls back 2d6"'

    def test_sustained_fire_seed8_no_jam(self):
        engine = OldhammerRulesEngine(dice_roller=seeded_roller(8))
        sf = engine.roll_sustained_fire(2)
        # Current behavior sums the FACE VALUES of dice >= 2 ([2, 3] -> +5
        # shots), which is generous vs. tabletop sustained-fire dice.
        assert sf.dice_rolled == [2, 3]
        assert sf.jammed is False
        assert sf.extra_shots == 5
        assert sf.jam_dice == []

    def test_sustained_fire_seed0_jams_on_doubles(self):
        engine = OldhammerRulesEngine(dice_roller=seeded_roller(0))
        sf = engine.roll_sustained_fire(4)
        # Seed 0 rolls [4, 4, 1, 3]: the pair of 4s is a jam -> zero shots.
        assert sf.dice_rolled == [4, 4, 1, 3]
        assert sf.jammed is True
        assert sf.extra_shots == 0
        assert sf.jam_dice == [4]


# =============================================================================
# OLD WORLD (Warhammer: The Old World)
# =============================================================================

class TestOldWorldEngine:
    """Characterization tests for OldWorldRulesEngine (rank-and-flank)."""

    @staticmethod
    def archers():
        return make_unit(
            "Archers", {"BS": 3, "S": 3, "T": 3, "Ld": 7}, models=5
        )

    @staticmethod
    def orc_mob(models=10, **extra):
        stats = {"WS": 3, "S": 3, "T": 4, "A": 1, "I": 2,
                 "AS": "6+", "W": 1, "Ld": 7}
        stats.update(extra)
        return make_unit("Orc Mob", stats, models=models)

    def test_shooting_seed42(self):
        engine = OldWorldRulesEngine(dice_roller=seeded_roller(42))
        weapon = {"name": "Longbow", "strength": 3, "shots": 1}
        result = engine.resolve_shooting(self.archers(), self.orc_mob(), weapon)

        # 5 models x 1 shot = 5 shots at BS3 (4+): [6,1,1,6,3] -> 2 hits.
        # S3 vs T4 -> 5+ to wound: [2, 2] -> 0 wounds.
        assert result.total_shots == 5
        assert [r.result for r in result.to_hit_rolls] == [6, 1, 1, 6, 3]
        assert result.hits == 2
        assert [r.result for r in result.to_wound_rolls] == [2, 2]
        assert result.wounds_caused == 0
        assert result.models_killed == 0

    def test_melee_seed42_combat_resolution(self):
        engine = OldWorldRulesEngine(dice_roller=seeded_roller(42))
        swordsmen = make_unit(
            "Empire Swordsmen",
            {"WS": 4, "S": 3, "T": 3, "A": 1, "I": 4, "AS": "5+",
             "Ld": 7, "ranks": 3, "standard": True},
            models=5,
        )
        orcs = self.orc_mob(models=6, ranks=2)
        result = engine.resolve_melee(swordsmen, orcs, modifiers={"charging": True})

        # Attacker I4 > defender I2, attacker strikes first.
        # 5 attacks at WS4 vs WS3 (3+): [6,1,1,6,3] -> 3 hits.
        # S3 vs T4 (5+): [2,2,2] -> 0 wounds.
        att = result.attacker_result
        assert att.total_shots == 5
        assert att.hits == 3
        assert att.wounds_caused == 0
        assert att.models_killed == 0

        # Defender: 6 attacks at WS3 vs WS4 (4+): [6,1,6,6,5,1] -> 4 hits.
        # S3 vs T3 (4+): [5,4,1,1] -> 2 wounds; AS5+ saves [1,2] both fail.
        dfn = result.defender_result
        assert dfn is not None
        assert dfn.total_shots == 6
        assert dfn.hits == 4
        assert dfn.wounds_caused == 2
        assert dfn.saves_failed == 2
        assert dfn.models_killed == 2

        # Combat resolution: attacker 0 wounds +1 charge +2 ranks +1 standard = 4
        # defender 2 wounds +1 ranks = 3 -> attacker wins by 1.
        assert result.attacker_combat_res == 4
        assert result.defender_combat_res == 3
        assert result.winner == "attacker"
        assert result.margin == 1

    def test_morale_seed6_break_test_with_combat_margin(self):
        engine = OldWorldRulesEngine(dice_roller=seeded_roller(6))
        unit = make_unit("Orc Mob", {"Ld": 7})
        result = engine.check_morale(
            unit, casualties=3, modifiers={"combat_margin": 2}
        )
        # 2d6 = 6, +2 lost-combat = 8 vs Ld7 -> fails and breaks.
        assert result.roll.result == 6
        assert result.modifiers == [("Lost combat by", 2)]
        assert result.passed is False
        assert result.consequence == "Breaks and flees!"


# =============================================================================
# TRENCH CRUSADE (2d6 vs 7, +/- Dice, injury table)
# =============================================================================

class TestTrenchCrusadeEngine:
    """Characterization tests for TrenchCrusadeEngine."""

    @staticmethod
    def pilgrim():
        return make_unit(
            "Trench Pilgrim", {"ranged": 1, "melee": 0, "armour": 0, "morale": 1}
        )

    @staticmethod
    def heretic():
        return make_unit(
            "Heretic Legionnaire", {"ranged": 0, "melee": 1, "armour": 1, "morale": 0}
        )

    def test_shooting_seed42_critical_hit(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(42))
        weapon = {"name": "Bolt Action Rifle", "shots": 1, "injury_dice": 0, "ap": 0}
        result = engine.resolve_shooting(
            self.pilgrim(), self.heretic(), weapon, modifiers={"aimed": True}
        )
        # Skill 1 + aimed 1 = +2 Dice; kept dice total 12 = CRITICAL HIT.
        # Injury roll -> 5 = Blood marker. No models killed.
        assert result.hits == 1
        assert result.to_hit_rolls[0].result == 12
        assert result.to_hit_rolls[0].critical is True
        assert result.wounds_caused == 1
        assert result.damage_dealt == 1  # blood marker
        assert result.models_killed == 0
        assert "CRITICAL HIT! [6+6=12]" in result.effects
        assert "Injury [5]: Blood marker" in result.effects

    def test_shooting_seed3_machine_gun_injury_spread(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(3))
        weapon = {"name": "Machine Gun", "shots": 3, "injury_dice": 1, "ap": 1}
        result = engine.resolve_shooting(self.pilgrim(), self.heretic(), weapon)

        # 3 shots, all hit (totals 10, 8, 11). Injuries: blood, out, downed.
        assert [r.result for r in result.to_hit_rolls] == [10, 8, 11]
        assert result.hits == 3
        assert result.wounds_caused == 3
        # damage = blood(1) + downed(2) + out(3) = 6
        assert result.damage_dealt == 6
        assert result.models_killed == 1  # only "out of action" kills
        assert "Injury [9]: OUT OF ACTION!" in result.effects
        assert "Injury [8]: DOWNED!" in result.effects

    def test_melee_seed42_downed_defender_still_strikes_back(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(42))
        attacker = make_unit(
            "Assault Priest", {"melee": 2, "armour": 1, "morale": 1},
            weapons=[{"name": "Great Maul", "type": "melee",
                      "injury_dice": 1, "ap": 1}],
        )
        defender = self.heretic()
        result = engine.resolve_melee(attacker, defender, modifiers={"charging": True})

        # Attacker crits (12), injury 8 = DOWNED -> damage 2, not killed.
        att = result.attacker_result
        assert att.weapon_name == "Great Maul"
        assert att.to_hit_rolls[0].result == 12
        assert att.hits == 1
        assert att.damage_dealt == 2
        assert att.models_killed == 0
        assert "Injury [8]: DOWNED" in att.effects

        # Current behavior: defender strikes back if models_killed == 0,
        # even though it was just Downed. (Characterization; the tabletop
        # rules would likely prevent a Downed model from fighting.)
        dfn = result.defender_result
        assert dfn is not None
        assert dfn.to_hit_rolls[0].result == 12
        assert dfn.damage_dealt == 1
        assert "Injury [6]: BLOOD" in dfn.effects

    def test_morale_seed9_shaken(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(9))
        unit = make_unit("Heretic", {"morale": 0})
        result = engine.check_morale(
            unit, casualties=2, modifiers={"terrifying": True}
        )
        # 3 net -Dice (casualties 1 + terrifying 2): total 5 vs 7 -> fail.
        assert result.roll.result == 5
        assert result.passed is False
        assert result.consequence == "SHAKEN! Model must fall back and recover."

    def test_injury_roll_seed4_keeps_highest_two(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(4))
        roll, injury_type, _desc = engine.roll_injury(plus_dice=1, minus_dice=0)
        assert roll.dice_rolled == [2, 3, 1]
        assert roll.dice_kept == [3, 2]  # highest 2, sorted descending
        assert roll.total == 5
        assert injury_type == "blood"

    def test_risky_action_seed2_critical_failure(self):
        engine = TrenchCrusadeEngine(dice_roller=seeded_roller(2))
        roll, outcome = engine.roll_risky_action()
        assert roll.total == 2
        assert roll.fumble is True
        assert outcome == "CRITICAL FAILURE! Disaster strikes - roll on mishap table."


# =============================================================================
# DETERMINISM: same seed twice -> identical results
# =============================================================================

def _run_opr(seed):
    engine = OPRRulesEngine(dice_roller=seeded_roller(seed))
    att = make_unit("A", {"quality": "3+", "defense": "4+", "A": 2},
                    weapons=[{"name": "Axe", "type": "melee", "ap": 1}], models=3)
    tgt = make_unit("B", {"quality": "5+", "defense": "5+", "A": 1}, models=5)
    shoot = engine.resolve_shooting(
        att, tgt, {"name": "Rifle", "shots": 3, "ap": 1})
    melee = engine.resolve_melee(att, tgt, modifiers={"charging": True})
    return (attack_snapshot(shoot), melee_snapshot(melee))


def _run_oldhammer(seed):
    engine = OldhammerRulesEngine(dice_roller=seeded_roller(seed))
    att = make_unit("A", {"WS": 4, "BS": 4, "S": 4, "T": 4, "A": 1,
                          "Sv": "3+", "Ld": 8}, models=5)
    tgt = make_unit("B", {"WS": 4, "BS": 2, "S": 3, "T": 4, "A": 2,
                          "Sv": "6+", "W": 1, "Ld": 7}, models=10)
    shoot = engine.resolve_shooting(
        att, tgt, {"name": "Boltgun", "strength": 4, "shots": 2, "ap": 0})
    melee = engine.resolve_melee(att, tgt, modifiers={"charging": True})
    morale = engine.check_morale(tgt, casualties=3)
    return (attack_snapshot(shoot), melee_snapshot(melee),
            (morale.roll.result, morale.passed))


def _run_old_world(seed):
    engine = OldWorldRulesEngine(dice_roller=seeded_roller(seed))
    att = make_unit("A", {"WS": 4, "BS": 3, "S": 3, "T": 3, "A": 1, "I": 4,
                          "AS": "5+", "Ld": 7, "ranks": 3, "standard": True},
                    models=5)
    tgt = make_unit("B", {"WS": 3, "BS": 3, "S": 3, "T": 4, "A": 1, "I": 2,
                          "AS": "6+", "W": 1, "Ld": 7, "ranks": 2}, models=6)
    shoot = engine.resolve_shooting(
        att, tgt, {"name": "Bow", "strength": 3, "shots": 1})
    melee = engine.resolve_melee(att, tgt, modifiers={"charging": True})
    morale = engine.check_morale(tgt, casualties=2,
                                 modifiers={"combat_margin": 1})
    return (attack_snapshot(shoot), melee_snapshot(melee),
            (morale.roll.result, morale.passed))


def _run_trench_crusade(seed):
    engine = TrenchCrusadeEngine(dice_roller=seeded_roller(seed))
    att = make_unit("A", {"ranged": 1, "melee": 2, "armour": 1, "morale": 1},
                    weapons=[{"name": "Maul", "type": "melee",
                              "injury_dice": 1, "ap": 1}])
    tgt = make_unit("B", {"ranged": 0, "melee": 1, "armour": 1, "morale": 0})
    shoot = engine.resolve_shooting(
        att, tgt, {"name": "Rifle", "shots": 2, "injury_dice": 0, "ap": 0})
    melee = engine.resolve_melee(att, tgt, modifiers={"charging": True})
    morale = engine.check_morale(tgt, casualties=2)
    return (attack_snapshot(shoot), melee_snapshot(melee),
            (morale.roll.result, morale.passed))


class TestDeterminism:
    """Same seed twice must produce byte-identical outcomes per engine."""

    @pytest.mark.parametrize(
        "runner",
        [_run_opr, _run_oldhammer, _run_old_world, _run_trench_crusade],
        ids=["opr", "oldhammer", "old_world", "trench_crusade"],
    )
    @pytest.mark.parametrize("seed", [1, 42, 1234])
    def test_same_seed_identical_results(self, runner, seed):
        assert runner(seed) == runner(seed)

    @pytest.mark.parametrize(
        "runner",
        [_run_opr, _run_oldhammer, _run_old_world, _run_trench_crusade],
        ids=["opr", "oldhammer", "old_world", "trench_crusade"],
    )
    def test_different_seeds_can_differ(self, runner):
        # Sanity check that the seed actually feeds the dice: across several
        # seeds at least one outcome must differ.
        results = {repr(runner(s)) for s in (1, 2, 3, 42, 99)}
        assert len(results) > 1
