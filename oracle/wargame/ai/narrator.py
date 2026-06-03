"""
Enhanced Battle Narrator - Integrates dice results with commander personality.

This module extends the basic BattleNarrator to provide dramatic narration
of actual game mechanics: dice rolls, wounds, casualties. The commander's
personality colors how these results are described.

Usage:
    narrator = EnhancedNarrator(commander)
    result = rules_engine.resolve_shooting(attacker, target, weapon)
    narrative = narrator.narrate_attack(result)
    # "Von Krieger's Devastators open fire! [4,5,2,6,3] - 3 hits!
    #  Wounds punch through... [5,4] - 2 casualties!
    #  'Crush them before they can react.'"
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .commander import CommanderPersonality, BattleNarrator
from ..engine.base import AttackResult, MeleeResult, MoraleResult, DiceRoll

if TYPE_CHECKING:
    from .opponent import AIActivation


@dataclass
class NarrativeStyle:
    """Narrative style preferences based on commander personality."""

    dramatic: float = 0.5  # How dramatic/theatrical
    technical: float = 0.3  # How much mechanical detail
    emotional: float = 0.5  # How emotionally charged
    verbose: float = 0.5  # How wordy


class EnhancedNarrator(BattleNarrator):
    """
    Enhanced battle narrator that integrates dice results with personality.

    Extends BattleNarrator to narrate actual attack results, showing
    dice rolls and their outcomes through the lens of the commander's
    personality.
    """

    def __init__(
        self,
        commander: CommanderPersonality,
        style: NarrativeStyle | None = None,
    ):
        """
        Initialize the enhanced narrator.

        Args:
            commander: The commander personality
            style: Optional narrative style overrides
        """
        super().__init__(commander)
        self.style = style or self._derive_style()

    def _derive_style(self) -> NarrativeStyle:
        """Derive narrative style from commander personality."""
        return NarrativeStyle(
            dramatic=self.commander.risk_tolerance,
            technical=1.0 - self.commander.risk_tolerance,
            emotional=1.0 - self.commander.patience,
            verbose=self.commander.patience,
        )

    # =========================================================================
    # DICE ROLL NARRATION
    # =========================================================================

    def format_dice(self, rolls: list[DiceRoll], show_target: bool = True) -> str:
        """
        Format a list of dice rolls for display.

        Args:
            rolls: List of DiceRoll objects
            show_target: Whether to show the target number

        Returns:
            Formatted string like "[4,5,2,6,3] needing 4+ = 3 hits"
        """
        if not rolls:
            return ""

        results = [str(r.result) for r in rolls]
        successes = sum(1 for r in rolls if r.success)
        criticals = sum(1 for r in rolls if r.critical)
        fumbles = sum(1 for r in rolls if r.fumble)

        dice_str = f"[{','.join(results)}]"

        if show_target and rolls:
            target = rolls[0].target
            dice_str += f" needing {target}+"

        dice_str += f" = {successes}"

        # Add flair for criticals/fumbles
        if criticals > 0:
            dice_str += f" ({criticals} critical!)"
        if fumbles > 0:
            dice_str += f" ({fumbles} fumbled)"

        return dice_str

    # =========================================================================
    # ATTACK RESULT NARRATION
    # =========================================================================

    def narrate_attack(
        self,
        result: AttackResult,
        is_ai_attacking: bool = True,
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Narrate an attack result with dice and personality.

        Args:
            result: The AttackResult from the rules engine
            is_ai_attacking: True if AI is attacking, False if defending
            rng: Optional random generator

        Returns:
            Dramatic narrative of the attack
        """
        if rng is None:
            rng = random.Random()

        lines = []
        title = f"{self.commander.title} {self.commander.name}"

        # Opening line - attacker fires
        if is_ai_attacking:
            openers = self._get_attack_openers(result, title, rng)
            lines.append(rng.choice(openers))
        else:
            # AI is being attacked
            openers = self._get_defense_openers(result, title, rng)
            lines.append(rng.choice(openers))

        # To-hit rolls
        if result.to_hit_rolls:
            hit_narrative = self._narrate_to_hit(result, is_ai_attacking, rng)
            lines.append(hit_narrative)

        # To-wound rolls
        if result.to_wound_rolls:
            wound_narrative = self._narrate_to_wound(result, is_ai_attacking, rng)
            lines.append(wound_narrative)

        # Save rolls
        if result.save_rolls:
            save_narrative = self._narrate_saves(result, is_ai_attacking, rng)
            lines.append(save_narrative)

        # Final casualties
        if result.models_killed > 0:
            casualty_narrative = self._narrate_casualties(result, is_ai_attacking, rng)
            lines.append(casualty_narrative)

        # Special effects
        for effect in result.effects:
            lines.append(f"  {effect}")

        # Commander voice line based on outcome
        if is_ai_attacking:
            if result.models_killed >= 3:
                voice = self.commander.get_voice_line("victory", rng)
            elif result.models_killed == 0:
                voice = self.commander.get_voice_line("defeat", rng)
            else:
                voice = self.commander.get_voice_line("general", rng)
        else:
            if result.models_killed >= 3:
                voice = self.commander.get_voice_line("defeat", rng)
            elif result.models_killed == 0:
                voice = self.commander.get_voice_line("taunt", rng)
            else:
                voice = self.commander.get_voice_line("general", rng)

        if voice:
            lines.append(f'"{voice}"')

        return "\n".join(lines)

    def _get_attack_openers(
        self,
        result: AttackResult,
        title: str,
        rng: random.Random,
    ) -> list[str]:
        """Get opening lines for an AI attack."""
        weapon = result.weapon_name
        target = result.target_name

        if self.style.dramatic > 0.6:
            return [
                f"{title}'s {result.attacker_name} unleash {weapon} upon {target}!",
                f"At {title}'s command, {result.attacker_name} opens fire!",
                f"{title} orders the {weapon} to speak! Target: {target}!",
            ]
        else:
            return [
                f"{result.attacker_name} fires {weapon} at {target}.",
                f"{title}'s {result.attacker_name} engages {target}.",
                f"{weapon} targets {target}.",
            ]

    def _get_defense_openers(
        self,
        result: AttackResult,
        title: str,
        rng: random.Random,
    ) -> list[str]:
        """Get opening lines when AI is being attacked."""
        weapon = result.weapon_name
        target = result.target_name

        if self.style.dramatic > 0.6:
            return [
                f"Enemy {result.attacker_name} fires upon {title}'s {target}!",
                f"Incoming fire! {result.attacker_name} targets our {target}!",
                f"{title}'s {target} comes under fire!",
            ]
        else:
            return [
                f"{result.attacker_name} fires at {target}.",
                f"Enemy engages {target} with {weapon}.",
                f"Incoming: {weapon} fire.",
            ]

    def _narrate_to_hit(
        self,
        result: AttackResult,
        is_ai: bool,
        rng: random.Random,
    ) -> str:
        """Narrate the to-hit phase."""
        dice_str = self.format_dice(result.to_hit_rolls)
        hits = result.hits
        total = result.total_shots

        if self.style.technical > 0.5:
            return f"  To Hit: {dice_str} = {hits}/{total} hits"
        else:
            if hits >= total * 0.6:
                return f"  Accurate fire! {hits} shots find their mark."
            elif hits > 0:
                return f"  {hits} shots connect."
            else:
                return "  All shots go wide!"

    def _narrate_to_wound(
        self,
        result: AttackResult,
        is_ai: bool,
        rng: random.Random,
    ) -> str:
        """Narrate the to-wound phase."""
        dice_str = self.format_dice(result.to_wound_rolls)
        wounds = result.wounds_caused
        hits = result.hits

        if self.style.technical > 0.5:
            return f"  To Wound: {dice_str} = {wounds}/{hits} wounds"
        else:
            if wounds >= hits * 0.6:
                return f"  Devastating! {wounds} wounds inflicted."
            elif wounds > 0:
                return f"  {wounds} wounds punch through."
            else:
                return "  No wounds caused."

    def _narrate_saves(
        self,
        result: AttackResult,
        is_ai: bool,
        rng: random.Random,
    ) -> str:
        """Narrate the save phase."""
        dice_str = self.format_dice(result.save_rolls)
        saved = result.saves_made
        failed = result.saves_failed

        if self.style.technical > 0.5:
            return f"  Saves: {dice_str} = {saved} saved, {failed} failed"
        else:
            if saved > failed:
                word = "Their" if is_ai else "Our"
                return f"  {word} armor holds! {saved} saves made."
            elif saved > 0:
                return f"  Some shots deflected, but {failed} get through."
            else:
                return "  No armor saves!"

    def _narrate_casualties(
        self,
        result: AttackResult,
        is_ai: bool,
        rng: random.Random,
    ) -> str:
        """Narrate casualties."""
        killed = result.models_killed
        target = result.target_name

        if is_ai:
            # AI inflicted these casualties
            if self.style.dramatic > 0.6:
                if killed >= 3:
                    return f"  >>> {killed} {target} fall! Devastating!"
                else:
                    return f"  >>> {killed} {target} eliminated."
            else:
                return f"  Result: {killed} casualties inflicted."
        else:
            # AI suffered these casualties
            if self.style.emotional > 0.6:
                if killed >= 3:
                    return f"  >>> {killed} losses! The line wavers..."
                else:
                    return f"  >>> {killed} of our troops fall."
            else:
                return f"  Casualties sustained: {killed}."

    # =========================================================================
    # MELEE NARRATION
    # =========================================================================

    def narrate_melee(
        self,
        result: MeleeResult,
        is_ai_attacking: bool = True,
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Narrate a melee combat result.

        Args:
            result: The MeleeResult from the rules engine
            is_ai_attacking: True if AI initiated the charge
            rng: Optional random generator

        Returns:
            Dramatic narrative of the melee
        """
        if rng is None:
            rng = random.Random()

        lines = []
        title = f"{self.commander.title} {self.commander.name}"

        # Opening
        if is_ai_attacking:
            if self.style.dramatic > 0.6:
                lines.append(
                    f"{title}'s {result.attacker_name} crashes into {result.defender_name}!"
                )
            else:
                lines.append(f"{result.attacker_name} charges {result.defender_name}.")
        else:
            lines.append(f"Enemy {result.attacker_name} charges our {result.defender_name}!")

        # Attacker's attacks
        if result.attacker_result:
            atk = result.attacker_result
            lines.append(f"  Attacker strikes: {atk.hits} hits, {atk.models_killed} killed")

        # Defender's attacks
        if result.defender_result:
            dfn = result.defender_result
            lines.append(f"  Defender strikes back: {dfn.hits} hits, {dfn.models_killed} killed")

        # Combat resolution (if applicable)
        if result.winner:
            if result.winner == "attacker":
                winner_name = result.attacker_name
            elif result.winner == "defender":
                winner_name = result.defender_name
            else:
                winner_name = "Neither"

            lines.append(f"  Combat won by {winner_name} (margin: {result.margin})")

        # Voice line
        voice = self.commander.get_voice_line("general", rng)
        if voice:
            lines.append(f'"{voice}"')

        return "\n".join(lines)

    # =========================================================================
    # MORALE NARRATION
    # =========================================================================

    def narrate_morale(
        self,
        result: MoraleResult,
        is_ai_unit: bool = True,
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Narrate a morale check result.

        Args:
            result: The MoraleResult from the rules engine
            is_ai_unit: True if this is an AI unit's morale check
            rng: Optional random generator

        Returns:
            Narrative of the morale check
        """
        if rng is None:
            rng = random.Random()

        lines = []
        title = f"{self.commander.title} {self.commander.name}"

        # Build the check description
        roll = result.roll.result
        ld = result.leadership

        if is_ai_unit:
            lines.append(f"{result.unit_name} takes {result.test_type} test!")
        else:
            lines.append(f"Enemy {result.unit_name} must test {result.test_type}!")

        # Show the roll
        mod_str = ""
        if result.modifiers:
            mods = ", ".join(f"{name} {mod:+d}" for name, mod in result.modifiers)
            mod_str = f" ({mods})"

        lines.append(f"  Rolled {roll}{mod_str} vs Leadership {ld}")

        # Result
        if result.passed:
            if is_ai_unit:
                lines.append(f"  PASSED! {result.consequence}")
                voice = self.commander.get_voice_line("general", rng)
            else:
                lines.append(f"  They hold! {result.consequence}")
                voice = self.commander.get_voice_line("respect", rng)
        else:
            if is_ai_unit:
                lines.append(f"  FAILED! {result.consequence}")
                voice = self.commander.get_voice_line("defeat", rng)
            else:
                lines.append(f"  They break! {result.consequence}")
                voice = self.commander.get_voice_line("taunt", rng)

        if voice:
            lines.append(f'"{voice}"')

        return "\n".join(lines)

    # =========================================================================
    # ACTIVATION NARRATION
    # =========================================================================

    def narrate_activation(
        self,
        activation: AIActivation,
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Narrate a complete AI activation.

        Args:
            activation: The AIActivation from OpponentAI
            rng: Optional random generator

        Returns:
            Full narrative of the activation
        """
        if rng is None:
            rng = random.Random()

        lines = []
        title = f"{self.commander.title} {self.commander.name}"

        # Opening based on action type
        action = activation.decision.action.name.lower()
        lines.append(f"\n=== {title}'s Turn: {activation.unit_name} ===")

        if action == "shoot":
            lines.append(f"{activation.unit_name} takes aim...")
        elif action == "charge":
            lines.append(f"{activation.unit_name} charges forward!")
        elif action == "hold":
            lines.append(f"{activation.unit_name} holds position.")
        elif action == "fall_back":
            lines.append(f"{activation.unit_name} falls back to safety.")

        # Narrate each result
        for result in activation.results:
            if isinstance(result, AttackResult):
                lines.append(self.narrate_attack(result, is_ai_attacking=True, rng=rng))
            elif isinstance(result, MeleeResult):
                lines.append(self.narrate_melee(result, is_ai_attacking=True, rng=rng))
            elif isinstance(result, MoraleResult):
                lines.append(self.narrate_morale(result, is_ai_unit=True, rng=rng))

        # Summary
        if activation.casualties_inflicted > 0:
            lines.append(f"\nTotal casualties inflicted: {activation.casualties_inflicted}")
        if activation.casualties_suffered > 0:
            lines.append(f"Casualties suffered: {activation.casualties_suffered}")

        return "\n".join(lines)

    # =========================================================================
    # PLAYER ACTION REACTIONS
    # =========================================================================

    def react_to_player_attack(
        self,
        result: AttackResult,
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Generate commander reaction to player's attack.

        Args:
            result: The AttackResult from player's attack
            rng: Optional random generator

        Returns:
            Commander's reaction narrative
        """
        if rng is None:
            rng = random.Random()

        title = f"{self.commander.title} {self.commander.name}"

        # Narrate the attack from defender's perspective
        attack_narrative = self.narrate_attack(result, is_ai_attacking=False, rng=rng)

        # Add reaction
        if result.models_killed >= 3:
            reactions = [
                f"\n{title} grimaces at the losses.",
                f"\n{title}: 'We will avenge them!'",
                f"\n{title} marks the enemy unit for destruction.",
            ]
        elif result.models_killed == 0:
            reactions = [
                f"\n{title} smirks. 'Is that all?'",
                f"\n{title} notes the ineffective fire.",
                f"\n{title}: 'They waste their ammunition.'",
            ]
        else:
            reactions = [
                f"\n{title} takes note of the casualties.",
                f"\n{title} adjusts the tactical plan.",
                f"\n{title}: 'Acceptable losses.'",
            ]

        return attack_narrative + rng.choice(reactions)
