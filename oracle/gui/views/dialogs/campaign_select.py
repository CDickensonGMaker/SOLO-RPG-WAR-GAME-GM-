"""
Campaign Selection Dialog - Modal for starting/loading campaigns.

Features:
- New campaign creation
- Load existing campaigns
- Campaign preview info
"""

from typing import Optional, Callable, List, Dict, Any
import dearpygui.dearpygui as dpg

from oracle.gui import style
from oracle.gui.models.game_state import GameState, CampaignInfo


class CampaignSelectDialog:
    """
    Modal dialog for campaign selection.

    Allows starting new campaigns or loading saved ones.
    """

    def __init__(self, game_state: GameState):
        self.game_state = game_state

        # Widget tags
        self._window_tag = None
        self._campaign_list_tag = None
        self._preview_tag = None
        self._save_list_tag = None

        # Selection state
        self._selected_campaign: Optional[str] = None
        self._selected_save: Optional[str] = None

        # Character input
        self._character_name = "Unnamed Regent"

        # Callbacks
        self._on_campaign_started: List[Callable] = []
        self._on_campaign_loaded: List[Callable] = []

        self._build()

    def _build(self):
        """Build the dialog UI."""
        with dpg.window(
            label="Campaign Selection",
            modal=True,
            show=False,
            width=700,
            height=500,
            tag="campaign_select_dialog",
            on_close=self.hide
        ):
            self._window_tag = dpg.last_item()

            # Tab bar for New/Load
            with dpg.tab_bar():
                # New Campaign Tab
                with dpg.tab(label="New Campaign"):
                    self._build_new_campaign_tab()

                # Load Campaign Tab
                with dpg.tab(label="Load Campaign"):
                    self._build_load_campaign_tab()

    def _build_new_campaign_tab(self):
        """Build the new campaign tab content."""
        with dpg.group(horizontal=True):
            # Campaign list (left side)
            with dpg.child_window(width=300, height=-50):
                dpg.add_text("Available Campaigns", color=(200, 180, 140))
                dpg.add_separator()

                self._campaign_list_tag = dpg.add_group(tag="new_campaign_list")
                self._refresh_campaign_list()

            # Preview (right side)
            with dpg.child_window(width=-1, height=-50):
                dpg.add_text("Campaign Preview", color=(200, 180, 140))
                dpg.add_separator()

                self._preview_tag = dpg.add_group(tag="campaign_preview")

        # Bottom section - Character name and start button
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text("Character Name:")
            dpg.add_input_text(
                default_value=self._character_name,
                width=200,
                callback=self._on_name_changed
            )
            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Start Campaign",
                callback=self._on_start_clicked,
                width=150
            )
            dpg.add_button(
                label="Cancel",
                callback=self.hide,
                width=100
            )

    def _build_load_campaign_tab(self):
        """Build the load campaign tab content."""
        with dpg.group(horizontal=True):
            # Save list (left side)
            with dpg.child_window(width=300, height=-50):
                dpg.add_text("Saved Games", color=(200, 180, 140))
                dpg.add_separator()

                self._save_list_tag = dpg.add_group(tag="save_list")

            # Save details (right side)
            with dpg.child_window(width=-1, height=-50):
                dpg.add_text("Save Details", color=(200, 180, 140))
                dpg.add_separator()

                self._save_details_tag = dpg.add_group(tag="save_details")

        # Bottom section
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Load",
                callback=self._on_load_clicked,
                width=100
            )
            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Refresh",
                callback=self._refresh_save_list,
                width=100
            )
            dpg.add_button(
                label="Cancel",
                callback=self.hide,
                width=100
            )

    def _refresh_campaign_list(self):
        """Refresh the list of available campaigns."""
        dpg.delete_item(self._campaign_list_tag, children_only=True)

        unlocked = self.game_state.get_unlocked_campaigns()

        if not unlocked:
            dpg.add_text(
                "No campaigns available",
                parent=self._campaign_list_tag,
                color=(150, 150, 150)
            )
            return

        for info in unlocked:
            with dpg.group(parent=self._campaign_list_tag):
                # Selectable campaign item - use user_data for proper callback
                dpg.add_selectable(
                    label=info.name,
                    callback=self._on_campaign_selected,
                    user_data=info,
                    span_columns=True
                )
                dpg.add_text(
                    f"  {info.tagline}",
                    color=(150, 150, 150)
                )
                dpg.add_text(
                    f"  Difficulty: {info.difficulty.title()}",
                    color=(180, 150, 100)
                )
                dpg.add_spacer(height=5)

    def _on_campaign_selected(self, sender, app_data, user_data):
        """Handle campaign selection."""
        info = user_data
        if info is None:
            return
        self._selected_campaign = info.id
        self._refresh_preview(info)

    def _refresh_preview(self, info: CampaignInfo):
        """Refresh the campaign preview panel."""
        dpg.delete_item(self._preview_tag, children_only=True)

        with dpg.group(parent=self._preview_tag):
            # Title
            dpg.add_text(info.name, color=(255, 255, 255))
            dpg.add_text(info.tagline, color=(200, 180, 140))

            dpg.add_spacer(height=10)

            # Theme and difficulty
            dpg.add_text(f"Theme: {info.theme.replace('_', ' ').title()}")
            dpg.add_text(f"Difficulty: {info.difficulty.title()}")

            dpg.add_spacer(height=10)

            # Description
            dpg.add_text("Description:", color=(200, 180, 140))
            # Wrap long description
            desc = info.description_short or info.description_long[:200] + "..."
            dpg.add_text(desc, wrap=250, color=(180, 180, 180))

            dpg.add_spacer(height=10)

            # Recommended bloodlines
            if info.recommended_bloodlines:
                dpg.add_text("Recommended Bloodlines:", color=(200, 180, 140))
                dpg.add_text(
                    ", ".join(info.recommended_bloodlines),
                    color=(180, 180, 180)
                )

    def _refresh_save_list(self):
        """Refresh the list of saved games."""
        if not self._save_list_tag:
            return

        dpg.delete_item(self._save_list_tag, children_only=True)

        saves = self.game_state.list_saves()

        if not saves:
            dpg.add_text(
                "No saved games found",
                parent=self._save_list_tag,
                color=(150, 150, 150)
            )
            return

        for save in saves:
            with dpg.group(parent=self._save_list_tag):
                dpg.add_selectable(
                    label=save.get("name", "Unknown"),
                    callback=self._on_save_selected,
                    user_data=save,
                    span_columns=True
                )

                # Campaign info
                campaign_id = save.get("active_campaign_id", "None")
                dpg.add_text(
                    f"  Campaign: {campaign_id}",
                    color=(150, 150, 150)
                )

                # Save time
                saved_at = save.get("saved_at", "Unknown")
                if saved_at and len(saved_at) > 10:
                    saved_at = saved_at[:10]  # Just date
                dpg.add_text(
                    f"  Saved: {saved_at}",
                    color=(120, 120, 120)
                )

                dpg.add_spacer(height=5)

    def _on_save_selected(self, sender, app_data, user_data):
        """Handle save selection."""
        save = user_data
        if save is None:
            return
        self._selected_save = save.get("name")
        self._refresh_save_details(save)

    def _refresh_save_details(self, save: Dict[str, Any]):
        """Refresh save details panel."""
        dpg.delete_item(self._save_details_tag, children_only=True)

        with dpg.group(parent=self._save_details_tag):
            dpg.add_text(save.get("name", "Unknown"), color=(255, 255, 255))

            dpg.add_spacer(height=10)

            dpg.add_text(f"Campaign: {save.get('active_campaign_id', 'None')}")
            dpg.add_text(f"Saved: {save.get('saved_at', 'Unknown')}")

            completed = save.get("completed_campaigns", [])
            if completed:
                dpg.add_spacer(height=10)
                dpg.add_text("Completed Campaigns:", color=(200, 180, 140))
                for c in completed:
                    dpg.add_text(f"  - {c}", color=(150, 180, 150))

    def _on_name_changed(self, sender, value):
        """Handle character name input change."""
        self._character_name = value

    def _on_start_clicked(self):
        """Handle start campaign button click."""
        if not self._selected_campaign:
            return

        # Start the campaign
        campaign = self.game_state.start_campaign(
            self._selected_campaign,
            character_id="player",
            character_name=self._character_name
        )

        if campaign:
            self.hide()
            for callback in self._on_campaign_started:
                callback(campaign)

    def _on_load_clicked(self):
        """Handle load button click."""
        if not self._selected_save:
            return

        success = self.game_state.load_save(self._selected_save)

        if success:
            self.hide()
            for callback in self._on_campaign_loaded:
                callback(self.game_state.active_campaign)

    def show(self):
        """Show the dialog, centered on the current viewport."""
        self._refresh_campaign_list()
        self._refresh_save_list()
        dpg.configure_item(self._window_tag, pos=style.centered_pos(700, 500))
        dpg.show_item(self._window_tag)

    def hide(self):
        """Hide the dialog."""
        dpg.hide_item(self._window_tag)

    def on_campaign_started(self, callback: Callable):
        """Register callback for campaign start."""
        self._on_campaign_started.append(callback)

    def on_campaign_loaded(self, callback: Callable):
        """Register callback for campaign load."""
        self._on_campaign_loaded.append(callback)
