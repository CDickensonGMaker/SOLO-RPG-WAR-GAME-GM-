"""
Force Display - Battle view showing both armies.

Provides:
- Your Army panel (left)
- Enemy Army panel (right)
- Model counts with visual indicators
- Wound tracking per unit
- Status indicators (Fresh/Damaged/Routing/Destroyed)
- Morale indicators
"""

from typing import Callable, Optional
import dearpygui.dearpygui as dpg

from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.roster import RosterUnit, UnitStatus


# Callback types
UnitClickCallback = Callable[[RosterUnit, bool], None]  # (unit, is_friendly)


class ForceDisplayPanel:
    """
    Dual-panel display showing both armies during battle.

    Left panel shows friendly forces, right panel shows enemy forces.
    Each unit displays status, wounds, and model count.
    """

    def __init__(
        self,
        parent: str,
        on_unit_click: Optional[UnitClickCallback] = None,
        panel_width: int = 300,
    ):
        """
        Create the force display panel.

        Args:
            parent: Parent DearPyGui item tag
            on_unit_click: Callback when a unit is clicked
            panel_width: Width of each force panel
        """
        self.parent = parent
        self._on_unit_click = on_unit_click
        self.panel_width = panel_width

        self._battle = get_battle_roster()

        # UI tags
        self._tag = f"force_display_{id(self)}"
        self._friendly_list_tag = f"{self._tag}_friendly"
        self._enemy_list_tag = f"{self._tag}_enemy"
        self._friendly_summary_tag = f"{self._tag}_friendly_sum"
        self._enemy_summary_tag = f"{self._tag}_enemy_sum"

        # Register as observer
        self._battle.add_roster_observer(self._on_roster_changed)

        self._build()

    def _build(self):
        """Build the UI components."""
        with dpg.group(parent=self.parent, horizontal=True, tag=f"{self._tag}_root"):
            # Left: Friendly Forces
            with dpg.child_window(width=self.panel_width, height=-1, border=True):
                dpg.add_text("Your Army", color=(100, 180, 100))
                dpg.add_separator()

                # Summary
                dpg.add_text(
                    "0 units | 0 pts",
                    tag=self._friendly_summary_tag,
                    color=(150, 150, 150)
                )

                dpg.add_spacer(height=5)

                # Unit list
                with dpg.child_window(
                    height=-1,
                    border=False,
                    tag=self._friendly_list_tag
                ):
                    dpg.add_text("No units", color=(100, 100, 100))

            dpg.add_spacer(width=10)

            # Right: Enemy Forces
            with dpg.child_window(width=self.panel_width, height=-1, border=True):
                dpg.add_text("Enemy Army", color=(180, 100, 100))
                dpg.add_separator()

                # Summary
                dpg.add_text(
                    "0 units | 0 pts",
                    tag=self._enemy_summary_tag,
                    color=(150, 150, 150)
                )

                dpg.add_spacer(height=5)

                # Unit list
                with dpg.child_window(
                    height=-1,
                    border=False,
                    tag=self._enemy_list_tag
                ):
                    dpg.add_text("No units", color=(100, 100, 100))

    def _on_roster_changed(self, model: BattleRosterModel):
        """Handle roster changes."""
        self.refresh()

    def refresh(self):
        """Refresh both force displays."""
        self._refresh_force_list(True)
        self._refresh_force_list(False)

    def _refresh_force_list(self, is_friendly: bool):
        """Refresh one force list."""
        list_tag = self._friendly_list_tag if is_friendly else self._enemy_list_tag
        summary_tag = self._friendly_summary_tag if is_friendly else self._enemy_summary_tag

        roster = self._battle.friendly_roster if is_friendly else self._battle.enemy_roster

        if dpg.does_item_exist(list_tag):
            dpg.delete_item(list_tag, children_only=True)

        with dpg.group(parent=list_tag):
            if not roster or not roster.units:
                dpg.add_text("No units", color=(100, 100, 100))
                dpg.set_value(summary_tag, "0 units | 0 pts")
                return

            # Summary
            active = len(roster.active_units)
            destroyed = len(roster.destroyed_units)
            total = len(roster.units)
            points = roster.points_all

            summary_text = f"{active}/{total} active | {points} pts"
            if destroyed > 0:
                summary_text += f" | {destroyed} destroyed"
            dpg.set_value(summary_tag, summary_text)

            # Units grouped by status
            fresh_units = roster.by_status(UnitStatus.FRESH)
            engaged_units = roster.by_status(UnitStatus.ENGAGED)
            damaged_units = roster.by_status(UnitStatus.DAMAGED) + roster.by_status(UnitStatus.WOUNDED)
            routing_units = roster.by_status(UnitStatus.ROUTING)
            destroyed_units = roster.destroyed_units

            # Render each group
            if fresh_units:
                self._render_unit_group("Fresh", fresh_units, is_friendly, (100, 180, 100))

            if engaged_units:
                self._render_unit_group("Engaged", engaged_units, is_friendly, (180, 180, 100))

            if damaged_units:
                self._render_unit_group("Damaged", damaged_units, is_friendly, (200, 140, 100))

            if routing_units:
                self._render_unit_group("Routing", routing_units, is_friendly, (200, 100, 100))

            if destroyed_units:
                with dpg.collapsing_header(label=f"Destroyed ({len(destroyed_units)})", default_open=False):
                    for unit in destroyed_units:
                        dpg.add_text(
                            f"  {unit.status.icon} {unit.name}",
                            color=(100, 100, 100)
                        )

    def _render_unit_group(
        self,
        group_name: str,
        units: list[RosterUnit],
        is_friendly: bool,
        header_color: tuple
    ):
        """Render a group of units."""
        dpg.add_text(f"[{group_name}]", color=header_color)

        for unit in units:
            self._render_unit_entry(unit, is_friendly)

        dpg.add_spacer(height=5)

    def _render_unit_entry(self, unit: RosterUnit, is_friendly: bool):
        """Render a single unit entry."""
        # Status icon and color
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
            # Clickable unit name
            dpg.add_selectable(
                label=f"{unit.status.icon} {unit.name}",
                callback=lambda s, a, u=unit, f=is_friendly: self._on_unit_clicked(u, f),
                width=180,
            )

            # Model/wound display
            if unit.models_max > 1:
                # Multi-model unit: show model count
                model_color = (100, 180, 100) if unit.models_current == unit.models_max else color
                dpg.add_text(
                    f"[{unit.models_current}/{unit.models_max}]",
                    color=model_color
                )
            elif unit.wounds_max > 1:
                # Single multi-wound model: show wounds
                self._render_wound_bar(unit)

    def _render_wound_bar(self, unit: RosterUnit):
        """Render a visual wound bar for multi-wound models."""
        wounds_current = unit.wounds_current
        wounds_max = unit.wounds_max

        # Create a simple text-based wound bar
        filled = int((wounds_current / wounds_max) * 5)
        bar = "[" + "=" * filled + "-" * (5 - filled) + "]"

        health_pct = wounds_current / wounds_max
        if health_pct > 0.75:
            color = (100, 180, 100)
        elif health_pct > 0.5:
            color = (180, 180, 100)
        elif health_pct > 0.25:
            color = (200, 140, 100)
        else:
            color = (200, 100, 100)

        dpg.add_text(f"{bar} {wounds_current}/{wounds_max}W", color=color)

    def _on_unit_clicked(self, unit: RosterUnit, is_friendly: bool):
        """Handle unit click."""
        if self._on_unit_click:
            self._on_unit_click(unit, is_friendly)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_selected_unit(self) -> Optional[RosterUnit]:
        """Get the most recently clicked unit."""
        # Could track this if needed
        return None

    def highlight_unit(self, unit_id: str):
        """Highlight a specific unit (for targeting, etc.)."""
        # Would need to track and update display
        pass

    def _rebuild_in_parent(self, new_parent: str):
        """Rebuild the panel content in a new parent (for pop-out support)."""
        # Delete existing root if it exists
        root_tag = f"{self._tag}_root"
        if dpg.does_item_exist(root_tag):
            dpg.delete_item(root_tag)

        # Update parent and rebuild
        self.parent = new_parent
        self._build()
        self.refresh()


class CompactForceDisplay:
    """
    Compact single-column force display for sidebar use.

    Shows both armies in a single vertical list.
    """

    def __init__(
        self,
        parent: str,
        on_unit_click: Optional[UnitClickCallback] = None,
    ):
        self.parent = parent
        self._on_unit_click = on_unit_click

        self._battle = get_battle_roster()
        self._tag = f"compact_force_{id(self)}"

        self._battle.add_roster_observer(self._on_roster_changed)
        self._build()

    def _build(self):
        """Build the compact display."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            # Friendly section
            with dpg.collapsing_header(label="Your Forces", default_open=True):
                with dpg.group(tag=f"{self._tag}_friendly"):
                    dpg.add_text("No units", color=(100, 100, 100))

            # Enemy section
            with dpg.collapsing_header(label="Enemy Forces", default_open=True):
                with dpg.group(tag=f"{self._tag}_enemy"):
                    dpg.add_text("No units", color=(100, 100, 100))

    def _on_roster_changed(self, model: BattleRosterModel):
        """Handle roster changes."""
        self.refresh()

    def refresh(self):
        """Refresh the display."""
        self._refresh_section(True)
        self._refresh_section(False)

    def _refresh_section(self, is_friendly: bool):
        """Refresh one section."""
        tag = f"{self._tag}_friendly" if is_friendly else f"{self._tag}_enemy"
        roster = self._battle.friendly_roster if is_friendly else self._battle.enemy_roster

        if dpg.does_item_exist(tag):
            dpg.delete_item(tag, children_only=True)

        with dpg.group(parent=tag):
            if not roster or not roster.units:
                dpg.add_text("No units", color=(100, 100, 100))
                return

            for unit in roster.units:
                # Compact format: icon name [models] wounds
                parts = [f"{unit.status.icon} {unit.name}"]

                if unit.models_max > 1:
                    parts.append(f"[{unit.models_current}/{unit.models_max}]")
                if unit.wounds_max > 1:
                    parts.append(f"W:{unit.wounds_current}/{unit.wounds_max}")

                color = (100, 180, 100) if unit.is_active else (100, 100, 100)

                dpg.add_selectable(
                    label=" ".join(parts),
                    callback=lambda s, a, u=unit, f=is_friendly: self._handle_click(u, f),
                    width=-1,
                )

    def _handle_click(self, unit: RosterUnit, is_friendly: bool):
        """Handle unit click."""
        if self._on_unit_click:
            self._on_unit_click(unit, is_friendly)
