"""
Game Selector - Game system and faction selection UI.

Provides:
- Game system dropdown with available systems
- Faction dropdown that updates when system changes
- System/faction info display
- Points limit configuration
"""

from typing import Callable, Optional
import dearpygui.dearpygui as dpg

from oracle.gui.models.wargame_data import get_wargame_data, WargameDataModel


# Callback types
SystemChangeCallback = Callable[[str, str], None]  # (system_id, system_name)
FactionChangeCallback = Callable[[str], None]  # (faction_name)


class GameSelectorPanel:
    """
    Game system and faction selection panel.

    Displays dropdown selectors for choosing a game system
    and faction, with info display and callbacks for changes.
    """

    def __init__(
        self,
        parent: str,
        on_system_change: Optional[SystemChangeCallback] = None,
        on_faction_change: Optional[FactionChangeCallback] = None,
        width: int = -1,
    ):
        """
        Create the game selector panel.

        Args:
            parent: Parent DearPyGui item tag
            on_system_change: Callback when system changes
            on_faction_change: Callback when faction changes
            width: Panel width (-1 for auto)
        """
        self.parent = parent
        self._on_system_change = on_system_change
        self._on_faction_change = on_faction_change
        self.width = width

        self._data = get_wargame_data()

        # UI tags
        self._tag_prefix = f"game_selector_{id(self)}"
        self._system_combo_tag = f"{self._tag_prefix}_system"
        self._faction_combo_tag = f"{self._tag_prefix}_faction"
        self._system_info_tag = f"{self._tag_prefix}_sysinfo"
        self._faction_info_tag = f"{self._tag_prefix}_facinfo"
        self._points_input_tag = f"{self._tag_prefix}_points"

        # State
        self._points_limit = 1000

        self._build()

    def _build(self):
        """Build the UI components."""
        with dpg.group(parent=self.parent, tag=f"{self._tag_prefix}_root"):
            # Header
            dpg.add_text("Game Setup", color=(200, 160, 120))
            dpg.add_separator()

            # Game System
            dpg.add_text("Game System:", color=(150, 150, 150))
            systems = self._data.list_available_systems()
            system_names = [name for _, name in systems]
            if not system_names:
                system_names = ["No game systems found"]

            dpg.add_combo(
                items=system_names,
                default_value=system_names[0] if system_names else "",
                callback=self._on_system_selected,
                tag=self._system_combo_tag,
                width=self.width,
            )

            dpg.add_text(
                "",
                tag=self._system_info_tag,
                wrap=280,
                color=(120, 120, 120),
            )

            dpg.add_spacer(height=8)

            # Faction
            dpg.add_text("Faction:", color=(150, 150, 150))
            dpg.add_combo(
                items=["Select a game system first"],
                default_value="Select a game system first",
                callback=self._on_faction_selected,
                tag=self._faction_combo_tag,
                width=self.width,
                enabled=False,
            )

            dpg.add_text(
                "",
                tag=self._faction_info_tag,
                wrap=280,
                color=(120, 120, 120),
            )

            dpg.add_spacer(height=8)

            # Points Limit
            dpg.add_text("Points Limit:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                dpg.add_input_int(
                    default_value=1000,
                    min_value=0,
                    max_value=10000,
                    step=100,
                    callback=self._on_points_change,
                    tag=self._points_input_tag,
                    width=120,
                )
                dpg.add_text("pts")

            # Quick presets
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="500",
                    callback=lambda: self._set_points(500),
                    width=50,
                )
                dpg.add_button(
                    label="1000",
                    callback=lambda: self._set_points(1000),
                    width=50,
                )
                dpg.add_button(
                    label="1500",
                    callback=lambda: self._set_points(1500),
                    width=50,
                )
                dpg.add_button(
                    label="2000",
                    callback=lambda: self._set_points(2000),
                    width=50,
                )

    def _on_system_selected(self, sender, app_data, user_data):
        """Handle game system selection."""
        system_name = app_data

        # Find system ID by display name
        systems = self._data.list_available_systems()
        system_id = None
        for sid, sname in systems:
            if sname == system_name:
                system_id = sid
                break

        if system_id and self._data.set_system(system_id):
            # Update faction dropdown
            factions = self._data.list_factions()
            if factions:
                dpg.configure_item(
                    self._faction_combo_tag,
                    items=factions,
                    default_value=factions[0],
                    enabled=True,
                )
                # Auto-select first faction
                self._data.set_faction(factions[0])
                self._update_faction_info()
            else:
                dpg.configure_item(
                    self._faction_combo_tag,
                    items=["No factions available"],
                    default_value="No factions available",
                    enabled=False,
                )

            # Update system info
            dpg.set_value(
                self._system_info_tag,
                f"Selected: {system_name}"
            )

            # Fire callback
            if self._on_system_change:
                self._on_system_change(system_id, system_name)

            # Fire faction callback for auto-selected faction
            if factions and self._on_faction_change:
                self._on_faction_change(factions[0])

    def _on_faction_selected(self, sender, app_data, user_data):
        """Handle faction selection."""
        faction_name = app_data

        if self._data.set_faction(faction_name):
            self._update_faction_info()

            if self._on_faction_change:
                self._on_faction_change(faction_name)

    def _update_faction_info(self):
        """Update faction info display."""
        info = self._data.get_faction_info()
        if info:
            text = f"{info.get('playstyle', '')}\n"
            strengths = info.get("strengths", [])
            if strengths:
                text += f"Strengths: {', '.join(strengths[:2])}"
            dpg.set_value(self._faction_info_tag, text)
        else:
            dpg.set_value(self._faction_info_tag, "")

    def _on_points_change(self, sender, app_data, user_data):
        """Handle points limit change."""
        self._points_limit = app_data

    def _set_points(self, points: int):
        """Set points limit via preset button."""
        self._points_limit = points
        dpg.set_value(self._points_input_tag, points)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def selected_system(self) -> Optional[str]:
        """Get currently selected system ID."""
        if self._data.current_system:
            return self._data.current_system.id
        return None

    @property
    def selected_system_name(self) -> str:
        """Get currently selected system display name."""
        return self._data.current_system_name

    @property
    def selected_faction(self) -> Optional[str]:
        """Get currently selected faction name."""
        if self._data.current_faction:
            return self._data.current_faction.name
        return None

    @property
    def points_limit(self) -> int:
        """Get configured points limit."""
        return self._points_limit

    def set_system(self, system_id: str) -> bool:
        """
        Programmatically set the game system.

        Args:
            system_id: System ID to select

        Returns:
            True if system was set successfully
        """
        if self._data.set_system(system_id):
            # Update combo display
            dpg.set_value(self._system_combo_tag, self._data.current_system_name)
            self._on_system_selected(None, self._data.current_system_name, None)
            return True
        return False

    def set_faction(self, faction_name: str) -> bool:
        """
        Programmatically set the faction.

        Args:
            faction_name: Faction name to select

        Returns:
            True if faction was set successfully
        """
        if self._data.set_faction(faction_name):
            dpg.set_value(self._faction_combo_tag, faction_name)
            self._update_faction_info()
            if self._on_faction_change:
                self._on_faction_change(faction_name)
            return True
        return False

    def set_points_limit(self, points: int) -> None:
        """Programmatically set points limit."""
        self._set_points(points)

    def refresh_systems(self) -> None:
        """Refresh the available systems list."""
        systems = self._data.list_available_systems()
        system_names = [name for _, name in systems]
        if system_names:
            dpg.configure_item(
                self._system_combo_tag,
                items=system_names,
            )
