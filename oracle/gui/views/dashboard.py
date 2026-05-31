"""
Dashboard Panel - Left sidebar showing character, domain, and quick actions.

Displays:
- Character name and bloodline
- Domain statistics (RP, GB, Holdings)
- Actions remaining this turn
- Quick action buttons
"""

from typing import Optional, Callable, List
import dearpygui.dearpygui as dpg

from oracle.gui.models.campaign import CampaignState, TurnState, Season
from oracle.gui.config import config


class DashboardPanel:
    """
    Left sidebar panel showing character and domain information.

    This panel provides at-a-glance information about the player's
    regent and domain, plus quick access to common actions.
    """

    def __init__(self, parent: int):
        self.parent = parent
        self.campaign: Optional[CampaignState] = None

        # Widget tags for updating
        self._character_name_tag = None
        self._bloodline_tag = None
        self._turn_tag = None
        self._season_tag = None
        self._actions_tag = None
        self._rp_tag = None
        self._gb_tag = None
        self._chaos_tag = None

        # Callbacks
        self._on_action: List[Callable] = []
        self._on_advance_turn: List[Callable] = []

        self._build()

    def _build(self):
        """Build the dashboard UI."""
        width = int(config.window.width * config.window.dashboard_width)

        with dpg.child_window(
            parent=self.parent,
            width=width,
            height=-1,
            tag="dashboard_panel"
        ):
            # Header
            dpg.add_text("REGENT", color=(200, 180, 140))
            dpg.add_separator()

            # Character section
            with dpg.group(horizontal=False):
                self._character_name_tag = dpg.add_text(
                    "No Campaign Active",
                    color=(255, 255, 255)
                )
                self._bloodline_tag = dpg.add_text(
                    "",
                    color=(180, 140, 100)
                )

            dpg.add_spacer(height=10)

            # Turn info section
            dpg.add_text("TURN", color=(200, 180, 140))
            dpg.add_separator()

            with dpg.group(horizontal=False):
                with dpg.group(horizontal=True):
                    dpg.add_text("Turn:")
                    self._turn_tag = dpg.add_text("1", color=(255, 255, 200))

                with dpg.group(horizontal=True):
                    dpg.add_text("Season:")
                    self._season_tag = dpg.add_text("Spring 551 MR", color=(180, 220, 180))

                with dpg.group(horizontal=True):
                    dpg.add_text("Actions:")
                    self._actions_tag = dpg.add_text("3", color=(200, 200, 255))

            dpg.add_spacer(height=10)

            # Domain resources section
            dpg.add_text("DOMAIN", color=(200, 180, 140))
            dpg.add_separator()

            with dpg.group(horizontal=False):
                with dpg.group(horizontal=True):
                    dpg.add_text("Regency (RP):")
                    self._rp_tag = dpg.add_text("0", color=(220, 200, 100))

                with dpg.group(horizontal=True):
                    dpg.add_text("Gold Bars (GB):")
                    self._gb_tag = dpg.add_text("0", color=(255, 215, 0))

            dpg.add_spacer(height=10)

            # Oracle section
            dpg.add_text("ORACLE", color=(200, 180, 140))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_text("Chaos Factor:")
                self._chaos_tag = dpg.add_text("5", color=(200, 100, 100))

            dpg.add_spacer(height=15)

            # Quick actions section
            dpg.add_text("QUICK ACTIONS", color=(200, 180, 140))
            dpg.add_separator()

            with dpg.group(horizontal=False):
                dpg.add_button(
                    label="Advance Turn",
                    callback=self._on_advance_turn_clicked,
                    width=-1
                )

                dpg.add_spacer(height=5)

                dpg.add_button(
                    label="Domain Action",
                    callback=lambda: self._trigger_action("domain"),
                    width=-1
                )

                dpg.add_button(
                    label="Diplomacy",
                    callback=lambda: self._trigger_action("diplomacy"),
                    width=-1
                )

                dpg.add_button(
                    label="Espionage",
                    callback=lambda: self._trigger_action("espionage"),
                    width=-1
                )

                dpg.add_button(
                    label="Oracle Ask",
                    callback=lambda: self._trigger_action("oracle"),
                    width=-1
                )

            dpg.add_spacer(height=15)

            # Campaign info
            dpg.add_text("CAMPAIGN", color=(200, 180, 140))
            dpg.add_separator()

            self._campaign_name_tag = dpg.add_text(
                "None",
                color=(150, 150, 150)
            )
            self._campaign_act_tag = dpg.add_text(
                "",
                color=(150, 150, 150)
            )

    def set_campaign(self, campaign: CampaignState):
        """Set the active campaign and update display."""
        self.campaign = campaign
        self.refresh()

    def refresh(self):
        """Refresh all displayed values."""
        if not self.campaign:
            dpg.set_value(self._character_name_tag, "No Campaign Active")
            dpg.set_value(self._bloodline_tag, "")
            dpg.set_value(self._turn_tag, "-")
            dpg.set_value(self._season_tag, "-")
            dpg.set_value(self._actions_tag, "-")
            dpg.set_value(self._campaign_name_tag, "None")
            dpg.set_value(self._campaign_act_tag, "")
            return

        # Character info
        dpg.set_value(self._character_name_tag, self.campaign.character_name)

        # Bloodline info (would come from character data)
        bloodline_text = self.campaign.variables.get("bloodline_derivation", "Unknown Bloodline")
        dpg.set_value(self._bloodline_tag, bloodline_text)

        # Turn info
        turn = self.campaign.turn
        dpg.set_value(self._turn_tag, str(turn.turn_number))

        season_text = f"{turn.season.value.title()} {turn.year} MR"
        dpg.set_value(self._season_tag, season_text)

        dpg.set_value(self._actions_tag, str(turn.actions_remaining))

        # Actions color based on remaining
        if turn.actions_remaining == 0:
            dpg.configure_item(self._actions_tag, color=(255, 100, 100))
        elif turn.actions_remaining == 1:
            dpg.configure_item(self._actions_tag, color=(255, 200, 100))
        else:
            dpg.configure_item(self._actions_tag, color=(200, 200, 255))

        # Domain resources (from variables or character)
        rp = self.campaign.variables.get("regency_points", 0)
        gb = self.campaign.variables.get("gold_bars", 0)
        dpg.set_value(self._rp_tag, str(rp))
        dpg.set_value(self._gb_tag, str(gb))

        # Chaos factor
        dpg.set_value(self._chaos_tag, str(self.campaign.chaos_factor))

        # Campaign info
        dpg.set_value(self._campaign_name_tag, self.campaign.campaign_name)
        dpg.set_value(
            self._campaign_act_tag,
            f"Act {self.campaign.current_act}"
        )

    def on_action(self, callback: Callable):
        """Register callback for action button clicks."""
        self._on_action.append(callback)

    def on_advance_turn(self, callback: Callable):
        """Register callback for advance turn."""
        self._on_advance_turn.append(callback)

    def _trigger_action(self, action_type: str):
        """Trigger action callbacks."""
        for callback in self._on_action:
            callback(action_type)

    def _on_advance_turn_clicked(self):
        """Handle advance turn button click."""
        for callback in self._on_advance_turn:
            callback()

    def set_actions_remaining(self, count: int):
        """Update actions remaining display."""
        if self._actions_tag:
            dpg.set_value(self._actions_tag, str(count))

            if count == 0:
                dpg.configure_item(self._actions_tag, color=(255, 100, 100))
            elif count == 1:
                dpg.configure_item(self._actions_tag, color=(255, 200, 100))
            else:
                dpg.configure_item(self._actions_tag, color=(200, 200, 255))

    def set_chaos_factor(self, chaos: int):
        """Update chaos factor display."""
        if self._chaos_tag:
            dpg.set_value(self._chaos_tag, str(chaos))

            # Color based on chaos level
            if chaos <= 3:
                dpg.configure_item(self._chaos_tag, color=(100, 200, 100))
            elif chaos <= 6:
                dpg.configure_item(self._chaos_tag, color=(200, 200, 100))
            else:
                dpg.configure_item(self._chaos_tag, color=(255, 100, 100))
