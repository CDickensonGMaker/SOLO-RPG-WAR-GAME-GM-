"""
Wargame App - Solo Wargaming with AI Opponent

A tabletop wargaming assistant where:
- The AI opponent actually plays by the rules (rolls dice, applies modifiers)
- Combat results include full dice breakdowns
- Commander personalities narrate the battle
- Both armies are tracked with wounds and model counts
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import dearpygui.dearpygui as dpg

# Wargame engine imports
from oracle.wargame import (
    # Engines
    OldhammerRulesEngine,
    OPRRulesEngine,
    OldWorldRulesEngine,
    TrenchCrusadeEngine,
    RulesEngine,
    DiceRoller,
    RollingMode,
    AttackResult,
    MeleeResult,
    MoraleResult,
    # AI
    CommanderPersonality,
    generate_commander,
    OpponentAI,
    AIActivation,
    EnhancedNarrator,
    WargameAI,
    Doctrine,
    Aggression,
    # Battle
    BattleCoordinator,
    BattlePhase,
    BattleState,
    BattleLog,
)
from oracle.roster import (
    Roster,
    RosterUnit,
    UnitStatus,
    SlotType,
    RosterManager,
)


# =============================================================================
# Configuration
# =============================================================================

GAME_SYSTEMS = {
    "oldhammer_2e": {
        "name": "Oldhammer 2nd Edition",
        "description": "Classic 40K 2nd Edition rules",
        "engine_class": OldhammerRulesEngine,
    },
    "opr_grimdark": {
        "name": "OPR Grimdark Future",
        "description": "OnePageRules streamlined wargaming",
        "engine_class": OPRRulesEngine,
    },
    "old_world": {
        "name": "Warhammer: The Old World",
        "description": "Fantasy regiment battles",
        "engine_class": OldWorldRulesEngine,
    },
    "trench_crusade": {
        "name": "Trench Crusade",
        "description": "WWI horror skirmish - d10 system",
        "engine_class": TrenchCrusadeEngine,
    },
}

COMMANDER_ARCHETYPES = [
    "aggressive_blitzer",
    "defensive_tactician",
    "balanced_strategist",
    "cautious_commander",
    "reckless_berserker",
]


# =============================================================================
# Battle Message Types
# =============================================================================

@dataclass
class BattleMessage:
    """A message in the battle log."""
    text: str
    sender: str  # "player", "ai", "system", "combat", "dice"
    msg_type: str = "normal"  # "normal", "combat", "dice", "narrative", "event"
    dice_breakdown: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# Battle Chat Panel
# =============================================================================

class BattleChatPanel:
    """
    Chat interface for battle actions and results.

    Shows combat results with dice breakdowns, AI decisions,
    and commander narration.
    """

    def __init__(
        self,
        parent: str,
        coordinator: BattleCoordinator,
        narrator: EnhancedNarrator,
    ):
        self.parent = parent
        self.coordinator = coordinator
        self.narrator = narrator
        self.messages: List[BattleMessage] = []

        # UI tags
        self._tag = f"battle_chat_{id(self)}"
        self._log_tag = f"{self._tag}_log"
        self._input_tag = f"{self._tag}_input"

        self._build()

    def _build(self):
        """Build the chat panel."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            # Header
            with dpg.group(horizontal=True):
                dpg.add_text("Battle Log", color=(200, 160, 120))
                dpg.add_spacer(width=-120)
                dpg.add_button(
                    label="Clear",
                    callback=self.clear,
                    width=50,
                )

            dpg.add_separator()

            # Log area
            with dpg.child_window(
                height=-100,
                border=False,
                tag=self._log_tag,
            ):
                pass

            dpg.add_separator()

            # Action buttons
            dpg.add_text("Actions:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Declare Attack",
                    callback=self._show_attack_dialog,
                    width=120,
                )
                dpg.add_button(
                    label="AI Turn",
                    callback=self._execute_ai_turn,
                    width=80,
                )
                dpg.add_button(
                    label="Next Phase",
                    callback=self._advance_phase,
                    width=90,
                )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Morale Check",
                    callback=self._show_morale_dialog,
                    width=100,
                )
                dpg.add_button(
                    label="Battle Event",
                    callback=self._generate_event,
                    width=100,
                )
                dpg.add_button(
                    label="Roll Dice",
                    callback=self._show_dice_dialog,
                    width=80,
                )

    def add_message(self, msg: BattleMessage):
        """Add a message to the log."""
        self.messages.append(msg)
        self._render_message(msg)

    def _render_message(self, msg: BattleMessage):
        """Render a single message."""
        with dpg.group(parent=self._log_tag):
            # Sender colors
            colors = {
                "player": (100, 180, 220),
                "ai": (200, 140, 140),
                "system": (150, 150, 150),
                "combat": (220, 180, 100),
                "dice": (140, 200, 140),
            }
            color = colors.get(msg.sender, (150, 150, 150))

            # Time and sender
            time_str = msg.timestamp.strftime("%H:%M")
            labels = {
                "player": "You",
                "ai": "AI Commander",
                "system": "System",
                "combat": "Combat",
                "dice": "Dice",
            }
            label = labels.get(msg.sender, msg.sender)

            with dpg.group(horizontal=True):
                dpg.add_text(f"[{time_str}]", color=(100, 100, 100))
                dpg.add_text(f"{label}:", color=color)

            # Message content
            msg_colors = {
                "combat": (220, 200, 140),
                "narrative": (180, 160, 200),
                "dice": (140, 200, 140),
                "event": (200, 180, 140),
            }
            text_color = msg_colors.get(msg.msg_type, None)

            dpg.add_text(msg.text, wrap=500, color=text_color)

            # Dice breakdown if present
            if msg.dice_breakdown:
                dpg.add_text(msg.dice_breakdown, wrap=500, color=(120, 160, 120))

            dpg.add_spacer(height=5)

    def _show_attack_dialog(self):
        """Show attack declaration dialog."""
        if dpg.does_item_exist("attack_dialog"):
            dpg.delete_item("attack_dialog")

        # Get available units
        friendly = self.coordinator.state.player_roster
        enemy = self.coordinator.state.ai_roster

        if not friendly or not enemy:
            self.add_message(BattleMessage(
                "No armies loaded. Add units first.",
                "system"
            ))
            return

        friendly_units = [u.name for u in friendly.active_units]
        enemy_units = [u.name for u in enemy.active_units]

        if not friendly_units or not enemy_units:
            self.add_message(BattleMessage(
                "No active units available for combat.",
                "system"
            ))
            return

        with dpg.window(
            label="Declare Attack",
            modal=True,
            tag="attack_dialog",
            width=450,
            height=400,
            pos=[200, 100],
        ):
            dpg.add_text("Select Attacker:")
            dpg.add_combo(
                items=friendly_units,
                default_value=friendly_units[0] if friendly_units else "",
                tag="attack_attacker",
                width=-1,
                callback=self._update_weapon_list,
            )

            dpg.add_spacer(height=5)

            dpg.add_text("Select Weapon:")
            dpg.add_combo(
                items=["(Select attacker first)"],
                tag="attack_weapon",
                width=-1,
            )

            dpg.add_spacer(height=5)

            dpg.add_text("Select Target:")
            dpg.add_combo(
                items=enemy_units,
                default_value=enemy_units[0] if enemy_units else "",
                tag="attack_target",
                width=-1,
            )

            dpg.add_spacer(height=5)

            dpg.add_text("Attack Type:")
            dpg.add_radio_button(
                items=["Shooting", "Melee"],
                default_value="Shooting",
                tag="attack_type",
                horizontal=True,
            )

            dpg.add_spacer(height=5)

            dpg.add_text("Modifiers:", color=(150, 150, 150))
            dpg.add_checkbox(label="Target in Cover", tag="attack_cover")
            dpg.add_checkbox(label="Moving", tag="attack_moving")
            dpg.add_checkbox(label="Charging", tag="attack_charging")

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Attack!",
                    callback=self._execute_attack,
                    width=120,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("attack_dialog"),
                    width=100,
                )

        # Initialize weapon list
        self._update_weapon_list()

    def _update_weapon_list(self, sender=None, app_data=None, user_data=None):
        """Update weapon dropdown based on selected attacker."""
        attacker_name = dpg.get_value("attack_attacker")
        if not attacker_name:
            return

        roster = self.coordinator.state.player_roster
        unit = roster.get_unit(attacker_name)
        if not unit:
            return

        weapons = [w.get("name", "Unknown") for w in unit.weapons]
        if not weapons:
            weapons = ["Close Combat"]

        dpg.configure_item("attack_weapon", items=weapons)
        dpg.set_value("attack_weapon", weapons[0])

    def _execute_attack(self):
        """Execute the declared attack."""
        attacker_name = dpg.get_value("attack_attacker")
        weapon_name = dpg.get_value("attack_weapon")
        target_name = dpg.get_value("attack_target")
        attack_type = dpg.get_value("attack_type")

        # Get modifiers
        modifiers = {}
        if dpg.get_value("attack_cover"):
            modifiers["cover"] = 1
        if dpg.get_value("attack_moving"):
            modifiers["moving"] = 1
        if dpg.get_value("attack_charging"):
            modifiers["charging"] = 1

        dpg.delete_item("attack_dialog")

        # Log player action
        self.add_message(BattleMessage(
            f"{attacker_name} attacks {target_name} with {weapon_name}!",
            "player",
        ))

        # Get units
        roster = self.coordinator.state.player_roster
        enemy_roster = self.coordinator.state.ai_roster

        attacker = roster.get_unit(attacker_name)
        target = enemy_roster.get_unit(target_name)

        # Find weapon
        weapon = None
        for w in attacker.weapons:
            if w.get("name") == weapon_name:
                weapon = w
                break

        if not weapon:
            weapon = {"name": weapon_name, "shots": 1, "ap": 0}

        # Execute attack via coordinator
        if attack_type == "Shooting":
            result, narrative = self.coordinator.player_declares_attack(
                attacker, target, weapon, modifiers
            )
        else:
            result = self.coordinator.rules.resolve_melee(
                attacker, target, modifiers
            )
            narrative = self.narrator.narrate_attack(result)

        # Format result
        self._display_attack_result(result, narrative)

    def _display_attack_result(self, result: AttackResult | MeleeResult, narrative: str):
        """Display attack result with dice breakdown."""
        if isinstance(result, MeleeResult):
            # Melee result contains both attacker and defender results
            self._display_melee_result(result, narrative)
            return

        # Build dice breakdown
        breakdown_lines = []

        # To-hit rolls
        if result.to_hit_rolls:
            hits_text = ", ".join(
                f"{'['+str(r.result)+']' if r.success else str(r.result)}"
                for r in result.to_hit_rolls
            )
            target = result.to_hit_rolls[0].target if result.to_hit_rolls else "?"
            breakdown_lines.append(f"To Hit ({target}+): {hits_text} = {result.hits} hits")

        # To-wound rolls
        if result.to_wound_rolls:
            wounds_text = ", ".join(
                f"{'['+str(r.result)+']' if r.success else str(r.result)}"
                for r in result.to_wound_rolls
            )
            target = result.to_wound_rolls[0].target if result.to_wound_rolls else "?"
            breakdown_lines.append(f"To Wound ({target}+): {wounds_text}")

        # Save rolls
        if result.save_rolls:
            saves_text = ", ".join(
                f"{'['+str(r.result)+']' if r.success else str(r.result)}"
                for r in result.save_rolls
            )
            target = result.save_rolls[0].target if result.save_rolls else "?"
            breakdown_lines.append(f"Saves ({target}+): {saves_text} = {result.saves_made} saves")

        dice_breakdown = "\n".join(breakdown_lines) if breakdown_lines else None

        # Combat summary
        summary = f"{result.attacker_name} vs {result.target_name}:\n"
        summary += f"  Hits: {result.hits}, Wounds: {result.wounds_caused}, "
        summary += f"Saves Failed: {result.saves_failed}\n"
        summary += f"  Damage: {result.damage_dealt}, Models Killed: {result.models_killed}"

        if result.effects:
            summary += f"\n  Effects: {', '.join(result.effects)}"

        self.add_message(BattleMessage(
            summary,
            "combat",
            "combat",
            dice_breakdown,
        ))

        # Narration
        if narrative:
            self.add_message(BattleMessage(
                narrative,
                "ai",
                "narrative",
            ))

    def _display_melee_result(self, result: MeleeResult, narrative: str):
        """Display melee combat result."""
        # Attacker result
        att_result = result.attacker_result
        if att_result:
            summary = f"{result.attacker_name} attacks:\n"
            summary += f"  Hits: {att_result.hits}, Wounds: {att_result.wounds_caused}, "
            summary += f"Models Killed: {att_result.models_killed}"

            self.add_message(BattleMessage(summary, "combat", "combat"))

        # Defender strikes back
        def_result = result.defender_result
        if def_result:
            summary = f"{result.defender_name} strikes back:\n"
            summary += f"  Hits: {def_result.hits}, Wounds: {def_result.wounds_caused}, "
            summary += f"Models Killed: {def_result.models_killed}"

            self.add_message(BattleMessage(summary, "combat", "combat"))

        # Narration
        if narrative:
            self.add_message(BattleMessage(narrative, "ai", "narrative"))

    def _execute_ai_turn(self):
        """Execute the AI opponent's turn."""
        self.add_message(BattleMessage(
            "AI Commander takes their turn...",
            "system",
        ))

        # Execute AI turn
        activations, narrative = self.coordinator.opponent_takes_turn()

        if not activations:
            self.add_message(BattleMessage(
                "AI has no valid actions available.",
                "ai",
            ))
            return

        # Display each activation
        for activation in activations:
            self.add_message(BattleMessage(
                f"{activation.unit_name}: {activation.action_type.upper()}",
                "ai",
            ))

            if activation.target_name:
                self.add_message(BattleMessage(
                    f"  Target: {activation.target_name}",
                    "ai",
                ))

            if activation.result:
                self._display_attack_result(activation.result, "")

            if activation.narrative:
                self.add_message(BattleMessage(
                    activation.narrative,
                    "ai",
                    "narrative",
                ))

        # Overall narrative
        if narrative:
            self.add_message(BattleMessage(narrative, "ai", "narrative"))

    def _advance_phase(self):
        """Advance to the next battle phase."""
        old_phase = self.coordinator.state.current_phase
        self.coordinator.advance_phase()
        new_phase = self.coordinator.state.current_phase

        self.add_message(BattleMessage(
            f"Phase: {old_phase.value} -> {new_phase.value}",
            "system",
        ))

    def _show_morale_dialog(self):
        """Show morale check dialog."""
        if dpg.does_item_exist("morale_dialog"):
            dpg.delete_item("morale_dialog")

        # Get all units from both sides
        all_units = []
        if self.coordinator.state.player_roster:
            all_units.extend([
                ("Friendly: " + u.name, u, True)
                for u in self.coordinator.state.player_roster.active_units
            ])
        if self.coordinator.state.ai_roster:
            all_units.extend([
                ("Enemy: " + u.name, u, False)
                for u in self.coordinator.state.ai_roster.active_units
            ])

        if not all_units:
            self.add_message(BattleMessage(
                "No active units for morale check.",
                "system"
            ))
            return

        with dpg.window(
            label="Morale Check",
            modal=True,
            tag="morale_dialog",
            width=400,
            height=250,
            pos=[200, 150],
        ):
            dpg.add_text("Select Unit:")
            unit_names = [u[0] for u in all_units]
            dpg.add_combo(
                items=unit_names,
                default_value=unit_names[0],
                tag="morale_unit",
                width=-1,
            )

            dpg.add_text("Casualties This Turn:")
            dpg.add_slider_int(
                default_value=1,
                min_value=0,
                max_value=10,
                tag="morale_casualties",
                width=-1,
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Check",
                    callback=lambda: self._execute_morale(all_units),
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("morale_dialog"),
                    width=100,
                )

    def _execute_morale(self, all_units):
        """Execute morale check."""
        selected = dpg.get_value("morale_unit")
        casualties = dpg.get_value("morale_casualties")

        # Find unit
        unit = None
        for name, u, is_friendly in all_units:
            if name == selected:
                unit = u
                break

        if not unit:
            dpg.delete_item("morale_dialog")
            return

        # Execute morale check
        result = self.coordinator.rules.check_morale(unit, casualties)

        dpg.delete_item("morale_dialog")

        # Display result
        msg = f"Morale Check: {unit.name}\n"
        msg += f"  Roll: {result.roll.result} vs {result.leadership}\n"
        msg += f"  Result: {'PASSED' if result.passed else 'FAILED'}\n"
        msg += f"  {result.consequence}"

        self.add_message(BattleMessage(msg, "dice", "dice"))

    def _generate_event(self):
        """Generate a random battle event."""
        # Use WargameAI for event generation
        ai = WargameAI()
        event = ai.roll_event()

        self.add_message(BattleMessage(
            f"BATTLE EVENT: {event}",
            "system",
            "event",
        ))

    def _show_dice_dialog(self):
        """Show quick dice roller."""
        if dpg.does_item_exist("dice_dialog"):
            dpg.delete_item("dice_dialog")

        with dpg.window(
            label="Roll Dice",
            modal=True,
            tag="dice_dialog",
            width=300,
            height=200,
            pos=[250, 150],
        ):
            dpg.add_text("Number of Dice:")
            dpg.add_slider_int(
                default_value=1,
                min_value=1,
                max_value=20,
                tag="dice_count",
                width=-1,
            )

            dpg.add_text("Target Number (X+):")
            dpg.add_slider_int(
                default_value=4,
                min_value=2,
                max_value=6,
                tag="dice_target",
                width=-1,
            )

            dpg.add_spacer(height=5)

            dpg.add_text("Quick:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                for n in [1, 5, 10]:
                    dpg.add_button(
                        label=f"{n}d6",
                        callback=lambda s, a, c=n: self._quick_roll(c),
                        width=60,
                    )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Roll",
                    callback=self._execute_dice_roll,
                    width=100,
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.delete_item("dice_dialog"),
                    width=100,
                )

    def _quick_roll(self, count: int):
        """Quick roll dice."""
        dpg.set_value("dice_count", count)
        self._execute_dice_roll()

    def _execute_dice_roll(self):
        """Execute dice roll."""
        count = dpg.get_value("dice_count")
        target = dpg.get_value("dice_target")

        rolls = self.coordinator.rules.dice.roll_check(count, target)

        successes = sum(1 for r in rolls if r.success)
        roll_text = ", ".join(
            f"[{r.result}]" if r.success else str(r.result)
            for r in rolls
        )

        msg = f"Rolling {count}d6 needing {target}+:\n"
        msg += f"  {roll_text}\n"
        msg += f"  Successes: {successes}/{count}"

        self.add_message(BattleMessage(msg, "dice", "dice"))

        dpg.delete_item("dice_dialog")

    def clear(self):
        """Clear the battle log."""
        self.messages.clear()
        if dpg.does_item_exist(self._log_tag):
            dpg.delete_item(self._log_tag, children_only=True)


# =============================================================================
# Force Panel
# =============================================================================

class ForcePanel:
    """
    Panel showing army composition with unit status.
    """

    def __init__(
        self,
        parent: str,
        coordinator: BattleCoordinator,
        is_friendly: bool = True,
    ):
        self.parent = parent
        self.coordinator = coordinator
        self.is_friendly = is_friendly

        self._tag = f"force_{id(self)}"
        self._list_tag = f"{self._tag}_list"
        self._summary_tag = f"{self._tag}_summary"

        self._on_unit_click = None

        self._build()

    def _build(self):
        """Build the force panel."""
        color = (100, 180, 100) if self.is_friendly else (180, 100, 100)
        title = "Your Army" if self.is_friendly else "Enemy Army"

        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            dpg.add_text(title, color=color)
            dpg.add_separator()

            # Summary
            dpg.add_text(
                "0 units | 0 pts",
                tag=self._summary_tag,
                color=(150, 150, 150),
            )

            dpg.add_spacer(height=5)

            # Unit list
            with dpg.child_window(
                height=200,
                border=False,
                tag=self._list_tag,
            ):
                dpg.add_text("No units", color=(100, 100, 100))

            # Add unit button
            dpg.add_button(
                label="Add Unit",
                callback=lambda: self._show_add_unit_dialog(),
                width=-1,
            )

    def refresh(self):
        """Refresh the unit list."""
        roster = (
            self.coordinator.state.player_roster
            if self.is_friendly
            else self.coordinator.state.ai_roster
        )

        if dpg.does_item_exist(self._list_tag):
            dpg.delete_item(self._list_tag, children_only=True)

        with dpg.group(parent=self._list_tag):
            if not roster or not roster.units:
                dpg.add_text("No units", color=(100, 100, 100))
                dpg.set_value(self._summary_tag, "0 units | 0 pts")
                return

            # Summary
            active = len(roster.active_units)
            total = len(roster.units)
            points = roster.points_all
            dpg.set_value(self._summary_tag, f"{active}/{total} active | {points} pts")

            # Units by status
            for unit in roster.units:
                self._render_unit(unit)

    def _render_unit(self, unit: RosterUnit):
        """Render a single unit."""
        status_colors = {
            UnitStatus.FRESH: (100, 180, 100),
            UnitStatus.ENGAGED: (180, 180, 100),
            UnitStatus.DAMAGED: (200, 160, 100),
            UnitStatus.WOUNDED: (200, 120, 100),
            UnitStatus.ROUTING: (200, 100, 100),
            UnitStatus.DESTROYED: (100, 100, 100),
            UnitStatus.DEAD: (100, 100, 100),
            UnitStatus.FLED: (100, 100, 100),
        }
        color = status_colors.get(unit.status, (150, 150, 150))

        with dpg.group(horizontal=True):
            # Unit name with status icon
            dpg.add_selectable(
                label=f"{unit.status.icon} {unit.name}",
                callback=lambda s, a, u=unit: self._on_click(u),
                width=150,
            )

            # Model/wound display
            if unit.models_max > 1:
                dpg.add_text(
                    f"[{unit.models_current}/{unit.models_max}]",
                    color=color,
                )
            if unit.wounds_max > 1:
                dpg.add_text(
                    f"W:{unit.wounds_current}/{unit.wounds_max}",
                    color=color,
                )

    def _on_click(self, unit: RosterUnit):
        """Handle unit click."""
        if self._on_unit_click:
            self._on_unit_click(unit, self.is_friendly)

    def _show_add_unit_dialog(self):
        """Show add unit dialog."""
        tag = f"add_unit_{'friendly' if self.is_friendly else 'enemy'}"

        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        with dpg.window(
            label=f"Add {'Friendly' if self.is_friendly else 'Enemy'} Unit",
            modal=True,
            tag=tag,
            width=400,
            height=400,
            pos=[200, 100],
        ):
            dpg.add_text("Unit Name:")
            dpg.add_input_text(
                hint="e.g., Space Marines",
                tag=f"{tag}_name",
                width=-1,
            )

            dpg.add_text("Models:")
            dpg.add_slider_int(
                default_value=5,
                min_value=1,
                max_value=30,
                tag=f"{tag}_models",
                width=-1,
            )

            dpg.add_text("Wounds per Model:")
            dpg.add_slider_int(
                default_value=1,
                min_value=1,
                max_value=10,
                tag=f"{tag}_wounds",
                width=-1,
            )

            dpg.add_text("Points:")
            dpg.add_input_int(
                default_value=100,
                tag=f"{tag}_points",
                width=-1,
            )

            # Stats section
            dpg.add_text("Stats:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                dpg.add_text("WS:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_ws", width=50)
                dpg.add_text("BS:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_bs", width=50)
                dpg.add_text("S:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_s", width=50)
                dpg.add_text("T:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_t", width=50)

            with dpg.group(horizontal=True):
                dpg.add_text("Ld:")
                dpg.add_input_int(default_value=7, tag=f"{tag}_ld", width=50)
                dpg.add_text("Sv:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_sv", width=50)

            # Weapons
            dpg.add_text("Weapons (comma-separated):")
            dpg.add_input_text(
                hint="e.g., Bolter, Chainsword",
                tag=f"{tag}_weapons",
                width=-1,
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add",
                    callback=lambda: self._add_unit(tag),
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(tag),
                    width=100,
                )

    def _add_unit(self, tag: str):
        """Add the unit."""
        name = dpg.get_value(f"{tag}_name")
        models = dpg.get_value(f"{tag}_models")
        wounds = dpg.get_value(f"{tag}_wounds")
        points = dpg.get_value(f"{tag}_points")

        ws = dpg.get_value(f"{tag}_ws")
        bs = dpg.get_value(f"{tag}_bs")
        s = dpg.get_value(f"{tag}_s")
        t = dpg.get_value(f"{tag}_t")
        ld = dpg.get_value(f"{tag}_ld")
        sv = dpg.get_value(f"{tag}_sv")

        weapons_text = dpg.get_value(f"{tag}_weapons")

        if not name:
            dpg.delete_item(tag)
            return

        # Parse weapons
        weapons = []
        if weapons_text:
            for w_name in weapons_text.split(","):
                w_name = w_name.strip()
                if w_name:
                    weapons.append({
                        "name": w_name,
                        "shots": 1,
                        "ap": 0,
                        "strength": s,
                    })

        # Create unit
        manager = RosterManager()
        unit = manager.create_custom_unit(
            name=name,
            slot_type=SlotType.TROOPS,
            stats={
                "WS": ws, "BS": bs, "S": s, "T": t,
                "Ld": ld, "Sv": f"{sv}+",
            },
            weapons=weapons,
            wounds=wounds,
            models=models,
            points=points,
        )

        # Add to appropriate roster
        roster = (
            self.coordinator.state.player_roster
            if self.is_friendly
            else self.coordinator.state.ai_roster
        )

        if roster is None:
            # Create roster if needed
            roster = Roster(
                name="Your Army" if self.is_friendly else "Enemy Army",
            )
            if self.is_friendly:
                self.coordinator.state.player_roster = roster
            else:
                self.coordinator.state.ai_roster = roster

        roster.add_unit(unit)

        dpg.delete_item(tag)
        self.refresh()

    def on_unit_click(self, callback):
        """Set unit click callback."""
        self._on_unit_click = callback


# =============================================================================
# Battle State Panel
# =============================================================================

class BattleStatePanel:
    """
    Panel showing current battle state: turn, phase, game system.
    """

    def __init__(self, parent: str, coordinator: BattleCoordinator):
        self.parent = parent
        self.coordinator = coordinator

        self._tag = f"battle_state_{id(self)}"

        self._build()

    def _build(self):
        """Build the panel."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            dpg.add_text("Battle Status", color=(200, 180, 140))
            dpg.add_separator()

            # Game system
            with dpg.group(horizontal=True):
                dpg.add_text("System:", color=(150, 150, 150))
                dpg.add_text(
                    self.coordinator.rules.system_name,
                    tag=f"{self._tag}_system",
                )

            # Turn/Phase
            with dpg.group(horizontal=True):
                dpg.add_text("Turn:", color=(150, 150, 150))
                dpg.add_text("1", tag=f"{self._tag}_turn")
                dpg.add_spacer(width=20)
                dpg.add_text("Phase:", color=(150, 150, 150))
                dpg.add_text("Movement", tag=f"{self._tag}_phase")

            # Commander
            with dpg.group(horizontal=True):
                dpg.add_text("AI Commander:", color=(150, 150, 150))
                dpg.add_text(
                    self.coordinator.commander.archetype.name if self.coordinator.commander else "None",
                    tag=f"{self._tag}_commander",
                )

    def refresh(self):
        """Refresh the display."""
        state = self.coordinator.state

        dpg.set_value(f"{self._tag}_turn", str(state.turn_number))
        dpg.set_value(f"{self._tag}_phase", state.current_phase.value.title())

        if self.coordinator.commander:
            dpg.set_value(
                f"{self._tag}_commander",
                self.coordinator.commander.archetype.name,
            )


# =============================================================================
# Phase Guide Panel - Learning Aid
# =============================================================================

class PhaseGuidePanel:
    """
    Phase-by-phase guide to help players learn the game.

    Loads detailed phase information from TOML files and displays
    steps, tips, and common mistakes for the current phase.
    """

    # Phase guide data path
    GUIDE_PATH = Path(__file__).parent.parent / "wargame" / "data" / "phase_guides.toml"

    # System ID mapping
    SYSTEM_MAP = {
        "oldhammer": "oldhammer_2e",
        "opr": "opr_grimdark",
        "old_world": "old_world",
        "trench_crusade": "trench_crusade",
    }

    def __init__(self, parent: str, coordinator: BattleCoordinator):
        self.parent = parent
        self.coordinator = coordinator
        self._tag = f"phase_guide_{id(self)}"

        # Load guide data
        self._guides = self._load_guides()
        self._current_phase_index = 0

        self._build()

    def _load_guides(self) -> Dict[str, Any]:
        """Load phase guide data from TOML."""
        if not self.GUIDE_PATH.exists():
            return {}

        try:
            with open(self.GUIDE_PATH, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Error loading phase guides: {e}")
            return {}

    def _get_system_key(self) -> str:
        """Get the guide key for the current game system."""
        system_id = self.coordinator.rules.system_id
        for key, guide_id in self.SYSTEM_MAP.items():
            if key in system_id.lower():
                return guide_id
        return "oldhammer_2e"  # Default

    def _build(self):
        """Build the phase guide panel."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            dpg.add_text("Phase Guide", color=(140, 180, 220))
            dpg.add_separator()

            # Phase navigation
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="<",
                    callback=lambda: self._change_phase(-1),
                    width=30,
                )
                dpg.add_text(
                    "Movement",
                    tag=f"{self._tag}_phase_name",
                    color=(200, 180, 140),
                )
                dpg.add_button(
                    label=">",
                    callback=lambda: self._change_phase(1),
                    width=30,
                )

            # Phase order indicator
            dpg.add_text(
                "Phase 1 of 5",
                tag=f"{self._tag}_phase_order",
                color=(100, 100, 100),
            )

            dpg.add_separator()

            # Summary
            dpg.add_text("Summary:", color=(150, 150, 150))
            dpg.add_text(
                "",
                tag=f"{self._tag}_summary",
                wrap=250,
            )

            dpg.add_spacer(height=5)

            # Key rules
            with dpg.collapsing_header(
                label="Key Rules",
                default_open=True,
                tag=f"{self._tag}_key_rules_header",
            ):
                with dpg.group(tag=f"{self._tag}_key_rules"):
                    pass

            # Steps
            with dpg.collapsing_header(
                label="Step by Step",
                default_open=True,
                tag=f"{self._tag}_steps_header",
            ):
                with dpg.child_window(
                    height=200,
                    border=False,
                    tag=f"{self._tag}_steps",
                ):
                    pass

            # Common mistakes
            with dpg.collapsing_header(
                label="Common Mistakes",
                default_open=False,
                tag=f"{self._tag}_mistakes_header",
            ):
                with dpg.group(tag=f"{self._tag}_mistakes"):
                    pass

            # Tips button
            dpg.add_button(
                label="Show Tips for Current Step",
                callback=self._show_tips_popup,
                width=-1,
            )

        # Initial render
        self._render_phase()

    def _change_phase(self, direction: int):
        """Change to next/previous phase."""
        system_key = self._get_system_key()
        system_data = self._guides.get(system_key, {})
        phases = system_data.get("phases", [])

        if not phases:
            return

        self._current_phase_index = (
            self._current_phase_index + direction
        ) % len(phases)

        self._render_phase()

    def _render_phase(self):
        """Render the current phase guide."""
        system_key = self._get_system_key()
        system_data = self._guides.get(system_key, {})
        phases = system_data.get("phases", [])

        if not phases:
            dpg.set_value(f"{self._tag}_phase_name", "No guide available")
            dpg.set_value(f"{self._tag}_summary", "")
            return

        phase = phases[self._current_phase_index]
        phase_name = phase.get("name", "Unknown")
        order = phase.get("order", self._current_phase_index + 1)
        total = len(phases)

        # Update header
        dpg.set_value(f"{self._tag}_phase_name", phase_name)
        dpg.set_value(f"{self._tag}_phase_order", f"Phase {order} of {total}")

        # Update summary
        summary = phase.get("summary", {})
        dpg.set_value(f"{self._tag}_summary", summary.get("text", ""))

        # Update key rules
        self._render_key_rules(summary.get("key_rules", []))

        # Update steps
        self._render_steps(phase.get("steps", []))

        # Update mistakes
        mistakes = phase.get("common_mistakes", {}).get("mistakes", [])
        self._render_mistakes(mistakes)

    def _render_key_rules(self, rules: List[str]):
        """Render key rules list."""
        tag = f"{self._tag}_key_rules"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag, children_only=True)

        with dpg.group(parent=tag):
            for rule in rules:
                dpg.add_text(f"* {rule}", wrap=240, color=(160, 200, 160))

    def _render_steps(self, steps: List[Dict]):
        """Render step-by-step guide."""
        tag = f"{self._tag}_steps"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag, children_only=True)

        with dpg.group(parent=tag):
            for step in steps:
                step_num = step.get("step", "?")
                step_name = step.get("name", "")
                step_desc = step.get("description", "")

                # Step header
                dpg.add_text(
                    f"Step {step_num}: {step_name}",
                    color=(220, 200, 140),
                )

                # Description (truncated)
                desc_lines = step_desc.strip().split("\n")
                preview = desc_lines[0][:100] + "..." if len(desc_lines[0]) > 100 else desc_lines[0]
                dpg.add_text(preview, wrap=240, color=(150, 150, 150))

                # Expand button
                dpg.add_button(
                    label="Details...",
                    callback=lambda s, a, st=step: self._show_step_details(st),
                    width=80,
                    small=True,
                )

                dpg.add_spacer(height=5)

    def _render_mistakes(self, mistakes: List[str]):
        """Render common mistakes list."""
        tag = f"{self._tag}_mistakes"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag, children_only=True)

        with dpg.group(parent=tag):
            for mistake in mistakes:
                dpg.add_text(f"X {mistake}", wrap=240, color=(200, 140, 140))

    def _show_step_details(self, step: Dict):
        """Show full step details in a popup."""
        if dpg.does_item_exist("step_detail_popup"):
            dpg.delete_item("step_detail_popup")

        step_name = step.get("name", "Step")
        description = step.get("description", "").strip()
        tips = step.get("tips", [])

        with dpg.window(
            label=f"Step: {step_name}",
            modal=True,
            tag="step_detail_popup",
            width=500,
            height=400,
            pos=[200, 100],
        ):
            dpg.add_text("Description:", color=(150, 150, 150))
            dpg.add_text(description, wrap=480)

            if tips:
                dpg.add_spacer(height=10)
                dpg.add_separator()
                dpg.add_text("Tips:", color=(140, 200, 140))
                for tip in tips:
                    dpg.add_text(f"- {tip}", wrap=480, color=(160, 200, 160))

            dpg.add_spacer(height=10)
            dpg.add_button(
                label="Close",
                callback=lambda: dpg.delete_item("step_detail_popup"),
                width=100,
            )

    def _show_tips_popup(self):
        """Show tips for the current phase."""
        system_key = self._get_system_key()
        system_data = self._guides.get(system_key, {})
        phases = system_data.get("phases", [])

        if not phases:
            return

        phase = phases[self._current_phase_index]
        phase_name = phase.get("name", "Unknown")
        steps = phase.get("steps", [])

        if dpg.does_item_exist("tips_popup"):
            dpg.delete_item("tips_popup")

        with dpg.window(
            label=f"{phase_name} Phase Tips",
            modal=True,
            tag="tips_popup",
            width=500,
            height=450,
            pos=[200, 80],
        ):
            for step in steps:
                step_name = step.get("name", "")
                tips = step.get("tips", [])

                if tips:
                    dpg.add_text(f"{step_name}:", color=(220, 200, 140))
                    for tip in tips:
                        dpg.add_text(f"  - {tip}", wrap=480, color=(160, 200, 160))
                    dpg.add_spacer(height=5)

            # Special rules
            special = phase.get("special_rules", {}).get("rules", [])
            if special:
                dpg.add_separator()
                dpg.add_text("Special Rules:", color=(200, 180, 140))
                for rule in special:
                    name = rule.get("name", "")
                    desc = rule.get("desc", "")
                    dpg.add_text(f"{name}: {desc}", wrap=480, color=(180, 180, 200))

            dpg.add_spacer(height=10)
            dpg.add_button(
                label="Close",
                callback=lambda: dpg.delete_item("tips_popup"),
                width=100,
            )

    def refresh(self):
        """Refresh to match current game state."""
        # Update to current phase from coordinator
        current_phase = self.coordinator.state.current_phase.value.lower()

        system_key = self._get_system_key()
        system_data = self._guides.get(system_key, {})
        phases = system_data.get("phases", [])

        for i, phase in enumerate(phases):
            if phase.get("name", "").lower() == current_phase:
                self._current_phase_index = i
                break

        self._render_phase()

    def set_game_system(self, system_id: str):
        """Update for a new game system."""
        self._current_phase_index = 0
        self._render_phase()


# =============================================================================
# Main Wargame App
# =============================================================================

class WargameApp:
    """
    Main wargame application with AI opponent.
    """

    def __init__(self, game_system: str = "oldhammer_2e"):
        # Initialize rules engine
        system_config = GAME_SYSTEMS.get(game_system, GAME_SYSTEMS["oldhammer_2e"])
        self.rules: RulesEngine = system_config["engine_class"]()

        # Initialize commander
        self.commander = generate_commander("balanced_strategist")

        # Initialize coordinator
        self.coordinator = BattleCoordinator(
            rules_engine=self.rules,
            player_roster=Roster(name="Your Army"),
            ai_roster=Roster(name="Enemy Army"),
            commander=self.commander,
        )

        # Initialize narrator
        self.narrator = EnhancedNarrator(self.commander)

        # UI components
        self._chat_panel: Optional[BattleChatPanel] = None
        self._friendly_panel: Optional[ForcePanel] = None
        self._enemy_panel: Optional[ForcePanel] = None
        self._state_panel: Optional[BattleStatePanel] = None
        self._phase_guide: Optional[PhaseGuidePanel] = None

        self._build_ui()

    def _build_ui(self):
        """Build the main UI."""
        dpg.create_context()
        dpg.create_viewport(title="Oracle Wargame", width=1400, height=900)

        with dpg.window(label="Wargame", tag="main_window"):
            # Top menu bar
            with dpg.menu_bar():
                with dpg.menu(label="Battle"):
                    dpg.add_menu_item(
                        label="New Battle",
                        callback=self._new_battle,
                    )
                    dpg.add_menu_item(
                        label="Save Battle",
                        callback=self._save_battle,
                    )
                    dpg.add_menu_item(
                        label="Load Battle",
                        callback=self._load_battle,
                    )
                    dpg.add_separator()
                    dpg.add_menu_item(
                        label="Exit",
                        callback=lambda: dpg.stop_dearpygui(),
                    )

                with dpg.menu(label="Game System"):
                    for sys_id, config in GAME_SYSTEMS.items():
                        dpg.add_menu_item(
                            label=config["name"],
                            callback=lambda s, a, sid=sys_id: self._change_system(sid),
                        )

                with dpg.menu(label="Commander"):
                    for arch in COMMANDER_ARCHETYPES:
                        dpg.add_menu_item(
                            label=arch.replace("_", " ").title(),
                            callback=lambda s, a, ar=arch: self._change_commander(ar),
                        )

            # Main layout
            with dpg.group(horizontal=True):
                # Left sidebar: Forces
                with dpg.child_window(width=300, height=-1, border=True):
                    # Battle state
                    self._state_panel = BattleStatePanel(
                        dpg.last_item(), self.coordinator
                    )

                    dpg.add_separator()

                    # Friendly forces
                    self._friendly_panel = ForcePanel(
                        dpg.last_item(), self.coordinator, is_friendly=True
                    )

                    dpg.add_separator()

                    # Enemy forces
                    self._enemy_panel = ForcePanel(
                        dpg.last_item(), self.coordinator, is_friendly=False
                    )

                # Center: Battle chat
                with dpg.child_window(width=-300, height=-1, border=True):
                    self._chat_panel = BattleChatPanel(
                        dpg.last_item(),
                        self.coordinator,
                        self.narrator,
                    )

                # Right sidebar: AI controls and Phase Guide
                with dpg.child_window(width=320, height=-1, border=True):
                    # Create a tabbed view for AI and Phase Guide
                    with dpg.tab_bar(tag="right_sidebar_tabs"):
                        with dpg.tab(label="AI Controls"):
                            self._build_ai_controls(dpg.last_item())

                        with dpg.tab(label="Phase Guide"):
                            self._phase_guide = PhaseGuidePanel(
                                dpg.last_item(),
                                self.coordinator,
                            )

        dpg.set_primary_window("main_window", True)

    def _build_ai_controls(self, parent: str):
        """Build AI configuration panel."""
        with dpg.group(parent=parent):
            dpg.add_text("AI Configuration", color=(200, 140, 140))
            dpg.add_separator()

            # Doctrine
            dpg.add_text("Doctrine:", color=(150, 150, 150))
            dpg.add_combo(
                items=[d.display for d in Doctrine],
                default_value=Doctrine.ELITE.display,
                callback=self._on_doctrine_change,
                tag="ai_doctrine",
                width=-1,
            )
            dpg.add_text(
                Doctrine.ELITE.description,
                tag="ai_doctrine_desc",
                wrap=260,
                color=(120, 120, 120),
            )

            dpg.add_spacer(height=5)

            # Aggression
            dpg.add_text("Aggression:", color=(150, 150, 150))
            dpg.add_combo(
                items=[a.display for a in Aggression],
                default_value=Aggression.BALANCED.display,
                callback=self._on_aggression_change,
                tag="ai_aggression",
                width=-1,
            )

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Quick actions
            dpg.add_text("Quick Actions:", color=(150, 150, 150))

            dpg.add_button(
                label="AI Analyzes Situation",
                callback=self._ai_analyze,
                width=-1,
            )
            dpg.add_button(
                label="AI Makes Decision",
                callback=self._ai_decide,
                width=-1,
            )
            dpg.add_button(
                label="AI Takes Full Turn",
                callback=lambda: self._chat_panel._execute_ai_turn(),
                width=-1,
            )

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Dice settings
            dpg.add_text("Dice Mode:", color=(150, 150, 150))
            dpg.add_radio_button(
                items=["Auto Roll", "Manual Entry"],
                default_value="Auto Roll",
                callback=self._on_dice_mode_change,
                horizontal=True,
            )

    def _on_doctrine_change(self, sender, app_data, user_data):
        """Handle doctrine change."""
        if self.coordinator.ai:
            for d in Doctrine:
                if d.display == app_data:
                    self.coordinator.ai.tactical.doctrine = d
                    dpg.set_value("ai_doctrine_desc", d.description)
                    break

    def _on_aggression_change(self, sender, app_data, user_data):
        """Handle aggression change."""
        if self.coordinator.ai:
            for a in Aggression:
                if a.display == app_data:
                    self.coordinator.ai.tactical.aggression = a
                    break

    def _on_dice_mode_change(self, sender, app_data, user_data):
        """Handle dice mode change."""
        if app_data == "Auto Roll":
            self.coordinator.rules.dice.mode = RollingMode.AUTO
        else:
            self.coordinator.rules.dice.mode = RollingMode.MANUAL

    def _ai_analyze(self):
        """Have AI analyze the situation."""
        if not self.coordinator.ai:
            return

        threats = self.coordinator.ai.tactical.analyze_threats(
            "Enemy forces present"
        )

        if threats:
            msg = "AI Analysis:\n"
            for t in threats:
                msg += f"  [{t.level.value}] {t.target}: {t.reason}\n"
        else:
            msg = "No significant threats detected."

        self._chat_panel.add_message(BattleMessage(msg, "ai"))

    def _ai_decide(self):
        """Have AI make a tactical decision."""
        if not self.coordinator.ai:
            return

        decision = self.coordinator.ai.tactical.decide("Enemy forces present")

        msg = f"AI Decision ({decision.doctrine.display}):\n"
        msg += f"  {decision.selected.description}"

        self._chat_panel.add_message(BattleMessage(msg, "ai"))

    def _new_battle(self):
        """Start a new battle."""
        self.coordinator.state = BattleState(
            player_roster=Roster(name="Your Army"),
            ai_roster=Roster(name="Enemy Army"),
        )
        self.coordinator.start_battle()
        self._refresh_all()

        self._chat_panel.add_message(BattleMessage(
            "New battle started. Add units to begin.",
            "system",
        ))

    def _save_battle(self):
        """Save the current battle."""
        # TODO: Implement save
        self._chat_panel.add_message(BattleMessage(
            "Save not yet implemented.",
            "system",
        ))

    def _load_battle(self):
        """Load a battle."""
        # TODO: Implement load
        self._chat_panel.add_message(BattleMessage(
            "Load not yet implemented.",
            "system",
        ))

    def _change_system(self, system_id: str):
        """Change the game system."""
        config = GAME_SYSTEMS.get(system_id)
        if not config:
            return

        self.rules = config["engine_class"]()
        self.coordinator.rules = self.rules

        self._state_panel.refresh()

        # Update phase guide to new system
        if self._phase_guide:
            self._phase_guide.set_game_system(system_id)

        self._chat_panel.add_message(BattleMessage(
            f"Changed game system to: {config['name']}",
            "system",
        ))

    def _change_commander(self, archetype: str):
        """Change the AI commander."""
        self.commander = generate_commander(archetype)
        self.coordinator.commander = self.commander
        self.narrator = EnhancedNarrator(self.commander)
        self._chat_panel.narrator = self.narrator

        self._state_panel.refresh()

        self._chat_panel.add_message(BattleMessage(
            f"AI Commander is now: {archetype.replace('_', ' ').title()}",
            "ai",
        ))

    def _refresh_all(self):
        """Refresh all panels."""
        if self._friendly_panel:
            self._friendly_panel.refresh()
        if self._enemy_panel:
            self._enemy_panel.refresh()
        if self._state_panel:
            self._state_panel.refresh()
        if self._phase_guide:
            self._phase_guide.refresh()

    def run(self):
        """Run the application."""
        dpg.setup_dearpygui()
        dpg.show_viewport()

        # Initial message
        self._chat_panel.add_message(BattleMessage(
            f"Welcome to Oracle Wargame! Using {self.rules.system_name}.",
            "system",
        ))
        self._chat_panel.add_message(BattleMessage(
            "Add units to both armies, then declare attacks or let the AI take turns.",
            "system",
        ))

        dpg.start_dearpygui()
        dpg.destroy_context()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Launch the wargame app."""
    app = WargameApp()
    app.run()


if __name__ == "__main__":
    main()
