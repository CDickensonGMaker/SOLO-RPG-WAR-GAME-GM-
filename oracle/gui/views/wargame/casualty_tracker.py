"""
Casualty Tracker - Wound allocation and model removal.

Provides:
- Wound allocation dialogs
- Model removal tracking
- Overkill wound handling
- Morale check prompts at casualty thresholds
"""

from typing import Callable, Optional
import dearpygui.dearpygui as dpg

from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.roster import RosterUnit, UnitStatus


# Callback types
MoraleCheckCallback = Callable[[RosterUnit, int], None]  # (unit, casualties_percent)
CasualtyCallback = Callable[[RosterUnit, str], None]  # (unit, result_message)


class CasualtyTracker:
    """
    Tracks and manages casualties during battle.

    Provides dialogs for allocating wounds and removing models,
    with automatic morale check prompts.
    """

    def __init__(
        self,
        on_morale_check: Optional[MoraleCheckCallback] = None,
        on_casualty: Optional[CasualtyCallback] = None,
    ):
        """
        Create the casualty tracker.

        Args:
            on_morale_check: Callback when morale check is needed
            on_casualty: Callback when casualties are applied
        """
        self._on_morale_check = on_morale_check
        self._on_casualty = on_casualty

        self._battle = get_battle_roster()

        # Track casualty thresholds for morale
        self._morale_thresholds = [25, 50, 75]  # Percent casualties
        self._morale_checked: dict[str, set[int]] = {}  # unit_id -> checked thresholds

    def show_wound_dialog(
        self,
        unit: RosterUnit,
        is_friendly: bool,
        parent_window: Optional[str] = None
    ):
        """
        Show a dialog for allocating wounds to a unit.

        Args:
            unit: The unit to damage
            is_friendly: Whether this is a friendly unit
            parent_window: Parent window for positioning
        """
        dialog_tag = f"wound_dialog_{id(unit)}"

        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        # Calculate current health info
        total_wounds = unit.wounds_max * unit.models_max
        current_wounds = (unit.wounds_max * (unit.models_current - 1)) + unit.wounds_current
        casualties_pct = int((1 - (current_wounds / total_wounds)) * 100)

        with dpg.window(
            label=f"Apply Wounds: {unit.name}",
            modal=True,
            tag=dialog_tag,
            width=350,
            height=300,
            pos=[250, 150],
            no_close=False,
        ):
            # Unit status
            dpg.add_text(f"Unit: {unit.name}", color=(200, 180, 140))
            dpg.add_text(
                f"Status: {unit.status.value.title()}",
                color=self._status_color(unit.status)
            )

            dpg.add_spacer(height=5)

            # Current state
            if unit.models_max > 1:
                dpg.add_text(f"Models: {unit.models_current}/{unit.models_max}")
            dpg.add_text(f"Wounds (current model): {unit.wounds_current}/{unit.wounds_max}")
            dpg.add_text(f"Casualties: {casualties_pct}%", color=(180, 140, 100))

            dpg.add_spacer(height=10)

            # Wound input
            dpg.add_text("Wounds to Apply:")
            dpg.add_input_int(
                default_value=1,
                min_value=1,
                max_value=50,
                tag=f"{dialog_tag}_wounds",
                width=100,
            )

            # Quick buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="1",
                    callback=lambda: dpg.set_value(f"{dialog_tag}_wounds", 1),
                    width=40,
                )
                dpg.add_button(
                    label="D3",
                    callback=lambda: self._roll_wounds(dialog_tag, "d3"),
                    width=40,
                )
                dpg.add_button(
                    label="D6",
                    callback=lambda: self._roll_wounds(dialog_tag, "d6"),
                    width=40,
                )
                dpg.add_button(
                    label="2D6",
                    callback=lambda: self._roll_wounds(dialog_tag, "2d6"),
                    width=50,
                )

            dpg.add_spacer(height=10)

            # Apply button
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply Wounds",
                    callback=lambda: self._apply_wounds(
                        unit, is_friendly, dialog_tag
                    ),
                    width=120,
                )
                dpg.add_button(
                    label="Destroy Unit",
                    callback=lambda: self._destroy_unit(unit, is_friendly, dialog_tag),
                    width=100,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(dialog_tag),
                    width=80,
                )

    def _roll_wounds(self, dialog_tag: str, dice: str):
        """Roll dice and set wound value."""
        import random
        if dice == "d3":
            value = random.randint(1, 3)
        elif dice == "d6":
            value = random.randint(1, 6)
        elif dice == "2d6":
            value = random.randint(1, 6) + random.randint(1, 6)
        else:
            value = 1

        dpg.set_value(f"{dialog_tag}_wounds", value)

    def _apply_wounds(self, unit: RosterUnit, is_friendly: bool, dialog_tag: str):
        """Apply wounds and check for morale."""
        wounds = dpg.get_value(f"{dialog_tag}_wounds")

        # Apply damage through battle model
        result = self._battle.damage_unit(
            unit.id,
            wounds,
            from_friendly=is_friendly
        )

        # Check for morale threshold
        self._check_morale_threshold(unit)

        # Callback
        if self._on_casualty:
            self._on_casualty(unit, result)

        dpg.delete_item(dialog_tag)

    def _destroy_unit(self, unit: RosterUnit, is_friendly: bool, dialog_tag: str):
        """Immediately destroy a unit."""
        self._battle.set_unit_status(
            unit.id,
            UnitStatus.DESTROYED,
            from_friendly=is_friendly
        )

        if self._on_casualty:
            self._on_casualty(unit, f"{unit.name} DESTROYED!")

        dpg.delete_item(dialog_tag)

    def _check_morale_threshold(self, unit: RosterUnit):
        """Check if unit has crossed a morale threshold."""
        if not unit.is_active:
            return

        # Calculate casualties percentage
        total_wounds = unit.wounds_max * unit.models_max
        current_wounds = (unit.wounds_max * (unit.models_current - 1)) + unit.wounds_current
        casualties_pct = int((1 - (current_wounds / total_wounds)) * 100)

        # Get previously checked thresholds
        if unit.id not in self._morale_checked:
            self._morale_checked[unit.id] = set()
        checked = self._morale_checked[unit.id]

        # Check each threshold
        for threshold in self._morale_thresholds:
            if casualties_pct >= threshold and threshold not in checked:
                checked.add(threshold)
                if self._on_morale_check:
                    self._on_morale_check(unit, casualties_pct)
                break

    def _status_color(self, status: UnitStatus) -> tuple:
        """Get color for status display."""
        colors = {
            UnitStatus.FRESH: (100, 180, 100),
            UnitStatus.ENGAGED: (180, 180, 100),
            UnitStatus.DAMAGED: (200, 160, 100),
            UnitStatus.WOUNDED: (200, 120, 100),
            UnitStatus.ROUTING: (200, 100, 100),
            UnitStatus.DESTROYED: (100, 100, 100),
        }
        return colors.get(status, (150, 150, 150))

    def show_heal_dialog(self, unit: RosterUnit, is_friendly: bool):
        """Show dialog for healing/restoring a unit."""
        dialog_tag = f"heal_dialog_{id(unit)}"

        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        with dpg.window(
            label=f"Restore: {unit.name}",
            modal=True,
            tag=dialog_tag,
            width=300,
            height=200,
            pos=[250, 150],
        ):
            dpg.add_text(f"Unit: {unit.name}", color=(200, 180, 140))

            # Current state
            if unit.models_max > 1:
                dpg.add_text(f"Models: {unit.models_current}/{unit.models_max}")
            dpg.add_text(f"Wounds: {unit.wounds_current}/{unit.wounds_max}")

            dpg.add_spacer(height=10)

            # Heal wounds
            dpg.add_text("Heal Wounds:")
            dpg.add_input_int(
                default_value=1,
                min_value=1,
                max_value=unit.wounds_max,
                tag=f"{dialog_tag}_heal",
                width=100,
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Heal",
                    callback=lambda: self._heal_unit(unit, is_friendly, dialog_tag),
                    width=80,
                )
                if unit.models_current < unit.models_max:
                    dpg.add_button(
                        label="Restore Model",
                        callback=lambda: self._restore_model(unit, is_friendly, dialog_tag),
                        width=120,
                    )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(dialog_tag),
                    width=80,
                )

    def _heal_unit(self, unit: RosterUnit, is_friendly: bool, dialog_tag: str):
        """Apply healing."""
        wounds = dpg.get_value(f"{dialog_tag}_heal")
        result = self._battle.heal_unit(unit.id, wounds, from_friendly=is_friendly)

        if self._on_casualty:
            self._on_casualty(unit, result)

        dpg.delete_item(dialog_tag)

    def _restore_model(self, unit: RosterUnit, is_friendly: bool, dialog_tag: str):
        """Restore a destroyed model."""
        result = self._battle.restore_model(unit.id, from_friendly=is_friendly)

        if self._on_casualty:
            self._on_casualty(unit, result)

        dpg.delete_item(dialog_tag)

    def show_status_dialog(self, unit: RosterUnit, is_friendly: bool):
        """Show dialog for manually setting unit status."""
        dialog_tag = f"status_dialog_{id(unit)}"

        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        statuses = [
            ("Fresh", UnitStatus.FRESH),
            ("Engaged", UnitStatus.ENGAGED),
            ("Damaged", UnitStatus.DAMAGED),
            ("Wounded", UnitStatus.WOUNDED),
            ("Routing", UnitStatus.ROUTING),
            ("Destroyed", UnitStatus.DESTROYED),
        ]

        with dpg.window(
            label=f"Set Status: {unit.name}",
            modal=True,
            tag=dialog_tag,
            width=250,
            height=220,
            pos=[250, 150],
        ):
            dpg.add_text(f"Current: {unit.status.value.title()}")
            dpg.add_spacer(height=10)

            dpg.add_text("Set Status:")
            for label, status in statuses:
                dpg.add_button(
                    label=label,
                    callback=lambda s=status: self._set_status(
                        unit, s, is_friendly, dialog_tag
                    ),
                    width=-1,
                )

    def _set_status(
        self,
        unit: RosterUnit,
        status: UnitStatus,
        is_friendly: bool,
        dialog_tag: str
    ):
        """Set unit status."""
        result = self._battle.set_unit_status(
            unit.id, status, from_friendly=is_friendly
        )

        if self._on_casualty:
            self._on_casualty(unit, result)

        dpg.delete_item(dialog_tag)

    def reset_morale_tracking(self):
        """Reset morale threshold tracking (e.g., for new battle)."""
        self._morale_checked.clear()


class QuickCasualtyButtons:
    """
    Quick casualty buttons that can be added to any panel.

    Provides +1/-1 wound and model buttons.
    """

    def __init__(
        self,
        parent: str,
        unit_getter: Callable[[], Optional[tuple[RosterUnit, bool]]],
        on_change: Optional[Callable] = None,
    ):
        """
        Create quick casualty buttons.

        Args:
            parent: Parent DearPyGui item tag
            unit_getter: Function that returns (unit, is_friendly) or None
            on_change: Callback when changes are made
        """
        self.parent = parent
        self._unit_getter = unit_getter
        self._on_change = on_change

        self._battle = get_battle_roster()
        self._build()

    def _build(self):
        """Build the quick buttons."""
        with dpg.group(parent=self.parent, horizontal=True):
            dpg.add_button(
                label="-1W",
                callback=self._damage_one,
                width=50,
            )
            dpg.add_button(
                label="+1W",
                callback=self._heal_one,
                width=50,
            )
            dpg.add_button(
                label="-Model",
                callback=self._remove_model,
                width=60,
            )
            dpg.add_button(
                label="+Model",
                callback=self._restore_model,
                width=60,
            )

    def _damage_one(self):
        """Apply 1 wound."""
        result = self._unit_getter()
        if result:
            unit, is_friendly = result
            self._battle.damage_unit(unit.id, 1, from_friendly=is_friendly)
            if self._on_change:
                self._on_change()

    def _heal_one(self):
        """Heal 1 wound."""
        result = self._unit_getter()
        if result:
            unit, is_friendly = result
            self._battle.heal_unit(unit.id, 1, from_friendly=is_friendly)
            if self._on_change:
                self._on_change()

    def _remove_model(self):
        """Remove a model (full damage)."""
        result = self._unit_getter()
        if result:
            unit, is_friendly = result
            # Damage equal to current wounds to kill one model
            self._battle.damage_unit(unit.id, unit.wounds_current, from_friendly=is_friendly)
            if self._on_change:
                self._on_change()

    def _restore_model(self):
        """Restore a model."""
        result = self._unit_getter()
        if result:
            unit, is_friendly = result
            self._battle.restore_model(unit.id, from_friendly=is_friendly)
            if self._on_change:
                self._on_change()
