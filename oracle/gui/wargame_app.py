"""
Wargame App - Solo Wargaming with AI Opponent

A tabletop wargaming assistant where:
- The AI opponent actually plays by the rules (rolls dice, applies modifiers)
- Combat results include full dice breakdowns
- Commander personalities narrate the battle
- Both armies are tracked with wounds and model counts
"""

from __future__ import annotations

import json
import random
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

import dearpygui.dearpygui as dpg

from oracle.gui import style

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
    BattleOutcome,
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
# Faction Data Loader
# =============================================================================

# Map game system IDs to faction directories
FACTION_DIRS = {
    "oldhammer_2e": "oldhammer_2e",
    "opr_grimdark": "grimdark_future",
    "old_world": "old_world",
    "trench_crusade": "trench_crusade",  # May need to create this
}


def load_factions_for_system(system_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all faction data for a game system.

    Returns dict of {faction_name: faction_data} where faction_data includes units list.
    """
    factions = {}

    faction_dir_name = FACTION_DIRS.get(system_id)
    if not faction_dir_name:
        return factions

    data_path = Path(__file__).parent.parent / "data" / "wargames" / faction_dir_name / "factions"

    if not data_path.exists():
        return factions

    for toml_file in data_path.glob("*.toml"):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)
                faction_name = data.get("name", toml_file.stem.replace("_", " ").title())
                factions[faction_name] = data
        except Exception as e:
            print(f"Error loading faction {toml_file}: {e}")

    return factions


def get_units_from_faction(faction_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract unit list from faction data."""
    return faction_data.get("units", [])


def load_wargear_for_system(system_id: str) -> Dict[str, Any]:
    """
    Load wargear data for a game system.

    Returns dict with 'wargear' list and optional 'wargear_lists' mapping.
    """
    wargear_dir_name = FACTION_DIRS.get(system_id)
    if not wargear_dir_name:
        return {}

    wargear_path = Path(__file__).parent.parent / "data" / "wargames" / wargear_dir_name / "wargear.toml"

    if not wargear_path.exists():
        return {}

    try:
        with open(wargear_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Error loading wargear: {e}")
        return {}


def load_chaos_gifts() -> Dict[str, Any]:
    """
    Load Chaos gifts/mutations data for Oldhammer 2e.

    Returns dict with 'marks', 'mutations', 'daemon_weapons', 'rewards'.
    """
    gifts_path = Path(__file__).parent.parent / "data" / "wargames" / "oldhammer_2e" / "chaos_gifts.toml"

    if not gifts_path.exists():
        return {}

    try:
        with open(gifts_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Error loading chaos gifts: {e}")
        return {}


def load_test_detachments() -> List[Dict[str, Any]]:
    """
    Load pre-built test detachments for quick army setup.

    Returns list of detachment dicts with units.
    """
    detachments_path = Path(__file__).parent.parent / "data" / "wargames" / "oldhammer_2e" / "test_detachments.toml"

    if not detachments_path.exists():
        return []

    try:
        with open(detachments_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("detachments", [])
    except Exception as e:
        print(f"Error loading test detachments: {e}")
        return []


# =============================================================================
# Force Organization Constraints (2nd Edition)
# =============================================================================

FORCE_ORG_2E = {
    "HQ": {"min": 1, "max": 2},
    "Troops": {"min": 2, "max": 6},
    "Elites": {"min": 0, "max": 3},
    "Fast Attack": {"min": 0, "max": 3},
    "Heavy Support": {"min": 0, "max": 3},
}


def validate_force_org(roster: "Roster") -> List[str]:
    """
    Validate a roster against 2nd Edition force organization.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Count units by category
    category_counts = {}
    for unit in roster.units:
        # Try to get category from unit data
        category = "Troops"  # Default
        if hasattr(unit, 'slot_type'):
            slot_val = unit.slot_type.value if hasattr(unit.slot_type, 'value') else str(unit.slot_type)
            category_map = {
                "hq": "HQ",
                "troops": "Troops",
                "elites": "Elites",
                "fast_attack": "Fast Attack",
                "heavy_support": "Heavy Support",
            }
            category = category_map.get(slot_val.lower(), "Troops")

        category_counts[category] = category_counts.get(category, 0) + 1

    # Check constraints
    for cat, limits in FORCE_ORG_2E.items():
        count = category_counts.get(cat, 0)
        if count < limits["min"]:
            errors.append(f"{cat}: Need at least {limits['min']}, have {count}")
        if count > limits["max"]:
            errors.append(f"{cat}: Maximum {limits['max']}, have {count}")

    return errors


def validate_unit_size(unit_data: Dict[str, Any], model_count: int) -> Optional[str]:
    """
    Validate unit model count against allowed range.

    Returns error message or None if valid.
    """
    models_str = str(unit_data.get("models", "1"))

    if "-" in models_str:
        parts = models_str.split("-")
        min_models = int(parts[0])
        max_models = int(parts[-1])
    else:
        min_models = max_models = int(models_str) if models_str.isdigit() else 1

    if model_count < min_models:
        return f"Minimum {min_models} models required, have {model_count}"
    if model_count > max_models:
        return f"Maximum {max_models} models allowed, have {model_count}"

    return None


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
        "description": "WWI horror skirmish - 2d6 vs 7 system",
        "engine_class": TrenchCrusadeEngine,
    },
}

COMMANDER_ARCHETYPES = [
    "aggressive_blitzer",
    "cautious_planner",
    "cunning_feinter",
    "stubborn_defender",
    "methodical_grinder",
    "glory_hunter",
    "ruthless_pragmatist",
]


def phase_display(phase: BattlePhase) -> str:
    """Human-readable name for a battle phase, e.g. PLAYER_SHOOTING -> 'Player Shooting'."""
    return phase.name.replace("_", " ").title()


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

    # Keep at most this many messages alive in the log (oldest are deleted).
    MAX_LOG_MESSAGES = 500

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

        # Set by WargameApp so battle actions can refresh the status panels.
        self.on_state_change: Optional[Callable[[], None]] = None

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
        """Add a message to the log, trim old entries, and scroll to the newest."""
        self.messages.append(msg)
        self._render_message(msg)

        # Cap the log: drop oldest messages/items beyond MAX_LOG_MESSAGES.
        if len(self.messages) > self.MAX_LOG_MESSAGES:
            self.messages = self.messages[-self.MAX_LOG_MESSAGES:]
        if dpg.does_item_exist(self._log_tag):
            children = dpg.get_item_children(self._log_tag, 1) or []
            for old_child in children[: max(0, len(children) - self.MAX_LOG_MESSAGES)]:
                dpg.delete_item(old_child)

            # Auto-scroll to the newest message (-1.0 = scroll to end).
            dpg.set_y_scroll(self._log_tag, -1.0)

    def _notify_state_change(self):
        """Tell the app that battle state changed so panels can refresh."""
        if self.on_state_change:
            self.on_state_change()

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
        friendly = self.coordinator.player_roster
        enemy = self.coordinator.ai_roster

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
            pos=style.centered_pos(450, 400),
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

        roster = self.coordinator.player_roster
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
        roster = self.coordinator.player_roster
        enemy_roster = self.coordinator.ai_roster

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

        # Casualties may have ended the battle; panels need fresh numbers.
        self._check_battle_end()
        self._notify_state_change()

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

        # Casualties may have ended the battle; panels need fresh numbers.
        self._check_battle_end()
        self._notify_state_change()

    def _advance_phase(self):
        """Advance to the next battle phase (or end the turn / the battle)."""
        state = self.coordinator.state

        if state.outcome != BattleOutcome.ONGOING:
            self.add_message(BattleMessage(
                "The battle is over. Start a New Battle from the Battle menu.",
                "system",
            ))
            return

        old_phase = state.current_phase
        if old_phase == BattlePhase.END_TURN:
            # Turn is complete: the coordinator checks victory and either
            # starts the next turn or ends the battle.
            summary = self.coordinator.end_turn()
            if state.outcome != BattleOutcome.ONGOING:
                self._announce_battle_end(summary)
            else:
                self.add_message(BattleMessage(summary, "system"))
        else:
            state.advance_phase()
            self.add_message(BattleMessage(
                f"Phase: {phase_display(old_phase)} -> {phase_display(state.current_phase)}",
                "system",
            ))

        self._notify_state_change()

    def _check_battle_end(self):
        """After combat, check whether either army is wiped out and narrate the ending."""
        state = self.coordinator.state
        if state.outcome != BattleOutcome.ONGOING:
            return
        state.check_victory(self.coordinator.player_roster, self.coordinator.ai_roster)
        if state.outcome != BattleOutcome.ONGOING:
            self._announce_battle_end(self.coordinator.narrate_battle_end())

    def _announce_battle_end(self, narrative: str):
        """Display the battle-end banner and the commander's closing narration."""
        outcome_labels = {
            BattleOutcome.PLAYER_VICTORY: "VICTORY! The enemy army is broken.",
            BattleOutcome.AI_VICTORY: "DEFEAT. Your army is broken.",
            BattleOutcome.DRAW: "DRAW. Both armies withdraw from the field.",
        }
        label = outcome_labels.get(self.coordinator.state.outcome, "The battle is over.")
        self.add_message(BattleMessage(f"BATTLE OVER - {label}", "system", "event"))
        if narrative:
            self.add_message(BattleMessage(narrative, "ai", "narrative"))

    def _show_morale_dialog(self):
        """Show morale check dialog."""
        if dpg.does_item_exist("morale_dialog"):
            dpg.delete_item("morale_dialog")

        # Get all units from both sides
        all_units = []
        if self.coordinator.player_roster:
            all_units.extend([
                ("Friendly: " + u.name, u, True)
                for u in self.coordinator.player_roster.active_units
            ])
        if self.coordinator.ai_roster:
            all_units.extend([
                ("Enemy: " + u.name, u, False)
                for u in self.coordinator.ai_roster.active_units
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
            pos=style.centered_pos(400, 250),
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
            pos=style.centered_pos(300, 200),
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

            dpg.add_spacer(height=5)

            # Roster management buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Load Detachment",
                    callback=lambda: self._show_load_detachment_dialog(),
                    width=110,
                )
                dpg.add_button(
                    label="Validate",
                    callback=lambda: self._validate_roster(),
                    width=70,
                )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save Roster",
                    callback=lambda: self._show_save_roster_dialog(),
                    width=90,
                )
                dpg.add_button(
                    label="Load Roster",
                    callback=lambda: self._show_load_roster_dialog(),
                    width=90,
                )

    def refresh(self):
        """Refresh the unit list."""
        roster = (
            self.coordinator.player_roster
            if self.is_friendly
            else self.coordinator.ai_roster
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
        """Show add unit dialog with faction/unit selection."""
        tag = f"add_unit_{'friendly' if self.is_friendly else 'enemy'}"

        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        # Get current game system from coordinator
        system_id = self.coordinator.rules.system_id if self.coordinator.rules else "oldhammer_2e"

        # Load factions for this system
        self._factions = load_factions_for_system(system_id)
        self._current_unit_data = None

        with dpg.window(
            label=f"Add {'Friendly' if self.is_friendly else 'Enemy'} Unit",
            modal=True,
            tag=tag,
            width=500,
            height=550,
            pos=style.centered_pos(500, 550),
        ):
            # Faction selection
            dpg.add_text("Select Faction:", color=(150, 200, 150))
            faction_names = list(self._factions.keys()) if self._factions else ["(No factions found)"]
            dpg.add_combo(
                items=faction_names,
                default_value=faction_names[0] if faction_names else "",
                tag=f"{tag}_faction",
                width=-1,
                callback=lambda s, a: self._on_faction_selected(tag, a),
            )

            # Unit selection
            dpg.add_text("Select Unit:", color=(150, 200, 150))
            dpg.add_combo(
                items=["(Select faction first)"],
                tag=f"{tag}_unit_select",
                width=-1,
                callback=lambda s, a: self._on_unit_selected(tag, a),
            )

            dpg.add_separator()
            dpg.add_text("Unit Details (editable):", color=(200, 200, 100))

            # Unit name
            dpg.add_text("Unit Name:")
            dpg.add_input_text(
                hint="e.g., Space Marines",
                tag=f"{tag}_name",
                width=-1,
            )

            # Models and wounds
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("Models:")
                    dpg.add_slider_int(
                        default_value=5,
                        min_value=1,
                        max_value=30,
                        tag=f"{tag}_models",
                        width=150,
                    )
                with dpg.group():
                    dpg.add_text("Wounds/Model:")
                    dpg.add_slider_int(
                        default_value=1,
                        min_value=1,
                        max_value=10,
                        tag=f"{tag}_wounds",
                        width=150,
                    )
                with dpg.group():
                    dpg.add_text("Points:")
                    dpg.add_input_int(
                        default_value=100,
                        tag=f"{tag}_points",
                        width=100,
                    )

            # Stats section
            dpg.add_text("Stats:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                dpg.add_text("WS:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_ws", width=40)
                dpg.add_text("BS:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_bs", width=40)
                dpg.add_text("S:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_s", width=40)
                dpg.add_text("T:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_t", width=40)
                dpg.add_text("W:")
                dpg.add_input_int(default_value=1, tag=f"{tag}_w", width=40)

            with dpg.group(horizontal=True):
                dpg.add_text("I:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_i", width=40)
                dpg.add_text("A:")
                dpg.add_input_int(default_value=1, tag=f"{tag}_a", width=40)
                dpg.add_text("Ld:")
                dpg.add_input_int(default_value=7, tag=f"{tag}_ld", width=40)
                dpg.add_text("Sv:")
                dpg.add_input_int(default_value=4, tag=f"{tag}_sv", width=40)

            # Weapons
            dpg.add_text("Weapons (comma-separated):")
            dpg.add_input_text(
                hint="e.g., Bolter, Chainsword",
                tag=f"{tag}_weapons",
                width=-1,
            )

            # Special rules
            dpg.add_text("Special Rules:")
            dpg.add_input_text(
                hint="e.g., And They Shall Know No Fear",
                tag=f"{tag}_special",
                width=-1,
            )

            dpg.add_spacer(height=5)

            # Wargear and Chaos buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Select Wargear...",
                    callback=lambda: self._show_wargear_dialog(tag),
                    width=130,
                )
                dpg.add_button(
                    label="Chaos Rewards...",
                    callback=lambda: self._show_chaos_rewards_dialog(tag),
                    width=130,
                )

            dpg.add_spacer(height=5)

            # Selected wargear display
            dpg.add_text("Selected Wargear:", color=(150, 150, 150))
            dpg.add_text("(none)", tag=f"{tag}_wargear_display", wrap=450, color=(180, 180, 140))

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add Unit",
                    callback=lambda: self._add_unit(tag),
                    width=120,
                )
                dpg.add_button(
                    label="Custom Unit",
                    callback=lambda: self._clear_form(tag),
                    width=120,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(tag),
                    width=100,
                )

        # Initialize wargear storage
        self._selected_wargear = []
        self._selected_chaos_gifts = []

        # Auto-select first faction if available
        if faction_names and faction_names[0] != "(No factions found)":
            self._on_faction_selected(tag, faction_names[0])

    def _on_faction_selected(self, tag: str, faction_name: str):
        """Handle faction selection - populate unit dropdown."""
        if faction_name not in self._factions:
            return

        faction_data = self._factions[faction_name]
        units = get_units_from_faction(faction_data)

        unit_names = [u.get("name", "Unknown") for u in units]
        if not unit_names:
            unit_names = ["(No units in faction)"]

        if dpg.does_item_exist(f"{tag}_unit_select"):
            dpg.configure_item(f"{tag}_unit_select", items=unit_names)
            dpg.set_value(f"{tag}_unit_select", unit_names[0])

            # Auto-select first unit
            if units:
                self._on_unit_selected(tag, unit_names[0])

    def _on_unit_selected(self, tag: str, unit_name: str):
        """Handle unit selection - populate form with unit data."""
        faction_name = dpg.get_value(f"{tag}_faction")
        if faction_name not in self._factions:
            return

        faction_data = self._factions[faction_name]
        units = get_units_from_faction(faction_data)

        # Find the selected unit
        unit_data = None
        for u in units:
            if u.get("name") == unit_name:
                unit_data = u
                break

        if not unit_data:
            return

        self._current_unit_data = unit_data
        stats = unit_data.get("stats", {})

        # Populate form
        dpg.set_value(f"{tag}_name", unit_data.get("name", ""))

        # Parse models (could be "5" or "5-10")
        models_str = str(unit_data.get("models", "5"))
        if "-" in models_str:
            models = int(models_str.split("-")[0])  # Use minimum
        else:
            models = int(models_str)
        dpg.set_value(f"{tag}_models", models)

        # Wounds
        wounds = stats.get("W", 1)
        if isinstance(wounds, str):
            wounds = int(wounds) if wounds.isdigit() else 1
        dpg.set_value(f"{tag}_wounds", wounds)

        # Points
        dpg.set_value(f"{tag}_points", unit_data.get("points", 100))

        # Stats
        def get_stat(name, default=4):
            val = stats.get(name, default)
            if isinstance(val, str):
                val = val.replace("+", "").replace("-", "")
                return int(val) if val.isdigit() else default
            return int(val) if val else default

        dpg.set_value(f"{tag}_ws", get_stat("WS", 4))
        dpg.set_value(f"{tag}_bs", get_stat("BS", 4))
        dpg.set_value(f"{tag}_s", get_stat("S", 4))
        dpg.set_value(f"{tag}_t", get_stat("T", 4))
        dpg.set_value(f"{tag}_w", get_stat("W", 1))
        dpg.set_value(f"{tag}_i", get_stat("I", 4))
        dpg.set_value(f"{tag}_a", get_stat("A", 1))
        dpg.set_value(f"{tag}_ld", get_stat("Ld", 7))

        # Save value - extract number from "3+" format
        sv = stats.get("Sv", "4+")
        if isinstance(sv, str):
            sv = sv.replace("+", "").split("/")[0]  # Handle "2+/5++" format
            sv = int(sv) if sv.isdigit() else 4
        dpg.set_value(f"{tag}_sv", sv)

        # Weapons
        weapons = unit_data.get("weapons", [])
        weapon_names = [w.get("name", "") for w in weapons]
        dpg.set_value(f"{tag}_weapons", ", ".join(weapon_names))

        # Special rules
        special = unit_data.get("special_rules", [])
        dpg.set_value(f"{tag}_special", ", ".join(special) if special else "")

    def _clear_form(self, tag: str):
        """Clear the form for custom unit entry."""
        dpg.set_value(f"{tag}_name", "")
        dpg.set_value(f"{tag}_models", 5)
        dpg.set_value(f"{tag}_wounds", 1)
        dpg.set_value(f"{tag}_points", 100)
        dpg.set_value(f"{tag}_ws", 4)
        dpg.set_value(f"{tag}_bs", 4)
        dpg.set_value(f"{tag}_s", 4)
        dpg.set_value(f"{tag}_t", 4)
        dpg.set_value(f"{tag}_w", 1)
        dpg.set_value(f"{tag}_i", 4)
        dpg.set_value(f"{tag}_a", 1)
        dpg.set_value(f"{tag}_ld", 7)
        dpg.set_value(f"{tag}_sv", 4)
        dpg.set_value(f"{tag}_weapons", "")
        dpg.set_value(f"{tag}_special", "")
        self._current_unit_data = None

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
        w = dpg.get_value(f"{tag}_w")
        i = dpg.get_value(f"{tag}_i")
        a = dpg.get_value(f"{tag}_a")
        ld = dpg.get_value(f"{tag}_ld")
        sv = dpg.get_value(f"{tag}_sv")

        weapons_text = dpg.get_value(f"{tag}_weapons")
        special_text = dpg.get_value(f"{tag}_special")

        if not name:
            dpg.delete_item(tag)
            return

        # Use weapon data from TOML if available, otherwise parse text
        weapons = []
        if self._current_unit_data and self._current_unit_data.get("weapons"):
            # Use detailed weapon data from TOML
            weapons = self._current_unit_data.get("weapons", [])
        elif weapons_text:
            # Parse simple weapon names
            for w_name in weapons_text.split(","):
                w_name = w_name.strip()
                if w_name:
                    weapons.append({
                        "name": w_name,
                        "shots": 1,
                        "ap": 0,
                        "strength": s,
                    })

        # Parse special rules
        special_rules = []
        if special_text:
            special_rules = [r.strip() for r in special_text.split(",") if r.strip()]

        # Calculate total points including wargear
        wargear_points = sum(w.get("points", 0) for w in self._selected_wargear)
        chaos_points = sum(g.get("points", 0) for g in self._selected_chaos_gifts)
        total_points = points + wargear_points + chaos_points

        # Build wargear list
        wargear_names = [w.get("name", "") for w in self._selected_wargear]
        for g in self._selected_chaos_gifts:
            wargear_names.append(f"[{g.get('type', 'gift').upper()}] {g.get('name', '')}")

        # Apply stat modifiers from Chaos gifts
        modified_stats = {
            "WS": ws, "BS": bs, "S": s, "T": t,
            "W": w, "I": i, "A": a,
            "Ld": ld, "Sv": f"{sv}+",
        }
        for gift in self._selected_chaos_gifts:
            stat_mods = gift.get("stat_mods", {})
            for stat_key, mod_value in stat_mods.items():
                if stat_key in modified_stats and isinstance(modified_stats[stat_key], int):
                    modified_stats[stat_key] = modified_stats[stat_key] + mod_value

        # Add any special rules from Chaos gifts
        for gift in self._selected_chaos_gifts:
            gift_rules = gift.get("special_rules", [])
            for rule in gift_rules:
                if rule not in special_rules:
                    special_rules.append(rule)

        # Create unit
        manager = RosterManager()
        unit = manager.create_custom_unit(
            name=name,
            slot_type=SlotType.TROOPS,
            stats=modified_stats,
            weapons=weapons,
            wargear=wargear_names,
            wounds=wounds,
            models=models,
            points=total_points,
        )

        # Add special rules to unit abilities
        if special_rules:
            for rule in special_rules:
                unit.add_ability(rule)

        # Add to appropriate roster
        roster = (
            self.coordinator.player_roster
            if self.is_friendly
            else self.coordinator.ai_roster
        )

        roster.add_unit(unit)

        dpg.delete_item(tag)
        self.refresh()

    def on_unit_click(self, callback):
        """Set unit click callback."""
        self._on_unit_click = callback

    def _show_wargear_dialog(self, parent_tag: str):
        """Show wargear selection dialog."""
        if dpg.does_item_exist("wargear_dialog"):
            dpg.delete_item("wargear_dialog")

        # Get system ID from coordinator
        system_id = self.coordinator.rules.system_id if self.coordinator.rules else "oldhammer_2e"
        wargear_data = load_wargear_for_system(system_id)
        wargear_items = wargear_data.get("wargear", [])

        if not wargear_items:
            return

        # Safety: dialog may be opened before any selection exists.
        if not hasattr(self, "_selected_wargear"):
            self._selected_wargear = []

        # Map item name -> checkbox tag so Clear All / Randomize can sync the UI.
        self._wargear_checkbox_tags: Dict[str, str] = {}

        # Group wargear by type
        wargear_by_type = {}
        for item in wargear_items:
            item_type = item.get("type", "other")
            if item_type not in wargear_by_type:
                wargear_by_type[item_type] = []
            wargear_by_type[item_type].append(item)

        with dpg.window(
            label="Select Wargear",
            modal=True,
            tag="wargear_dialog",
            width=600,
            height=500,
            pos=style.centered_pos(600, 500),
        ):
            dpg.add_text("Select wargear for this unit.")
            dpg.add_text("Points costs are added to unit total.", color=(150, 150, 150))

            dpg.add_spacer(height=5)

            # Random wargear buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Random Loadout",
                    callback=lambda: self._randomize_wargear(parent_tag, wargear_items),
                    width=130,
                )
                dpg.add_text("(D3 random items)", color=(150, 150, 150))

            dpg.add_spacer(height=5)

            # Running total
            with dpg.group(horizontal=True):
                dpg.add_text("Total Wargear Cost:")
                dpg.add_text("0 pts", tag="wargear_total_pts", color=(200, 180, 100))

            dpg.add_separator()

            # Wargear tabs by type
            selected_names = {w.get("name") for w in self._selected_wargear}
            with dpg.tab_bar():
                for wg_type, items in sorted(wargear_by_type.items()):
                    with dpg.tab(label=wg_type.title()):
                        with dpg.child_window(height=300, border=False):
                            for item in items:
                                item_name = item.get("name", "Unknown")
                                item_pts = item.get("points", 0)
                                item_desc = item.get("description", "")
                                effects = item.get("effects", [])

                                checkbox_tag = f"wg_{item_name.replace(' ', '_')}"
                                self._wargear_checkbox_tags[item_name] = checkbox_tag
                                with dpg.group(horizontal=True):
                                    dpg.add_checkbox(
                                        label=f"{item_name} ({item_pts} pts)",
                                        tag=checkbox_tag,
                                        default_value=item_name in selected_names,
                                        callback=self._on_wargear_checkbox,
                                        user_data=(item, parent_tag),
                                    )
                                if effects:
                                    dpg.add_text(f"  {', '.join(effects)}", color=(120, 150, 120))

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Done",
                    callback=lambda: dpg.delete_item("wargear_dialog"),
                    width=100,
                )
                dpg.add_button(
                    label="Clear All",
                    callback=lambda: self._clear_wargear(parent_tag),
                    width=100,
                )

        # Sync the running total with any already-selected wargear.
        self._update_wargear_display(parent_tag)

    def _sync_wargear_checkboxes(self):
        """Set every wargear checkbox to match the backing selection list."""
        selected_names = {w.get("name") for w in self._selected_wargear}
        for item_name, checkbox_tag in getattr(self, "_wargear_checkbox_tags", {}).items():
            if dpg.does_item_exist(checkbox_tag):
                dpg.set_value(checkbox_tag, item_name in selected_names)

    def _randomize_wargear(self, parent_tag: str, wargear_items: List[Dict[str, Any]]):
        """Randomly select D3 wargear items."""
        self._selected_wargear = []

        if not wargear_items:
            return

        # Roll D3 for number of items
        num_items = random.randint(1, 3)

        # Pick random items (no duplicates)
        available = list(wargear_items)
        for _ in range(min(num_items, len(available))):
            if available:
                item = random.choice(available)
                available.remove(item)
                self._selected_wargear.append(item)

        self._sync_wargear_checkboxes()
        self._update_wargear_display(parent_tag)

    def _on_wargear_checkbox(self, sender, app_data, user_data):
        """Checkbox callback: app_data is the new checked state."""
        item, parent_tag = user_data
        item_name = item.get("name", "Unknown")

        # Drive the selection from the checkbox state so they can't desync.
        self._selected_wargear = [
            w for w in self._selected_wargear if w.get("name") != item_name
        ]
        if app_data:
            self._selected_wargear.append(item)

        self._update_wargear_display(parent_tag)

    def _clear_wargear(self, parent_tag: str):
        """Clear all selected wargear."""
        self._selected_wargear = []
        self._sync_wargear_checkboxes()
        self._update_wargear_display(parent_tag)

    def _update_wargear_display(self, parent_tag: str):
        """Update the wargear display text."""
        if not self._selected_wargear:
            display_text = "(none)"
            total_pts = 0
        else:
            names = [f"{w.get('name')} ({w.get('points', 0)}pts)" for w in self._selected_wargear]
            display_text = ", ".join(names)
            total_pts = sum(w.get("points", 0) for w in self._selected_wargear)

        if dpg.does_item_exist(f"{parent_tag}_wargear_display"):
            dpg.set_value(f"{parent_tag}_wargear_display", display_text)

        if dpg.does_item_exist("wargear_total_pts"):
            dpg.set_value("wargear_total_pts", f"{total_pts} pts")

    def _show_chaos_rewards_dialog(self, parent_tag: str):
        """Show Chaos rewards/mutations selection dialog."""
        if dpg.does_item_exist("chaos_rewards_dialog"):
            dpg.delete_item("chaos_rewards_dialog")

        chaos_data = load_chaos_gifts()
        if not chaos_data:
            return

        marks = chaos_data.get("marks", [])
        mutations = chaos_data.get("mutations", [])
        daemon_weapons = chaos_data.get("daemon_weapons", [])
        rewards = chaos_data.get("rewards", [])

        # Safety: dialog may be opened before any selection exists.
        if not hasattr(self, "_selected_chaos_gifts"):
            self._selected_chaos_gifts = []

        # Map gift name -> checkbox tag so Clear All / Randomize can sync the UI.
        self._chaos_checkbox_tags: Dict[str, str] = {}
        selected_gift_names = {g.get("name") for g in self._selected_chaos_gifts}

        with dpg.window(
            label="Chaos Rewards & Mutations",
            modal=True,
            tag="chaos_rewards_dialog",
            width=650,
            height=550,
            pos=style.centered_pos(650, 550),
        ):
            dpg.add_text("Path to Glory", color=(200, 100, 100))
            dpg.add_text("Select Chaos gifts for your champion.", color=(150, 150, 150))

            dpg.add_spacer(height=5)

            # Quick randomize buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Randomize Champion",
                    callback=lambda: self._randomize_chaos_champion(parent_tag),
                    width=150,
                )
                dpg.add_text("(Random mark + D3 mutations)", color=(150, 150, 150))

            dpg.add_spacer(height=5)

            # Running total
            with dpg.group(horizontal=True):
                dpg.add_text("Total Gift Cost:")
                dpg.add_text("0 pts", tag="chaos_total_pts", color=(200, 100, 100))

            dpg.add_separator()

            # Tabs for different gift types
            with dpg.tab_bar():
                # Marks of Chaos
                with dpg.tab(label="Marks"):
                    dpg.add_text("A champion can bear only ONE Mark.", color=(200, 150, 100))
                    with dpg.child_window(height=250, border=False):
                        for mark in marks:
                            name = mark.get("name", "Unknown")
                            god = mark.get("god", "")
                            pts = mark.get("points", 0)
                            desc = mark.get("description", "")
                            rules = mark.get("special_rules", [])

                            mark_tag = f"chaos_mark_{name.replace(' ', '_')}"
                            self._chaos_checkbox_tags[name] = mark_tag
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(
                                    label=f"{name} ({pts} pts)",
                                    tag=mark_tag,
                                    default_value=name in selected_gift_names,
                                    callback=self._on_chaos_checkbox,
                                    user_data=("mark", mark, parent_tag),
                                )
                            dpg.add_text(f"  {desc}", color=(150, 150, 150), wrap=600)
                            if rules:
                                dpg.add_text(f"  Rules: {', '.join(rules)}", color=(100, 150, 100))
                            dpg.add_spacer(height=5)

                # Mutations
                with dpg.tab(label="Mutations"):
                    dpg.add_text("Roll D100 or select mutations.", color=(200, 150, 100))
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="Roll Mutation (D100)",
                            callback=lambda: self._roll_mutation(parent_tag),
                            width=150,
                        )
                        dpg.add_button(
                            label="Roll D3 Mutations",
                            callback=lambda: self._roll_multiple_mutations(parent_tag, 3),
                            width=140,
                        )
                    dpg.add_spacer(height=5)

                    with dpg.child_window(height=220, border=False):
                        for mut in mutations:
                            name = mut.get("name", "Unknown")
                            pts = mut.get("points", 0)
                            desc = mut.get("description", "")
                            stat_mods = mut.get("stat_mods", {})

                            mut_tag = f"chaos_mut_{name.replace(' ', '_')}"
                            self._chaos_checkbox_tags[name] = mut_tag
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(
                                    label=f"{name} ({pts} pts)",
                                    tag=mut_tag,
                                    default_value=name in selected_gift_names,
                                    callback=self._on_chaos_checkbox,
                                    user_data=("mutation", mut, parent_tag),
                                )
                            if stat_mods:
                                mods_str = ", ".join(f"+{v} {k}" for k, v in stat_mods.items())
                                dpg.add_text(f"  Stats: {mods_str}", color=(150, 180, 150))

                # Daemon Weapons
                with dpg.tab(label="Daemon Weapons"):
                    dpg.add_text("Powerful but dangerous.", color=(200, 100, 100))
                    with dpg.child_window(height=250, border=False):
                        for weapon in daemon_weapons:
                            name = weapon.get("name", "Unknown")
                            pts = weapon.get("points", 0)
                            desc = weapon.get("description", "")
                            drawback = weapon.get("drawback", "")

                            dw_tag = f"chaos_dw_{name.replace(' ', '_')}"
                            self._chaos_checkbox_tags[name] = dw_tag
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(
                                    label=f"{name} ({pts} pts)",
                                    tag=dw_tag,
                                    default_value=name in selected_gift_names,
                                    callback=self._on_chaos_checkbox,
                                    user_data=("daemon_weapon", weapon, parent_tag),
                                )
                            dpg.add_text(f"  {desc}", color=(150, 150, 150), wrap=600)
                            if drawback:
                                dpg.add_text(f"  DRAWBACK: {drawback}", color=(200, 100, 100), wrap=600)
                            dpg.add_spacer(height=5)

                # Other Rewards
                with dpg.tab(label="Rewards"):
                    with dpg.child_window(height=250, border=False):
                        for reward in rewards:
                            name = reward.get("name", "Unknown")
                            pts = reward.get("points", 0)
                            rules = reward.get("special_rules", [])

                            rew_tag = f"chaos_rew_{name.replace(' ', '_')}"
                            self._chaos_checkbox_tags[name] = rew_tag
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(
                                    label=f"{name} ({pts} pts)",
                                    tag=rew_tag,
                                    default_value=name in selected_gift_names,
                                    callback=self._on_chaos_checkbox,
                                    user_data=("reward", reward, parent_tag),
                                )
                            if rules:
                                dpg.add_text(f"  {', '.join(rules)}", color=(100, 150, 100))

            dpg.add_spacer(height=10)

            # Selected gifts display
            dpg.add_text("Selected Gifts:", color=(150, 150, 150))
            dpg.add_text("(none)", tag="chaos_selected_display", wrap=600, color=(200, 150, 150))

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Done",
                    callback=lambda: dpg.delete_item("chaos_rewards_dialog"),
                    width=100,
                )
                dpg.add_button(
                    label="Clear All",
                    callback=lambda: self._clear_chaos_gifts(parent_tag),
                    width=100,
                )

        # Sync the running total with any already-selected gifts.
        self._update_chaos_display(parent_tag)

    def _on_chaos_checkbox(self, sender, app_data, user_data):
        """Checkbox callback: app_data is the new checked state."""
        gift_type, gift, parent_tag = user_data
        gift_name = gift.get("name", "Unknown")

        # Drive the selection from the checkbox state so they can't desync.
        self._selected_chaos_gifts = [
            g for g in self._selected_chaos_gifts if g.get("name") != gift_name
        ]

        if app_data:
            # A champion can bear only ONE Mark - unselect any other marks.
            if gift_type == "mark":
                self._selected_chaos_gifts = [
                    g for g in self._selected_chaos_gifts if g.get("type") != "mark"
                ]
            gift_copy = dict(gift)
            gift_copy["type"] = gift_type
            self._selected_chaos_gifts.append(gift_copy)

        self._sync_chaos_checkboxes()
        self._update_chaos_display(parent_tag)

    def _sync_chaos_checkboxes(self):
        """Set every Chaos gift checkbox to match the backing selection list."""
        selected_names = {g.get("name") for g in self._selected_chaos_gifts}
        for gift_name, checkbox_tag in getattr(self, "_chaos_checkbox_tags", {}).items():
            if dpg.does_item_exist(checkbox_tag):
                dpg.set_value(checkbox_tag, gift_name in selected_names)

    def _randomize_chaos_champion(self, parent_tag: str):
        """Fully randomize a Chaos champion with mark and mutations."""
        # Clear existing
        self._selected_chaos_gifts = []

        chaos_data = load_chaos_gifts()
        marks = chaos_data.get("marks", [])
        mutations = chaos_data.get("mutations", [])

        # Pick random mark
        if marks:
            mark = random.choice(marks)
            mark_copy = dict(mark)
            mark_copy["type"] = "mark"
            self._selected_chaos_gifts.append(mark_copy)

        # Roll D3 mutations
        num_mutations = random.randint(1, 3)
        for _ in range(num_mutations):
            if mutations:
                # Roll D100
                roll = random.randint(1, 100)
                selected = None
                for mut in mutations:
                    roll_range = mut.get("roll_range", [0, 0])
                    if roll_range[0] <= roll <= roll_range[1]:
                        selected = mut
                        break
                if not selected:
                    selected = random.choice(mutations)

                mut_copy = dict(selected)
                mut_copy["type"] = "mutation"
                self._selected_chaos_gifts.append(mut_copy)

        self._sync_chaos_checkboxes()
        self._update_chaos_display(parent_tag)

        if dpg.does_item_exist("chaos_selected_display"):
            mark_name = self._selected_chaos_gifts[0].get("name", "None") if self._selected_chaos_gifts else "None"
            dpg.set_value("chaos_selected_display",
                          f"Randomized! Mark: {mark_name}, {num_mutations} mutations rolled.")

    def _roll_multiple_mutations(self, parent_tag: str, num_dice: int):
        """Roll for multiple mutations (D3 or more)."""
        count = random.randint(1, num_dice)
        for _ in range(count):
            self._roll_mutation(parent_tag)

        if dpg.does_item_exist("chaos_selected_display"):
            dpg.set_value("chaos_selected_display",
                          f"Rolled D{num_dice} = {count} mutations! See selected gifts above.")

    def _roll_mutation(self, parent_tag: str):
        """Roll for a random mutation."""
        chaos_data = load_chaos_gifts()
        mutations = chaos_data.get("mutations", [])

        if not mutations:
            return

        # Roll D100
        roll = random.randint(1, 100)

        # Find matching mutation
        selected_mutation = None
        for mut in mutations:
            roll_range = mut.get("roll_range", [0, 0])
            if roll_range[0] <= roll <= roll_range[1]:
                selected_mutation = mut
                break

        if not selected_mutation:
            # Default to random selection
            selected_mutation = random.choice(mutations)

        # Add mutation
        mut_copy = dict(selected_mutation)
        mut_copy["type"] = "mutation"
        self._selected_chaos_gifts.append(mut_copy)

        self._sync_chaos_checkboxes()
        self._update_chaos_display(parent_tag)

        # Show result
        if dpg.does_item_exist("chaos_selected_display"):
            name = selected_mutation.get("name", "Unknown")
            dpg.set_value("chaos_selected_display",
                          f"Rolled {roll}: {name}! {selected_mutation.get('description', '')}")

    def _clear_chaos_gifts(self, parent_tag: str):
        """Clear all selected Chaos gifts."""
        self._selected_chaos_gifts = []
        self._sync_chaos_checkboxes()
        self._update_chaos_display(parent_tag)

    def _update_chaos_display(self, parent_tag: str):
        """Update the Chaos gifts display."""
        if not self._selected_chaos_gifts:
            display_text = "(none)"
            total_pts = 0
        else:
            names = [f"{g.get('name')} ({g.get('points', 0)}pts)" for g in self._selected_chaos_gifts]
            display_text = ", ".join(names)
            total_pts = sum(g.get("points", 0) for g in self._selected_chaos_gifts)

        if dpg.does_item_exist("chaos_selected_display"):
            dpg.set_value("chaos_selected_display", display_text)

        if dpg.does_item_exist("chaos_total_pts"):
            dpg.set_value("chaos_total_pts", f"{total_pts} pts")

        # Also update the main wargear display to show Chaos gifts
        if dpg.does_item_exist(f"{parent_tag}_wargear_display"):
            all_items = []
            for w in self._selected_wargear:
                all_items.append(f"{w.get('name')} ({w.get('points', 0)}pts)")
            for g in self._selected_chaos_gifts:
                all_items.append(f"[{g.get('type', 'gift').upper()}] {g.get('name')} ({g.get('points', 0)}pts)")

            if all_items:
                dpg.set_value(f"{parent_tag}_wargear_display", ", ".join(all_items))
            else:
                dpg.set_value(f"{parent_tag}_wargear_display", "(none)")

    # -------------------------------------------------------------------------
    # Roster Management Methods
    # -------------------------------------------------------------------------

    def _show_load_detachment_dialog(self):
        """Show dialog to load a pre-built test detachment."""
        tag = f"load_detachment_{id(self)}"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        detachments = load_test_detachments()

        with dpg.window(
            label="Load Test Detachment",
            modal=True,
            tag=tag,
            width=500,
            height=400,
            pos=style.centered_pos(500, 400),
        ):
            dpg.add_text("Select a pre-built detachment to load.")
            dpg.add_text("This will replace the current roster.", color=(200, 150, 100))

            dpg.add_spacer(height=10)

            if not detachments:
                dpg.add_text("No detachments found.", color=(150, 150, 150))
            else:
                self._detachments = detachments

                with dpg.child_window(height=280, border=True):
                    for i, det in enumerate(detachments):
                        name = det.get("name", "Unknown")
                        faction = det.get("faction", "Unknown")
                        points = det.get("points", 0)
                        desc = det.get("description", "")
                        units = det.get("units", [])

                        with dpg.group():
                            dpg.add_selectable(
                                label=f"{name} ({faction}) - {points} pts",
                                callback=lambda s, a, u: self._select_detachment(u),
                                user_data=i,
                                tag=f"det_select_{id(self)}_{i}",
                            )
                            dpg.add_text(f"  {desc}", color=(150, 150, 150), wrap=450)
                            dpg.add_text(f"  Units: {len(units)}", color=(120, 150, 120))
                            dpg.add_spacer(height=5)

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Load",
                    callback=lambda: self._do_load_detachment(tag),
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(tag),
                    width=100,
                )

        self._selected_detachment_idx = 0 if detachments else -1

    def _select_detachment(self, idx: int):
        """Handle detachment selection."""
        self._selected_detachment_idx = idx

    def _do_load_detachment(self, dialog_tag: str):
        """Load the selected detachment into the roster."""
        idx = getattr(self, '_selected_detachment_idx', None)

        if not hasattr(self, '_detachments'):
            return
        if idx is None or idx < 0:
            return

        det = self._detachments[idx]

        # Get the appropriate roster
        roster = (
            self.coordinator.player_roster
            if self.is_friendly
            else self.coordinator.ai_roster
        )

        # Clear existing units
        roster.units = []

        # Add units from detachment
        manager = RosterManager()
        for unit_data in det.get("units", []):
            # Map category to slot type
            category = unit_data.get("category", "Troops").lower().replace(" ", "_")
            slot_map = {
                "hq": SlotType.HQ,
                "troops": SlotType.TROOPS,
                "elites": SlotType.ELITES,
                "fast_attack": SlotType.FAST_ATTACK,
                "heavy_support": SlotType.HEAVY_SUPPORT,
            }
            slot_type = slot_map.get(category, SlotType.TROOPS)

            # Create unit
            unit = manager.create_custom_unit(
                name=unit_data.get("name", "Unknown"),
                slot_type=slot_type,
                stats=unit_data.get("stats", {}),
                weapons=[{"name": w} for w in unit_data.get("weapons", [])],
                wargear=unit_data.get("wargear", []),
                abilities=unit_data.get("special_rules", []),
                wounds=unit_data.get("stats", {}).get("W", 1),
                models=unit_data.get("models", 1),
                points=unit_data.get("points", 0),
            )
            roster.add_unit(unit)

        dpg.delete_item(dialog_tag)
        self.refresh()

    def _validate_roster(self):
        """Validate the roster against force organization rules."""
        roster = (
            self.coordinator.player_roster
            if self.is_friendly
            else self.coordinator.ai_roster
        )

        errors = validate_force_org(roster)

        tag = f"validate_result_{id(self)}"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        with dpg.window(
            label="Force Organization Check",
            modal=True,
            tag=tag,
            width=400,
            height=250,
            pos=style.centered_pos(400, 250),
        ):
            if not errors:
                dpg.add_text("Army is VALID!", color=(100, 200, 100))
                dpg.add_text("Force organization requirements met.")
            else:
                dpg.add_text("Army has ISSUES:", color=(200, 100, 100))
                dpg.add_spacer(height=5)
                for err in errors:
                    dpg.add_text(f"  - {err}", color=(200, 150, 100))

            dpg.add_spacer(height=10)

            # Show current breakdown
            dpg.add_separator()
            dpg.add_text("Current Force Organization:", color=(150, 150, 150))

            category_counts = {}
            for unit in roster.units:
                slot_val = unit.slot_type.value if hasattr(unit.slot_type, 'value') else str(unit.slot_type)
                category_map = {
                    "hq": "HQ",
                    "troops": "Troops",
                    "elites": "Elites",
                    "fast_attack": "Fast Attack",
                    "heavy_support": "Heavy Support",
                }
                category = category_map.get(slot_val.lower(), "Other")
                category_counts[category] = category_counts.get(category, 0) + 1

            for cat in ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support"]:
                count = category_counts.get(cat, 0)
                limits = FORCE_ORG_2E.get(cat, {"min": 0, "max": 3})
                color = (100, 200, 100) if limits["min"] <= count <= limits["max"] else (200, 100, 100)
                dpg.add_text(f"  {cat}: {count} (need {limits['min']}-{limits['max']})", color=color)

            dpg.add_spacer(height=10)

            dpg.add_button(
                label="OK",
                callback=lambda: dpg.delete_item(tag),
                width=100,
            )

    def _show_save_roster_dialog(self):
        """Show dialog to save the current roster."""
        tag = f"save_roster_{id(self)}"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        with dpg.window(
            label="Save Roster",
            modal=True,
            tag=tag,
            width=400,
            height=180,
            pos=style.centered_pos(400, 180),
        ):
            dpg.add_text("Save this roster for future use.")

            dpg.add_spacer(height=10)

            dpg.add_text("Roster Name:")
            dpg.add_input_text(
                hint="e.g., Space Marines 500pts",
                tag=f"{tag}_name",
                width=-1,
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    callback=lambda: self._do_save_roster(tag),
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(tag),
                    width=100,
                )

    def _do_save_roster(self, dialog_tag: str):
        """Execute roster save."""
        name = dpg.get_value(f"{dialog_tag}_name")
        if not name:
            name = f"roster_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        roster = (
            self.coordinator.player_roster
            if self.is_friendly
            else self.coordinator.ai_roster
        )

        # Create save directory
        save_dir = Path.home() / ".oracle" / "rosters"
        save_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
        filepath = save_dir / f"{safe_name}.json"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(roster.to_dict(), f, indent=2, ensure_ascii=False)

            dpg.delete_item(dialog_tag)
            # Could add a success message here
        except OSError as e:
            print(f"Failed to save roster: {e}")

    def _show_load_roster_dialog(self):
        """Show dialog to load a saved roster."""
        tag = f"load_roster_{id(self)}"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        # Get saved rosters
        save_dir = Path.home() / ".oracle" / "rosters"
        saved_rosters = []
        if save_dir.exists():
            for f in save_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        saved_rosters.append({
                            "file": f,
                            "name": data.get("name", f.stem),
                            "faction": data.get("faction", ""),
                            "units": len(data.get("units", [])),
                            "points": sum(u.get("points_cost", 0) for u in data.get("units", [])),
                        })
                except (json.JSONDecodeError, OSError):
                    pass

        with dpg.window(
            label="Load Roster",
            modal=True,
            tag=tag,
            width=500,
            height=400,
            pos=style.centered_pos(500, 400),
        ):
            dpg.add_text("Select a saved roster to load.")
            dpg.add_text("This will replace the current roster.", color=(200, 150, 100))

            dpg.add_spacer(height=10)

            if not saved_rosters:
                dpg.add_text("No saved rosters found.", color=(150, 150, 150))
            else:
                self._saved_rosters = saved_rosters

                with dpg.child_window(height=250, border=True):
                    for i, ros in enumerate(saved_rosters):
                        with dpg.group(horizontal=True):
                            dpg.add_selectable(
                                label=f"{ros['name']} - {ros['units']} units, {ros['points']} pts",
                                callback=lambda s, a, u: self._select_roster(u),
                                user_data=i,
                                width=350,
                                tag=f"ros_select_{id(self)}_{i}",
                            )
                            dpg.add_button(
                                label="Del",
                                callback=lambda s, a, u: self._delete_roster(u, tag),
                                user_data=ros['file'],
                                width=40,
                                small=True,
                            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Load",
                    callback=lambda: self._do_load_roster(tag),
                    width=100,
                    enabled=bool(saved_rosters),
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(tag),
                    width=100,
                )

        self._selected_roster_idx = 0 if saved_rosters else -1

    def _select_roster(self, idx: int):
        """Handle roster selection."""
        self._selected_roster_idx = idx

    def _delete_roster(self, filepath: Path, dialog_tag: str):
        """Delete a saved roster file."""
        try:
            filepath.unlink()
            dpg.delete_item(dialog_tag)
            self._show_load_roster_dialog()
        except OSError as e:
            print(f"Failed to delete roster: {e}")

    def _do_load_roster(self, dialog_tag: str):
        """Load the selected roster."""
        idx = getattr(self, '_selected_roster_idx', None)
        if not hasattr(self, '_saved_rosters') or idx is None or idx < 0:
            return

        ros = self._saved_rosters[idx]
        filepath = ros['file']

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            loaded_roster = Roster.from_dict(data)

            # Set as appropriate roster
            if self.is_friendly:
                self.coordinator.player_roster = loaded_roster
            else:
                self.coordinator.ai_roster = loaded_roster

            dpg.delete_item(dialog_tag)
            self.refresh()

        except (json.JSONDecodeError, OSError, KeyError) as e:
            print(f"Failed to load roster: {e}")


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

        dpg.set_value(f"{self._tag}_turn", str(state.current_turn))
        dpg.set_value(f"{self._tag}_phase", phase_display(state.current_phase))

        if dpg.does_item_exist(f"{self._tag}_system"):
            dpg.set_value(f"{self._tag}_system", self.coordinator.rules.system_name)

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
            pos=style.centered_pos(500, 400),
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
            pos=style.centered_pos(500, 450),
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

    # Battle phases -> guide phase names they may appear under in the TOML.
    _PHASE_SYNONYMS = {
        "movement": ("movement", "activation"),
        "shooting": ("shooting", "activation"),
        "melee": ("melee", "hand-to-hand", "combat", "activation"),
        "morale": ("morale", "rally", "morale phase"),
    }

    def refresh(self):
        """Refresh to match current game state."""
        # Derive a guide phase name from the battle phase, e.g.
        # PLAYER_SHOOTING / AI_SHOOTING -> "shooting".
        phase_key = self.coordinator.state.current_phase.name.lower()
        for prefix in ("player_", "ai_"):
            if phase_key.startswith(prefix):
                phase_key = phase_key[len(prefix):]

        candidates = self._PHASE_SYNONYMS.get(phase_key, (phase_key,))

        system_key = self._get_system_key()
        system_data = self._guides.get(system_key, {})
        phases = system_data.get("phases", [])

        for i, phase in enumerate(phases):
            if phase.get("name", "").lower() in candidates:
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
        self.commander = generate_commander("methodical_grinder")

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
        style.apply_style()
        dpg.create_viewport(title="Oracle — Wargame", width=1600, height=900)

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
                with dpg.child_window(width=300, height=-1, border=True, tag="left_sidebar"):
                    # Battle state
                    self._state_panel = BattleStatePanel(
                        "left_sidebar", self.coordinator
                    )

                    dpg.add_separator()

                    # Friendly forces
                    self._friendly_panel = ForcePanel(
                        "left_sidebar", self.coordinator, is_friendly=True
                    )

                    dpg.add_separator()

                    # Enemy forces
                    self._enemy_panel = ForcePanel(
                        "left_sidebar", self.coordinator, is_friendly=False
                    )

                # Center: Battle chat
                with dpg.child_window(width=-350, height=-1, border=True, tag="center_panel"):
                    self._chat_panel = BattleChatPanel(
                        "center_panel",
                        self.coordinator,
                        self.narrator,
                    )

                # Right sidebar: AI controls and Phase Guide
                with dpg.child_window(width=340, height=-1, border=True, tag="right_sidebar"):
                    # Create a tabbed view for AI and Phase Guide
                    with dpg.tab_bar(tag="right_sidebar_tabs"):
                        with dpg.tab(label="AI Controls", tag="ai_controls_tab"):
                            self._build_ai_controls("ai_controls_tab")

                        with dpg.tab(label="Phase Guide", tag="phase_guide_tab"):
                            self._phase_guide = PhaseGuidePanel(
                                "phase_guide_tab",
                                self.coordinator,
                            )

        # Battle actions (attacks, AI turns, phase changes) refresh all panels.
        self._chat_panel.on_state_change = self._refresh_all

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
                wrap=300,
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
        # Update displayed description
        for d in Doctrine:
            if d.display == app_data:
                dpg.set_value("ai_doctrine_desc", d.description)
                break

    def _on_aggression_change(self, sender, app_data, user_data):
        """Handle aggression change."""
        # Aggression setting stored for future use
        pass

    def _on_dice_mode_change(self, sender, app_data, user_data):
        """Handle dice mode change."""
        if app_data == "Auto Roll":
            self.coordinator.rules.dice.mode = RollingMode.AUTO
        else:
            self.coordinator.rules.dice.mode = RollingMode.MANUAL

    def _ai_analyze(self):
        """Have AI analyze the situation."""
        # Get threat assessments from opponent AI
        threats = self.coordinator.opponent.assess_threats(self.coordinator.player_roster)

        if threats:
            msg = "AI Analysis:\n"
            for t in threats:
                msg += f"  [{t.priority_level}] {t.unit.name}: {', '.join(t.reasons)}\n"
        else:
            msg = "No significant threats detected."

        self._chat_panel.add_message(BattleMessage(msg, "ai"))

    def _ai_decide(self):
        """Have AI make a tactical decision."""
        # Use the opponent to generate a decision narrative
        commander = self.coordinator.commander
        if commander:
            msg = f"Commander {commander.name} assesses the battlefield..."
        else:
            msg = "The enemy commander assesses the battlefield..."

        self._chat_panel.add_message(BattleMessage(msg, "ai"))

    def _new_battle(self):
        """Start a new battle."""
        intro = self.coordinator.reset_battle(
            Roster(name="Your Army"),
            Roster(name="Enemy Army"),
        )
        self._refresh_all()

        self._chat_panel.add_message(BattleMessage(
            "New battle started. Add units to begin.",
            "system",
        ))
        # The commander's opening address.
        if intro:
            self._chat_panel.add_message(BattleMessage(intro, "ai", "narrative"))

    def _save_battle(self):
        """Show save battle dialog."""
        if dpg.does_item_exist("save_battle_dialog"):
            dpg.delete_item("save_battle_dialog")

        with dpg.window(
            label="Save Battle Setup",
            modal=True,
            tag="save_battle_dialog",
            width=400,
            height=200,
            pos=style.centered_pos(400, 200),
        ):
            dpg.add_text("Save current battle setup for later use.")
            dpg.add_text("Both armies and game system will be saved.", color=(150, 150, 150))

            dpg.add_spacer(height=10)

            dpg.add_text("Battle Name:")
            dpg.add_input_text(
                hint="e.g., Space Marines vs Orks",
                tag="save_battle_name",
                width=-1,
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    callback=self._do_save_battle,
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("save_battle_dialog"),
                    width=100,
                )

    def _do_save_battle(self):
        """Execute the battle save."""
        name = dpg.get_value("save_battle_name")
        if not name:
            name = f"battle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create save directory
        save_dir = Path.home() / ".oracle" / "battles"
        save_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
        filepath = save_dir / f"{safe_name}.json"

        # Build save data
        save_data = {
            "name": name,
            "game_system": self.rules.system_id,
            "commander_archetype": self.commander.archetype.name if self.commander else "methodical_grinder",
            "player": self.coordinator.player_roster.to_dict() if self.coordinator.player_roster else None,
            "enemy": self.coordinator.ai_roster.to_dict() if self.coordinator.ai_roster else None,
            "battle_state": {
                "turn": self.coordinator.state.current_turn,
                "phase": self.coordinator.state.current_phase.name,
            },
            "saved_at": datetime.now().isoformat(),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            dpg.delete_item("save_battle_dialog")

            self._chat_panel.add_message(BattleMessage(
                f"Battle saved: {name}",
                "system",
            ))
        except OSError as e:
            self._chat_panel.add_message(BattleMessage(
                f"Failed to save battle: {e}",
                "system",
            ))

    def _load_battle(self):
        """Show load battle dialog."""
        if dpg.does_item_exist("load_battle_dialog"):
            dpg.delete_item("load_battle_dialog")

        # Get saved battles
        save_dir = Path.home() / ".oracle" / "battles"
        saved_battles = []
        if save_dir.exists():
            for f in save_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        saved_battles.append({
                            "file": f,
                            "name": data.get("name", f.stem),
                            "system": data.get("game_system", "unknown"),
                            "saved_at": data.get("saved_at", ""),
                        })
                except (json.JSONDecodeError, OSError):
                    pass

        with dpg.window(
            label="Load Battle Setup",
            modal=True,
            tag="load_battle_dialog",
            width=500,
            height=400,
            pos=style.centered_pos(500, 400),
        ):
            dpg.add_text("Select a saved battle to load.")
            dpg.add_text("This will replace both armies.", color=(200, 150, 100))

            dpg.add_spacer(height=10)

            if not saved_battles:
                dpg.add_text("No saved battles found.", color=(150, 150, 150))
            else:
                # Store battle list for reference
                self._saved_battles = saved_battles

                with dpg.child_window(height=250, border=True):
                    for i, battle in enumerate(saved_battles):
                        with dpg.group(horizontal=True):
                            dpg.add_selectable(
                                label=f"{battle['name']} ({battle['system']})",
                                callback=lambda s, a, u: self._select_battle(u),
                                user_data=i,
                                width=350,
                                tag=f"battle_select_{i}",
                            )
                            dpg.add_button(
                                label="Delete",
                                callback=lambda s, a, u: self._delete_battle(u),
                                user_data=battle['file'],
                                width=60,
                                small=True,
                            )

                dpg.add_spacer(height=5)
                dpg.add_text("", tag="load_battle_selected", color=(100, 200, 100))

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Load",
                    callback=self._do_load_battle,
                    width=100,
                    enabled=bool(saved_battles),
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("load_battle_dialog"),
                    width=100,
                )

        self._selected_battle_idx = 0 if saved_battles else -1

    def _select_battle(self, idx: int):
        """Handle battle selection."""
        self._selected_battle_idx = idx
        if hasattr(self, '_saved_battles') and 0 <= idx < len(self._saved_battles):
            battle = self._saved_battles[idx]
            dpg.set_value("load_battle_selected", f"Selected: {battle['name']}")

    def _delete_battle(self, filepath: Path):
        """Delete a saved battle file."""
        try:
            filepath.unlink()
            self._chat_panel.add_message(BattleMessage(
                f"Deleted battle: {filepath.stem}",
                "system",
            ))
            # Refresh dialog
            dpg.delete_item("load_battle_dialog")
            self._load_battle()
        except OSError as e:
            self._chat_panel.add_message(BattleMessage(
                f"Failed to delete: {e}",
                "system",
            ))

    def _do_load_battle(self):
        """Execute the battle load."""
        if not hasattr(self, '_saved_battles') or self._selected_battle_idx < 0:
            return

        if self._selected_battle_idx >= len(self._saved_battles):
            return

        battle = self._saved_battles[self._selected_battle_idx]
        filepath = battle['file']

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Change game system if needed
            system_id = data.get("game_system", "oldhammer_2e")
            if system_id != self.rules.system_id:
                self._change_system(system_id)

            # Change commander if specified
            commander_arch = data.get("commander_archetype", "methodical_grinder")
            self._change_commander(commander_arch)

            # Load rosters
            if data.get("player"):
                self.coordinator.player_roster = Roster.from_dict(data["player"])
            else:
                self.coordinator.player_roster = Roster(name="Your Army")

            if data.get("enemy"):
                self.coordinator.ai_roster = Roster.from_dict(data["enemy"])
            else:
                self.coordinator.ai_roster = Roster(name="Enemy Army")

            # Restore battle state
            if data.get("battle_state"):
                self.coordinator.state.current_turn = data["battle_state"].get("turn", 1)
                phase_str = data["battle_state"].get("phase", "PLAYER_MOVEMENT")
                restored = BattlePhase.PLAYER_MOVEMENT
                for phase in BattlePhase:
                    # Match by name (new saves) or raw value (older saves).
                    if phase.name == phase_str or phase.value == phase_str:
                        restored = phase
                        break
                self.coordinator.state.current_phase = restored

            dpg.delete_item("load_battle_dialog")

            self._refresh_all()

            self._chat_panel.add_message(BattleMessage(
                f"Loaded battle: {data.get('name', 'Unknown')}",
                "system",
            ))

        except (json.JSONDecodeError, OSError, KeyError) as e:
            self._chat_panel.add_message(BattleMessage(
                f"Failed to load battle: {e}",
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
        self.coordinator.set_commander(self.commander)
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
