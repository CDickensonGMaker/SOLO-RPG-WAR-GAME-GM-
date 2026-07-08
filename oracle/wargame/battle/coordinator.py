"""
Battle Coordinator - Orchestrates player vs AI combat.

This module ties together the rules engine, AI opponent, and narrator
to provide a complete battle experience. It manages turn flow, applies
results to rosters, and maintains battle history.

Usage:
    coordinator = BattleCoordinator(
        rules_engine=OldhammerRulesEngine(),
        player_roster=player_army,
        ai_roster=enemy_army,
        commander=generate_commander("aggressive_blitzer"),
    )

    # Player attacks
    result = coordinator.player_declares_attack(
        attacker=my_marines,
        target=enemy_orks,
        weapon=bolter,
    )

    # AI responds
    ai_turn = coordinator.opponent_takes_turn()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from oracle.roster import Roster, RosterUnit
    from oracle.wargame.engine.base import (
        AttackResult,
        MeleeResult,
        MoraleResult,
        RulesEngine,
    )
    from oracle.wargame.ai.commander import CommanderPersonality
    from oracle.wargame.ai.opponent import AIActivation, OpponentAI
    from oracle.wargame.ai.narrator import EnhancedNarrator


class BattlePhase(Enum):
    """Current phase of the battle turn."""

    SETUP = auto()
    PLAYER_MOVEMENT = auto()
    PLAYER_SHOOTING = auto()
    PLAYER_MELEE = auto()
    AI_MOVEMENT = auto()
    AI_SHOOTING = auto()
    AI_MELEE = auto()
    MORALE = auto()
    END_TURN = auto()
    BATTLE_OVER = auto()


class BattleOutcome(Enum):
    """Possible battle outcomes."""

    ONGOING = auto()
    PLAYER_VICTORY = auto()
    AI_VICTORY = auto()
    DRAW = auto()


@dataclass
class BattleLogEntry:
    """A single entry in the battle log."""

    timestamp: datetime
    turn: int
    phase: BattlePhase
    actor: str  # "player", "ai", "system"
    action: str  # Brief description
    details: str  # Full narrative
    result: Any | None = None  # AttackResult, MeleeResult, etc.

    def __str__(self) -> str:
        return f"[Turn {self.turn}] {self.actor}: {self.action}"


@dataclass
class BattleState:
    """
    Current state of the battle.

    Tracks turn count, phase, victory conditions, and
    cumulative statistics.
    """

    current_turn: int = 1
    current_phase: BattlePhase = BattlePhase.SETUP
    outcome: BattleOutcome = BattleOutcome.ONGOING

    # Victory conditions
    max_turns: int = 6
    player_objective_held: bool = False
    ai_objective_held: bool = False

    # Statistics
    player_casualties: int = 0
    ai_casualties: int = 0
    player_units_destroyed: int = 0
    ai_units_destroyed: int = 0

    # Phase tracking
    units_activated_this_phase: list[str] = field(default_factory=list)

    def advance_phase(self) -> None:
        """Advance to the next phase."""
        phase_order = [
            BattlePhase.PLAYER_MOVEMENT,
            BattlePhase.PLAYER_SHOOTING,
            BattlePhase.PLAYER_MELEE,
            BattlePhase.AI_MOVEMENT,
            BattlePhase.AI_SHOOTING,
            BattlePhase.AI_MELEE,
            BattlePhase.MORALE,
            BattlePhase.END_TURN,
        ]

        try:
            current_index = phase_order.index(self.current_phase)
            if current_index < len(phase_order) - 1:
                self.current_phase = phase_order[current_index + 1]
            else:
                # End of turn - start next turn
                self.current_turn += 1
                self.current_phase = BattlePhase.PLAYER_MOVEMENT
                self.units_activated_this_phase = []
        except ValueError:
            # Not in normal phase order (setup, battle_over)
            if self.current_phase == BattlePhase.SETUP:
                self.current_phase = BattlePhase.PLAYER_MOVEMENT

    def check_victory(
        self,
        player_roster: Roster,
        ai_roster: Roster,
    ) -> None:
        """Check if either side has won."""
        # A battle that was never set up (no units on either side) can't be won.
        if not player_roster.units and not ai_roster.units:
            return

        player_active = len(list(player_roster.active_units))
        ai_active = len(list(ai_roster.active_units))

        if ai_active == 0:
            self.outcome = BattleOutcome.PLAYER_VICTORY
            self.current_phase = BattlePhase.BATTLE_OVER
        elif player_active == 0:
            self.outcome = BattleOutcome.AI_VICTORY
            self.current_phase = BattlePhase.BATTLE_OVER
        elif self.current_turn > self.max_turns:
            # Compare objectives or casualties
            if self.player_casualties < self.ai_casualties:
                self.outcome = BattleOutcome.PLAYER_VICTORY
            elif self.ai_casualties < self.player_casualties:
                self.outcome = BattleOutcome.AI_VICTORY
            else:
                self.outcome = BattleOutcome.DRAW
            self.current_phase = BattlePhase.BATTLE_OVER


class BattleLog:
    """
    Log of all battle events.

    Maintains history of attacks, casualties, and narrative
    for display and replay purposes.
    """

    def __init__(self):
        self.entries: list[BattleLogEntry] = []

    def add_entry(
        self,
        turn: int,
        phase: BattlePhase,
        actor: str,
        action: str,
        details: str,
        result: Any | None = None,
    ) -> None:
        """Add an entry to the log."""
        entry = BattleLogEntry(
            timestamp=datetime.now(),
            turn=turn,
            phase=phase,
            actor=actor,
            action=action,
            details=details,
            result=result,
        )
        self.entries.append(entry)

    def get_turn(self, turn: int) -> list[BattleLogEntry]:
        """Get all entries for a specific turn."""
        return [e for e in self.entries if e.turn == turn]

    def get_recent(self, count: int = 5) -> list[BattleLogEntry]:
        """Get the most recent entries."""
        return self.entries[-count:]

    def format_history(self, turns: int = 3) -> str:
        """Format recent turns as readable text."""
        lines = []
        current_turn = max(e.turn for e in self.entries) if self.entries else 0

        for turn in range(max(1, current_turn - turns + 1), current_turn + 1):
            turn_entries = self.get_turn(turn)
            if turn_entries:
                lines.append(f"\n=== Turn {turn} ===")
                for entry in turn_entries:
                    lines.append(entry.details)

        return "\n".join(lines)


class BattleCoordinator:
    """
    Orchestrates player vs AI combat.

    This is the main interface for running a battle. It:
    - Manages turn flow and phases
    - Resolves player attacks through the rules engine
    - Runs AI activations with narration
    - Applies casualties to rosters
    - Tracks battle history
    """

    def __init__(
        self,
        rules_engine: RulesEngine,
        player_roster: Roster,
        ai_roster: Roster,
        commander: CommanderPersonality | None = None,
    ):
        """
        Initialize the battle coordinator.

        Args:
            rules_engine: The rules engine for this game system
            player_roster: The player's army
            ai_roster: The AI's army
            commander: Optional AI commander personality
        """
        self.rules = rules_engine
        self.player_roster = player_roster
        self.ai_roster = ai_roster
        self.commander = commander

        self.state = BattleState()
        self.log = BattleLog()

        # Lazy-init AI and narrator
        self._opponent: OpponentAI | None = None
        self._narrator: EnhancedNarrator | None = None

    @property
    def opponent(self) -> OpponentAI:
        """Get or create the opponent AI."""
        if self._opponent is None:
            from oracle.wargame.ai.opponent import OpponentAI

            self._opponent = OpponentAI(
                rules_engine=self.rules,
                ai_roster=self.ai_roster,
                commander=self.commander,
            )
        elif self._opponent.ai_roster is not self.ai_roster:
            # Roster was swapped (e.g. a saved roster was loaded) - stay in sync.
            self._opponent.ai_roster = self.ai_roster
        return self._opponent

    @property
    def narrator(self) -> EnhancedNarrator:
        """Get or create the narrator."""
        if self._narrator is None:
            from oracle.wargame.ai.narrator import EnhancedNarrator
            from oracle.wargame.ai.commander import (
                CommanderPersonality,
                generate_commander,
            )

            if self.commander is None:
                self.commander = generate_commander()
            self._narrator = EnhancedNarrator(self.commander)
        return self._narrator

    # =========================================================================
    # BATTLE FLOW
    # =========================================================================

    def start_battle(self) -> str:
        """
        Start the battle.

        Returns:
            Opening narrative
        """
        self.state.current_phase = BattlePhase.PLAYER_MOVEMENT
        self.state.current_turn = 1

        # Log the battle start
        self.log.add_entry(
            turn=1,
            phase=BattlePhase.SETUP,
            actor="system",
            action="Battle begins",
            details=f"Turn 1 begins. Player vs {self.commander.name if self.commander else 'Enemy'}",
        )

        title = (
            f"{self.commander.title} {self.commander.name}"
            if self.commander
            else "The enemy commander"
        )
        return f"The battle begins! {title} awaits your move."

    def end_turn(self) -> str:
        """
        End the current turn and check victory.

        Returns:
            End-of-turn summary
        """
        self.state.check_victory(self.player_roster, self.ai_roster)

        if self.state.outcome != BattleOutcome.ONGOING:
            return self.narrate_battle_end()

        self.state.current_turn += 1
        self.state.current_phase = BattlePhase.PLAYER_MOVEMENT
        self.state.units_activated_this_phase = []

        return f"Turn {self.state.current_turn} begins."

    def narrate_battle_end(self) -> str:
        """Narrate the end of battle from the AI commander's perspective."""
        if self.state.outcome == BattleOutcome.PLAYER_VICTORY:
            # The AI commander was beaten.
            return self.narrator.narrate_defeat()
        elif self.state.outcome == BattleOutcome.AI_VICTORY:
            # The AI commander gloats.
            return self.narrator.narrate_victory()
        else:
            return "The battle ends in a draw. Both forces withdraw from the field."

    def reset_battle(self, player_roster: Roster, ai_roster: Roster) -> str:
        """
        Replace both rosters, reset state/log, and start a fresh battle.

        Returns:
            Opening narrative from start_battle()
        """
        self.player_roster = player_roster
        self.ai_roster = ai_roster
        self.state = BattleState()
        self.log = BattleLog()
        self._opponent = None  # rebuilt lazily against the new roster
        return self.start_battle()

    def set_commander(self, commander: CommanderPersonality) -> None:
        """Swap the AI commander, invalidating cached AI and narrator."""
        self.commander = commander
        self._narrator = None
        self._opponent = None

    # =========================================================================
    # PLAYER ACTIONS
    # =========================================================================

    def player_declares_attack(
        self,
        attacker: RosterUnit,
        target: RosterUnit,
        weapon: dict[str, Any],
        modifiers: dict[str, int] | None = None,
    ) -> tuple[AttackResult, str]:
        """
        Resolve a player's shooting attack.

        Args:
            attacker: The attacking unit
            target: The target unit (must be in ai_roster)
            weapon: Weapon profile dict
            modifiers: Optional situational modifiers

        Returns:
            Tuple of (AttackResult, narrative)
        """
        # Resolve through rules engine
        result = self.rules.resolve_shooting(
            attacker=attacker,
            target=target,
            weapon=weapon,
            modifiers=modifiers,
        )

        # Apply casualties to AI roster
        if result.models_killed > 0:
            target.take_damage(result.damage_dealt)
            self.state.ai_casualties += result.models_killed

            # Check if unit destroyed
            if target.models_current <= 0:
                self.state.ai_units_destroyed += 1

        # Generate narrative (AI reacts to player attack)
        narrative = self.narrator.react_to_player_attack(result)

        # Log the attack
        self.log.add_entry(
            turn=self.state.current_turn,
            phase=self.state.current_phase,
            actor="player",
            action=f"{attacker.name} shoots {target.name}",
            details=narrative,
            result=result,
        )

        return result, narrative

    def player_declares_charge(
        self,
        charger: RosterUnit,
        target: RosterUnit,
        modifiers: dict[str, int] | None = None,
    ) -> tuple[MeleeResult, str]:
        """
        Resolve a player's charge/melee attack.

        Args:
            charger: The charging unit
            target: The target unit (must be in ai_roster)
            modifiers: Optional situational modifiers

        Returns:
            Tuple of (MeleeResult, narrative)
        """
        modifiers = modifiers or {}
        modifiers["charging"] = True

        # Resolve through rules engine
        result = self.rules.resolve_melee(
            attacker=charger,
            defender=target,
            modifiers=modifiers,
        )

        # Apply casualties
        if result.attacker_result and result.attacker_result.models_killed > 0:
            target.take_damage(result.attacker_result.damage_dealt)
            self.state.ai_casualties += result.attacker_result.models_killed

        if result.defender_result and result.defender_result.models_killed > 0:
            charger.take_damage(result.defender_result.damage_dealt)
            self.state.player_casualties += result.defender_result.models_killed

        # Generate narrative
        narrative = self.narrator.narrate_melee(result, is_ai_attacking=False)

        # Log
        self.log.add_entry(
            turn=self.state.current_turn,
            phase=self.state.current_phase,
            actor="player",
            action=f"{charger.name} charges {target.name}",
            details=narrative,
            result=result,
        )

        return result, narrative

    # =========================================================================
    # AI ACTIONS
    # =========================================================================

    def opponent_takes_turn(
        self,
        phase: str = "shooting",
    ) -> tuple[list[AIActivation], str]:
        """
        Have the AI opponent take its turn.

        Args:
            phase: Current game phase ("movement", "shooting", "melee")

        Returns:
            Tuple of (list of AIActivations, combined narrative)
        """
        from oracle.wargame.ai.opponent import AIActivation

        # Get AI activations
        activations = self.opponent.take_turn(self.player_roster, phase)

        # Apply results and build narrative
        narratives = []

        for activation in activations:
            # Apply casualties from each attack
            for result in activation.results:
                if hasattr(result, "models_killed") and result.models_killed > 0:
                    # Find the target and apply damage
                    if hasattr(result, "target_name"):
                        target = self.player_roster.get_unit(result.target_name)
                        if target:
                            target.take_damage(result.damage_dealt)
                            self.state.player_casualties += result.models_killed

            # Generate narrative for this activation
            narrative = self.narrator.narrate_activation(activation)
            narratives.append(narrative)

            # Log
            self.log.add_entry(
                turn=self.state.current_turn,
                phase=self.state.current_phase,
                actor="ai",
                action=f"{activation.unit_name}: {activation.decision.action.name}",
                details=narrative,
            )

        combined_narrative = "\n\n".join(narratives)
        return activations, combined_narrative

    def opponent_reacts(
        self,
        player_action: str,
        player_unit: RosterUnit | None = None,
        target: RosterUnit | None = None,
        result: AttackResult | MeleeResult | None = None,
    ) -> str:
        """
        Get AI commander's reaction to player's action.

        Args:
            player_action: What the player did
            player_unit: The unit that acted
            target: The target (if applicable)
            result: The result (if applicable)

        Returns:
            Commander's reaction narrative
        """
        return self.opponent.react_to_player_action(
            player_unit=player_unit,
            action_type=player_action,
            target=target,
            result=result,
        )

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_battle_summary(self) -> str:
        """Get a summary of the current battle state."""
        lines = [
            f"=== Battle Summary: Turn {self.state.current_turn} ===",
            f"Phase: {self.state.current_phase.name}",
            f"Outcome: {self.state.outcome.name}",
            "",
            "Player Forces:",
            f"  Active units: {len(list(self.player_roster.active_units))}",
            f"  Casualties: {self.state.player_casualties}",
            f"  Units destroyed: {self.state.player_units_destroyed}",
            "",
            "AI Forces:",
            f"  Active units: {len(list(self.ai_roster.active_units))}",
            f"  Casualties: {self.state.ai_casualties}",
            f"  Units destroyed: {self.state.ai_units_destroyed}",
        ]

        if self.commander:
            lines.extend(
                [
                    "",
                    f"Commander: {self.commander.title} {self.commander.name}",
                    f"  Archetype: {self.commander.archetype.value}",
                ]
            )

        return "\n".join(lines)

    def get_recent_log(self, count: int = 5) -> str:
        """Get recent log entries as formatted text."""
        entries = self.log.get_recent(count)
        return "\n\n".join(e.details for e in entries)
