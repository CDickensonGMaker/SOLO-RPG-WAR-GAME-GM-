"""
Opponent AI - An AI that actually plays the game.

This module provides an AI opponent that uses the rules engine
to make decisions and resolve actions. Unlike the tactical advisor
(WargameAI), this AI is the enemy - it fights back.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Protocol

# These need to be imported at runtime for isinstance() checks
from oracle.wargame.engine.base import (
    AttackResult,
    MeleeResult,
    MoraleResult,
)

if TYPE_CHECKING:
    from oracle.roster import Roster, RosterUnit
    from oracle.wargame.engine.base import (
        ActivationResult,
        RulesEngine,
    )


class ActionType(Enum):
    """Types of actions an AI unit can take."""

    SHOOT = auto()
    CHARGE = auto()
    HOLD = auto()
    FALL_BACK = auto()
    ADVANCE = auto()
    OVERWATCH = auto()
    CAST_POWER = auto()


@dataclass
class ThreatAssessment:
    """Assessment of how dangerous an enemy unit is."""

    unit: RosterUnit
    threat_score: float  # 0.0 - 1.0
    reasons: list[str] = field(default_factory=list)
    priority_target: bool = False
    avoid: bool = False


@dataclass
class TargetSelection:
    """Result of target selection process."""

    target: RosterUnit
    weapon: dict[str, Any]
    reason: str
    expected_damage: float = 0.0


@dataclass
class TacticalDecision:
    """AI's decision for a unit's activation."""

    unit: RosterUnit
    action: ActionType
    target: TargetSelection | None = None
    secondary_targets: list[TargetSelection] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.5  # 0.0 = desperate, 1.0 = certain


@dataclass
class AIActivation:
    """Complete result of an AI unit's activation."""

    unit_name: str
    decision: TacticalDecision
    results: list[AttackResult | MeleeResult | MoraleResult] = field(
        default_factory=list
    )
    narrative: str = ""
    casualties_inflicted: int = 0
    casualties_suffered: int = 0


class CommanderTraits(Protocol):
    """Protocol for commander personality traits."""

    @property
    def risk_tolerance(self) -> float:
        """How willing to take risks (0.0 = cautious, 1.0 = reckless)."""
        ...

    @property
    def aggression(self) -> float:
        """How aggressive in target selection (0.0 = defensive, 1.0 = offensive)."""
        ...

    @property
    def patience(self) -> float:
        """How willing to wait for better opportunities."""
        ...


class OpponentAI:
    """
    AI opponent that actually plays the game.

    Uses a RulesEngine to resolve attacks and apply game mechanics.
    Takes into account commander personality for decision-making.
    """

    def __init__(
        self,
        rules_engine: RulesEngine,
        ai_roster: Roster,
        commander: CommanderTraits | None = None,
    ):
        """
        Initialize the opponent AI.

        Args:
            rules_engine: The rules engine for this game system
            ai_roster: The AI's army roster
            commander: Optional commander personality
        """
        self.rules = rules_engine
        self.roster = ai_roster
        self.commander = commander
        self._rng = secrets.SystemRandom()

        # Default personality if none provided
        self._default_risk = 0.5
        self._default_aggression = 0.5
        self._default_patience = 0.5

    @property
    def risk_tolerance(self) -> float:
        """Get risk tolerance from commander or default."""
        if self.commander:
            return self.commander.risk_tolerance
        return self._default_risk

    @property
    def aggression(self) -> float:
        """Get aggression from commander or default."""
        if self.commander:
            return self.commander.aggression
        return self._default_aggression

    @property
    def patience(self) -> float:
        """Get patience from commander or default."""
        if self.commander:
            return self.commander.patience
        return self._default_patience

    # =========================================================================
    # THREAT ASSESSMENT
    # =========================================================================

    def assess_threats(
        self,
        enemy_roster: Roster,
    ) -> list[ThreatAssessment]:
        """
        Assess all enemy units for threat level.

        Args:
            enemy_roster: The player's roster

        Returns:
            List of threat assessments sorted by threat score
        """
        assessments = []

        for unit in enemy_roster.active_units:
            score, reasons = self._calculate_threat_score(unit)
            priority = unit.get_stat("priority_target", False) or \
                       "character" in str(unit.keywords).lower()

            assessments.append(
                ThreatAssessment(
                    unit=unit,
                    threat_score=score,
                    reasons=reasons,
                    priority_target=priority,
                )
            )

        # Sort by threat score descending
        assessments.sort(key=lambda a: a.threat_score, reverse=True)
        return assessments

    def _calculate_threat_score(
        self,
        unit: RosterUnit,
    ) -> tuple[float, list[str]]:
        """Calculate threat score for a unit."""
        score = 0.0
        reasons = []

        # Base threat from tactical role
        role = str(unit.tactical_role or "").lower()
        if role in ("firebase", "heavy_support", "artillery"):
            score += 0.3
            reasons.append("Heavy firepower")
        elif role in ("assault", "melee", "shock"):
            score += 0.25
            reasons.append("Close combat threat")
        elif role in ("elite", "veteran"):
            score += 0.2
            reasons.append("Elite unit")

        # Threat from weapons
        for weapon in unit.weapons:
            strength = int(weapon.get("strength", weapon.get("S", 4)))
            if strength >= 8:
                score += 0.15
                reasons.append(f"S{strength} weapon")
            elif strength >= 6:
                score += 0.1

            ap = int(weapon.get("ap", weapon.get("AP", 0)))
            if ap >= 3:
                score += 0.1
                reasons.append(f"AP-{ap} weapon")

        # Threat from unit size
        models = unit.models_current or 1
        if models >= 10:
            score += 0.15
            reasons.append(f"{models} models")
        elif models >= 5:
            score += 0.1

        # Threat from special rules
        for rule in unit.special_rules or []:
            rule_lower = str(rule).lower()
            if "psyker" in rule_lower:
                score += 0.2
                reasons.append("Psyker")
            if "deep strike" in rule_lower or "teleport" in rule_lower:
                score += 0.1
                reasons.append("Deep Strike")

        # Cap at 1.0
        return min(1.0, score), reasons

    # =========================================================================
    # TARGET SELECTION
    # =========================================================================

    def select_target(
        self,
        shooter: RosterUnit,
        enemies: list[ThreatAssessment],
    ) -> TargetSelection | None:
        """
        Select the best target for a shooting unit.

        Args:
            shooter: The unit doing the shooting
            enemies: Threat assessments of enemy units

        Returns:
            TargetSelection or None if no valid target
        """
        if not enemies:
            return None

        best_target = None
        best_score = -1.0

        # Get shooter's weapons
        weapons = shooter.weapons or []
        if not weapons:
            # Default weapon
            weapons = [{"name": "Standard Weapon", "strength": 4, "shots": 1}]

        for weapon in weapons:
            weapon_type = str(weapon.get("type", "")).lower()
            if weapon_type in ("melee", "close combat"):
                continue  # Skip melee weapons for shooting

            for assessment in enemies:
                enemy = assessment.unit

                # Skip dead or routed enemies
                if not enemy.is_active:
                    continue

                # Calculate expected damage
                expected = self._estimate_damage(shooter, enemy, weapon)

                # Weight by threat score and personality
                weighted_score = expected * (1.0 + assessment.threat_score)

                # Priority targets get bonus
                if assessment.priority_target:
                    weighted_score *= 1.5

                # Aggressive commanders prefer high-threat targets
                if self.aggression > 0.6:
                    weighted_score *= (1.0 + assessment.threat_score)

                if weighted_score > best_score:
                    best_score = weighted_score
                    best_target = TargetSelection(
                        target=enemy,
                        weapon=weapon,
                        reason=f"Expected {expected:.1f} damage, threat {assessment.threat_score:.1%}",
                        expected_damage=expected,
                    )

        return best_target

    def _estimate_damage(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
    ) -> float:
        """Estimate expected damage from an attack."""
        # Get stats
        bs = attacker.get_stat("BS", 3)
        if isinstance(bs, str):
            bs = int(bs.replace("+", ""))

        strength = int(weapon.get("strength", weapon.get("S", 4)))
        target_t = target.get_stat("T", 4)
        if isinstance(target_t, str):
            target_t = int(target_t)

        target_sv = target.get_stat("Sv", 7)
        if isinstance(target_sv, str):
            target_sv = int(target_sv.replace("+", ""))

        shots = weapon.get("shots", 1)
        if isinstance(shots, str):
            if "d6" in shots.lower():
                shots = 3.5  # Average
            else:
                shots = int(shots)

        # Calculate probabilities
        to_hit = self.rules.get_to_hit(attacker, target, weapon, is_melee=False)
        hit_prob = max(0, (7 - to_hit)) / 6.0

        to_wound = self.rules.get_to_wound(strength, target_t)
        wound_prob = max(0, (7 - to_wound)) / 6.0 if to_wound > 0 else 0

        save_target = self.rules.get_armor_save(
            target, strength, int(weapon.get("ap", 0))
        )
        if save_target is None:
            fail_save_prob = 1.0
        else:
            fail_save_prob = (save_target - 1) / 6.0

        damage = int(weapon.get("damage", weapon.get("D", 1)))

        # Expected damage
        expected = shots * hit_prob * wound_prob * fail_save_prob * damage
        return expected

    # =========================================================================
    # TACTICAL DECISIONS
    # =========================================================================

    def decide_action(
        self,
        unit: RosterUnit,
        enemies: list[ThreatAssessment],
        battle_state: dict[str, Any] | None = None,
    ) -> TacticalDecision:
        """
        Decide what action a unit should take.

        Args:
            unit: The AI unit to activate
            enemies: Threat assessments of enemies
            battle_state: Optional battle context

        Returns:
            TacticalDecision with chosen action
        """
        battle_state = battle_state or {}

        # Get unit's tactical role
        role = str(unit.tactical_role or "balanced").lower()

        # Check unit status
        wounded_ratio = 1.0
        if unit.models_max and unit.models_current:
            wounded_ratio = unit.models_current / unit.models_max

        # Determine action based on role and situation
        if wounded_ratio < 0.25 and self.risk_tolerance < 0.7:
            # Badly damaged - fall back unless reckless
            return TacticalDecision(
                unit=unit,
                action=ActionType.FALL_BACK,
                reasoning="Unit heavily damaged, withdrawing to preserve forces",
                confidence=0.8,
            )

        # Check for melee-focused units
        is_melee = role in ("assault", "melee", "shock", "berserker")
        has_ranged = any(
            str(w.get("type", "")).lower() not in ("melee", "close combat")
            for w in unit.weapons
        )

        # Find target
        target = self.select_target(unit, enemies)

        if target is None:
            # No targets - hold position
            return TacticalDecision(
                unit=unit,
                action=ActionType.HOLD,
                reasoning="No valid targets in range or line of sight",
                confidence=0.5,
            )

        # Decide between shooting and charging
        if is_melee and self.aggression > 0.4:
            # Melee unit - prefer charging
            return TacticalDecision(
                unit=unit,
                action=ActionType.CHARGE,
                target=target,
                reasoning=f"Assault unit charging {target.target.name}",
                confidence=0.7 + self.aggression * 0.3,
            )
        elif has_ranged:
            # Ranged unit - shoot
            return TacticalDecision(
                unit=unit,
                action=ActionType.SHOOT,
                target=target,
                reasoning=f"Engaging {target.target.name} at range - {target.reason}",
                confidence=0.6 + target.expected_damage * 0.1,
            )
        else:
            # No ranged, not melee-focused - hold or advance
            if self.aggression > 0.6:
                return TacticalDecision(
                    unit=unit,
                    action=ActionType.ADVANCE,
                    target=target,
                    reasoning="Advancing to close range",
                    confidence=0.5,
                )
            else:
                return TacticalDecision(
                    unit=unit,
                    action=ActionType.HOLD,
                    reasoning="Holding position, no effective action available",
                    confidence=0.4,
                )

    # =========================================================================
    # ACTION EXECUTION
    # =========================================================================

    def execute_activation(
        self,
        unit: RosterUnit,
        enemy_roster: Roster,
    ) -> AIActivation:
        """
        Execute a complete activation for an AI unit.

        This is the main entry point - assess threats, decide action,
        resolve it through the rules engine, return results.

        Args:
            unit: The AI unit to activate
            enemy_roster: The player's roster

        Returns:
            AIActivation with all results and narrative
        """
        # Assess enemy threats
        threats = self.assess_threats(enemy_roster)

        # Decide what to do
        decision = self.decide_action(unit, threats)

        # Create activation record
        activation = AIActivation(
            unit_name=unit.name,
            decision=decision,
        )

        # Execute the chosen action
        if decision.action == ActionType.SHOOT and decision.target:
            result = self._execute_shooting(unit, decision.target)
            activation.results.append(result)
            activation.casualties_inflicted = result.models_killed

        elif decision.action == ActionType.CHARGE and decision.target:
            result = self._execute_charge(unit, decision.target.target)
            activation.results.append(result)
            if result.attacker_result:
                activation.casualties_inflicted = result.attacker_result.models_killed
            if result.defender_result:
                activation.casualties_suffered = result.defender_result.models_killed

        elif decision.action == ActionType.FALL_BACK:
            # No attack, just movement
            pass

        elif decision.action == ActionType.HOLD:
            # No action
            pass

        # Build narrative summary
        activation.narrative = self._build_narrative(activation)

        return activation

    def _execute_shooting(
        self,
        shooter: RosterUnit,
        target: TargetSelection,
    ) -> AttackResult:
        """Execute a shooting attack through the rules engine."""
        return self.rules.resolve_shooting(
            attacker=shooter,
            target=target.target,
            weapon=target.weapon,
        )

    def _execute_charge(
        self,
        charger: RosterUnit,
        target: RosterUnit,
    ) -> MeleeResult:
        """Execute a charge/melee attack through the rules engine."""
        return self.rules.resolve_melee(
            attacker=charger,
            defender=target,
            modifiers={"charging": True},
        )

    def _build_narrative(self, activation: AIActivation) -> str:
        """Build a narrative description of the activation."""
        parts = [f"{activation.unit_name}:"]

        action = activation.decision.action
        if action == ActionType.SHOOT:
            target = activation.decision.target
            if target and activation.results:
                result = activation.results[0]
                if isinstance(result, AttackResult):
                    parts.append(
                        f"Opens fire on {target.target.name} with {result.weapon_name}."
                    )
                    parts.append(result.summary())
        elif action == ActionType.CHARGE:
            target = activation.decision.target
            if target:
                parts.append(f"Charges into {target.target.name}!")
                if activation.results:
                    result = activation.results[0]
                    if isinstance(result, MeleeResult):
                        parts.append(result.summary())
        elif action == ActionType.FALL_BACK:
            parts.append("Falls back to a safer position.")
        elif action == ActionType.HOLD:
            parts.append("Holds position.")
        elif action == ActionType.ADVANCE:
            parts.append("Advances toward the enemy.")

        return " ".join(parts)

    # =========================================================================
    # TURN MANAGEMENT
    # =========================================================================

    def take_turn(
        self,
        enemy_roster: Roster,
        phase: str = "shooting",
    ) -> list[AIActivation]:
        """
        Take a complete turn for all AI units.

        Args:
            enemy_roster: The player's roster
            phase: Current game phase ("movement", "shooting", "melee")

        Returns:
            List of all activations this turn
        """
        activations = []

        # Get all active AI units
        units = list(self.roster.active_units)

        # Sort by tactical priority (characters/elites first if aggressive,
        # troops first if defensive)
        if self.aggression > 0.5:
            # Aggressive - activate heavy hitters first
            units.sort(
                key=lambda u: (
                    1 if "character" in str(u.keywords).lower() else 2,
                    -(u.points_cost or 0),
                ),
            )
        else:
            # Defensive - activate screening units first
            units.sort(
                key=lambda u: (
                    2 if "character" in str(u.keywords).lower() else 1,
                    u.points_cost or 0,
                ),
            )

        for unit in units:
            # Skip units that can't act in this phase
            if phase == "shooting":
                has_ranged = any(
                    str(w.get("type", "")).lower() not in ("melee", "close combat")
                    for w in unit.weapons
                )
                if not has_ranged and not unit.weapons:
                    continue

            activation = self.execute_activation(unit, enemy_roster)
            activations.append(activation)

        return activations

    def react_to_player_action(
        self,
        player_unit: RosterUnit,
        action_type: str,
        target: RosterUnit | None = None,
        result: AttackResult | MeleeResult | None = None,
    ) -> str:
        """
        Generate a reaction to the player's action.

        This is for narrative flavor - the AI commander comments
        on what the player just did.

        Args:
            player_unit: The unit that acted
            action_type: What they did (shoot, charge, etc.)
            target: Who they targeted (may be AI unit)
            result: The result of their action

        Returns:
            Narrative reaction string
        """
        reactions = []

        if result and isinstance(result, AttackResult):
            if result.models_killed >= 3:
                reactions.extend([
                    "A devastating strike!",
                    "Our lines buckle under the assault.",
                    "Regroup! Regroup!",
                ])
            elif result.models_killed == 0:
                reactions.extend([
                    "They waste ammunition.",
                    "Hold the line! Their fire is ineffective!",
                    "Is that the best they can do?",
                ])
            else:
                reactions.extend([
                    "Casualties sustained, but we endure.",
                    "Return fire!",
                    "Mark that unit for elimination.",
                ])

        if result and isinstance(result, MeleeResult):
            if result.attacker_result and result.attacker_result.models_killed >= 2:
                reactions.extend([
                    "Fall back! Regroup at the secondary position!",
                    "They break through!",
                ])
            elif result.defender_result and result.defender_result.models_killed >= 1:
                reactions.extend([
                    "Our counter-attack draws blood!",
                    "Make them pay for every inch!",
                ])

        if not reactions:
            reactions = [
                "Noted.",
                "Adjust tactics accordingly.",
                "Continue as planned.",
            ]

        return self._rng.choice(reactions)
