"""
Army Builder - Two-pane army building interface.

Provides:
- Left pane: Available units filtered by slot type
- Right pane: Your army with added units
- Unit cards with stats preview
- Points tracking with limit warning
- Add/remove units
"""

from typing import Callable, Optional, Any
import dearpygui.dearpygui as dpg

from oracle.gui.models.wargame_data import (
    get_wargame_data,
    WargameDataModel,
    UnitCard,
    SlotCategory,
)
from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.gamesystems import UnitProfile


# Callback types
UnitSelectedCallback = Callable[[UnitCard], None]
ArmyChangedCallback = Callable[[int, int], None]  # (current_points, limit)


class ArmyBuilderPanel:
    """
    Two-pane army builder interface.

    Left side shows available units organized by slot.
    Right side shows your current army selection.
    """

    def __init__(
        self,
        parent: str,
        on_unit_selected: Optional[UnitSelectedCallback] = None,
        on_army_changed: Optional[ArmyChangedCallback] = None,
        points_limit: int = 1000,
        is_friendly: bool = True,
    ):
        """
        Create the army builder panel.

        Args:
            parent: Parent DearPyGui item tag
            on_unit_selected: Callback when a unit is selected for detail view
            on_army_changed: Callback when army composition changes
            points_limit: Initial points limit
            is_friendly: True for building friendly army, False for enemy
        """
        self.parent = parent
        self._on_unit_selected = on_unit_selected
        self._on_army_changed = on_army_changed
        self._points_limit = points_limit
        self._is_friendly = is_friendly

        self._data = get_wargame_data()
        self._battle = get_battle_roster()

        # UI tags
        self._tag = f"army_builder_{id(self)}"
        self._slot_filter_tag = f"{self._tag}_slot"
        self._search_tag = f"{self._tag}_search"
        self._available_list_tag = f"{self._tag}_available"
        self._army_list_tag = f"{self._tag}_army"
        self._points_tag = f"{self._tag}_points"

        # Current filter
        self._current_slot: Optional[SlotCategory] = None
        self._search_query = ""

        # Register as observer
        self._data.add_observer(self._on_data_changed)

        self._build()

    def _build(self):
        """Build the UI components."""
        with dpg.group(parent=self.parent, horizontal=True, tag=f"{self._tag}_root"):
            # Left pane: Available Units
            with dpg.child_window(width=320, height=-1, border=True):
                dpg.add_text(
                    "Available Units",
                    color=(200, 160, 120)
                )
                dpg.add_separator()

                # Slot filter
                dpg.add_text("Filter by Slot:", color=(150, 150, 150))
                slots = self._data.get_available_slots()
                slot_names = ["All"] + [s.display_name for s in slots]
                dpg.add_combo(
                    items=slot_names,
                    default_value="All",
                    callback=self._on_slot_filter,
                    tag=self._slot_filter_tag,
                    width=-1,
                )

                # Search
                dpg.add_input_text(
                    hint="Search units...",
                    callback=self._on_search,
                    tag=self._search_tag,
                    width=-1,
                )

                dpg.add_spacer(height=5)

                # Unit list
                with dpg.child_window(
                    height=-40,
                    border=False,
                    tag=self._available_list_tag
                ):
                    dpg.add_text(
                        "Select a faction to see units",
                        color=(100, 100, 100)
                    )

                # Add button
                dpg.add_button(
                    label="Add Selected Unit",
                    callback=self._add_selected_unit,
                    width=-1,
                )

            dpg.add_spacer(width=10)

            # Right pane: Your Army
            with dpg.child_window(width=320, height=-1, border=True):
                title = "Your Army" if self._is_friendly else "Enemy Army"
                dpg.add_text(title, color=(200, 160, 120))
                dpg.add_separator()

                # Points display
                with dpg.group(horizontal=True):
                    dpg.add_text("Points:", color=(150, 150, 150))
                    dpg.add_text(
                        f"0 / {self._points_limit}",
                        tag=self._points_tag,
                    )

                # Progress bar for points
                dpg.add_progress_bar(
                    default_value=0,
                    tag=f"{self._tag}_points_bar",
                    width=-1,
                )

                dpg.add_spacer(height=5)

                # Army list
                with dpg.child_window(
                    height=-80,
                    border=False,
                    tag=self._army_list_tag
                ):
                    dpg.add_text("No units added", color=(100, 100, 100))

                # Army controls
                dpg.add_button(
                    label="Remove Selected",
                    callback=self._remove_selected_unit,
                    width=-1,
                )
                dpg.add_button(
                    label="Clear Army",
                    callback=self._clear_army,
                    width=-1,
                )

        # State for selection
        self._selected_available: Optional[UnitCard] = None
        self._selected_army_unit_id: Optional[str] = None

    def _on_data_changed(self, data: WargameDataModel):
        """Handle data model changes (system/faction change)."""
        self._refresh_available_units()
        self._refresh_slot_filter()

    def _refresh_slot_filter(self):
        """Update slot filter dropdown."""
        slots = self._data.get_available_slots()
        slot_names = ["All"] + [s.display_name for s in slots]
        dpg.configure_item(self._slot_filter_tag, items=slot_names)

    def _refresh_available_units(self):
        """Refresh the available units list."""
        # Clear existing
        if dpg.does_item_exist(self._available_list_tag):
            dpg.delete_item(self._available_list_tag, children_only=True)

        # Get units based on filter
        if self._current_slot:
            cards = self._data.get_units_by_slot(self._current_slot)
        else:
            cards = self._data.get_unit_cards()

        # Apply search filter
        if self._search_query:
            query = self._search_query.lower()
            cards = [
                c for c in cards
                if query in c.name.lower() or
                   query in c.tactical_role.lower()
            ]

        with dpg.group(parent=self._available_list_tag):
            if not cards:
                dpg.add_text(
                    "No units match filter" if self._search_query
                    else "Select a faction to see units",
                    color=(100, 100, 100)
                )
                return

            # Group by slot
            current_slot = None
            for card in cards:
                if card.slot != current_slot:
                    current_slot = card.slot
                    dpg.add_text(
                        f"[{current_slot.display_name}]",
                        color=(140, 140, 100)
                    )

                # Unit entry
                with dpg.group(horizontal=True):
                    dpg.add_selectable(
                        label=f"{card.name}",
                        callback=lambda s, a, c=card: self._select_available(c),
                        width=200,
                    )
                    dpg.add_text(
                        f"{card.points}pts",
                        color=(100, 150, 100)
                    )

    def _refresh_army_list(self):
        """Refresh the army list display."""
        if dpg.does_item_exist(self._army_list_tag):
            dpg.delete_item(self._army_list_tag, children_only=True)

        roster = (
            self._battle.friendly_roster if self._is_friendly
            else self._battle.enemy_roster
        )

        with dpg.group(parent=self._army_list_tag):
            if not roster or not roster.units:
                dpg.add_text("No units added", color=(100, 100, 100))
                self._update_points_display(0)
                return

            total_points = 0
            for unit in roster.units:
                total_points += unit.points_cost

                with dpg.group(horizontal=True):
                    # Unit selectable
                    dpg.add_selectable(
                        label=f"{unit.name}",
                        callback=lambda s, a, u=unit: self._select_army_unit(u),
                        width=180,
                    )
                    # Points and model count
                    model_text = f"x{unit.models_current}" if unit.models_max > 1 else ""
                    dpg.add_text(
                        f"{model_text} {unit.points_cost}pts",
                        color=(100, 150, 100)
                    )

            self._update_points_display(total_points)

    def _update_points_display(self, current: int):
        """Update points display and progress bar."""
        over_limit = current > self._points_limit
        color = (200, 100, 100) if over_limit else (150, 200, 150)

        dpg.set_value(
            self._points_tag,
            f"{current} / {self._points_limit}"
        )
        dpg.configure_item(self._points_tag, color=color)

        # Progress bar
        progress = min(1.0, current / self._points_limit) if self._points_limit > 0 else 0
        dpg.set_value(f"{self._tag}_points_bar", progress)

        if self._on_army_changed:
            self._on_army_changed(current, self._points_limit)

    def _on_slot_filter(self, sender, app_data, user_data):
        """Handle slot filter change."""
        if app_data == "All":
            self._current_slot = None
        else:
            # Find slot by display name
            for slot in SlotCategory:
                if slot.display_name == app_data:
                    self._current_slot = slot
                    break
        self._refresh_available_units()

    def _on_search(self, sender, app_data, user_data):
        """Handle search input."""
        self._search_query = app_data
        self._refresh_available_units()

    def _select_available(self, card: UnitCard):
        """Select a unit from available list."""
        self._selected_available = card
        if self._on_unit_selected:
            self._on_unit_selected(card)

    def _select_army_unit(self, unit):
        """Select a unit from army list."""
        self._selected_army_unit_id = unit.id

    def _add_selected_unit(self):
        """Add the selected unit to the army."""
        if not self._selected_available:
            return

        profile = self._selected_available.profile
        self._battle.add_unit_from_profile(
            profile,
            to_friendly=self._is_friendly
        )
        self._refresh_army_list()

    def _remove_selected_unit(self):
        """Remove the selected unit from the army."""
        if not self._selected_army_unit_id:
            return

        self._battle.remove_unit(
            self._selected_army_unit_id,
            from_friendly=self._is_friendly
        )
        self._selected_army_unit_id = None
        self._refresh_army_list()

    def _clear_army(self):
        """Clear all units from the army."""
        roster = (
            self._battle.friendly_roster if self._is_friendly
            else self._battle.enemy_roster
        )
        if roster:
            roster.units.clear()
        self._refresh_army_list()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_points_limit(self, limit: int):
        """Set the points limit."""
        self._points_limit = limit
        self._refresh_army_list()

    def refresh(self):
        """Refresh all displays."""
        self._refresh_available_units()
        self._refresh_army_list()
        self._refresh_slot_filter()

    def add_unit_by_name(self, unit_name: str) -> bool:
        """
        Add a unit to the army by name.

        Args:
            unit_name: Name of unit to add

        Returns:
            True if unit was found and added
        """
        profile = self._data.get_unit_profile(unit_name)
        if profile:
            self._battle.add_unit_from_profile(
                profile,
                to_friendly=self._is_friendly
            )
            self._refresh_army_list()
            return True
        return False

    def get_total_points(self) -> int:
        """Get current total points."""
        roster = (
            self._battle.friendly_roster if self._is_friendly
            else self._battle.enemy_roster
        )
        if roster:
            return roster.points_all
        return 0

    def get_unit_count(self) -> int:
        """Get number of units in army."""
        roster = (
            self._battle.friendly_roster if self._is_friendly
            else self._battle.enemy_roster
        )
        if roster:
            return len(roster.units)
        return 0
