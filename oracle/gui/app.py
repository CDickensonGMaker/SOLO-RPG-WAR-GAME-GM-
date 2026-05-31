"""
Birthright Campaign Manager - Main Application

The central Dear PyGui application that coordinates all panels,
controllers, and game state for the Birthright campaign system.
"""

from typing import Optional
import dearpygui.dearpygui as dpg

from oracle.gui.config import config, ConfigManager
from oracle.gui.models.game_state import GameState
from oracle.gui.models.campaign import CampaignState, DomainEvent, EventChoice
from oracle.gui.controllers.domain_turn import DomainTurnController
from oracle.gui.controllers.event_handler import EventHandler
from oracle.gui.controllers.relationship import RelationshipController
from oracle.gui.views.dashboard import DashboardPanel
from oracle.gui.views.event_log import EventLogPanel
from oracle.gui.views.map_view import MapTimelinePanel
from oracle.gui.views.npc_graph import NPCGraphPanel
from oracle.gui.views.dialogs.campaign_select import CampaignSelectDialog
from oracle.gui.views.dialogs.domain_action import DomainActionDialog


class BirthrightApp:
    """
    Main application class for the Birthright Campaign Manager.

    Coordinates:
    - Dear PyGui window setup
    - Panel layout and management
    - Game state and controllers
    - Event routing between components
    """

    def __init__(self):
        # Game state
        self.game_state = GameState()

        # Controllers (initialized when campaign starts)
        self.turn_controller: Optional[DomainTurnController] = None
        self.event_handler: Optional[EventHandler] = None
        self.relationship_controller: Optional[RelationshipController] = None

        # UI panels (initialized in _build_ui)
        self.dashboard: Optional[DashboardPanel] = None
        self.event_log: Optional[EventLogPanel] = None
        self.map_view: Optional[MapTimelinePanel] = None
        self.npc_graph: Optional[NPCGraphPanel] = None

        # Dialogs
        self.campaign_dialog: Optional[CampaignSelectDialog] = None
        self.action_dialog: Optional[DomainActionDialog] = None

        # Main window tag
        self._main_window_tag = None

    def run(self):
        """Run the application."""
        dpg.create_context()

        self._setup_theme()
        self._build_ui()
        self._setup_callbacks()

        dpg.create_viewport(
            title=config.window.title,
            width=config.window.width,
            height=config.window.height
        )

        dpg.setup_dearpygui()
        dpg.show_viewport()

        # Show campaign selection on startup
        dpg.set_frame_callback(30, self._on_startup)

        dpg.start_dearpygui()
        dpg.destroy_context()

    def _setup_theme(self):
        """Set up the visual theme."""
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                # Colors
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (25, 25, 30, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 42, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (60, 60, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (45, 45, 55, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (55, 55, 65, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (65, 65, 75, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 60, 50, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (90, 75, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (110, 90, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Header, (60, 55, 50, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (75, 68, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (90, 80, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (55, 50, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (75, 68, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (90, 80, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (35, 35, 40, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (50, 45, 40, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Separator, (80, 70, 60, 255))

                # Styling
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)

        dpg.bind_theme(global_theme)

    def _build_ui(self):
        """Build the main UI layout."""
        # Main window
        with dpg.window(
            label="Birthright Campaign Manager",
            tag="main_window",
            no_title_bar=True,
            no_move=True,
            no_resize=True,
            no_collapse=True
        ):
            self._main_window_tag = dpg.last_item()

            # Menu bar
            with dpg.menu_bar():
                with dpg.menu(label="Campaign"):
                    dpg.add_menu_item(
                        label="New/Load Campaign",
                        callback=self._show_campaign_dialog
                    )
                    dpg.add_menu_item(
                        label="Save",
                        callback=self._save_game
                    )
                    dpg.add_separator()
                    dpg.add_menu_item(
                        label="Exit",
                        callback=self._exit
                    )

                with dpg.menu(label="View"):
                    dpg.add_menu_item(
                        label="NPC Relationships",
                        callback=self._toggle_npc_graph
                    )
                    dpg.add_menu_item(
                        label="Domain Actions",
                        callback=self._show_action_dialog
                    )

                with dpg.menu(label="Oracle"):
                    dpg.add_menu_item(
                        label="Ask Yes/No",
                        callback=self._show_oracle_dialog
                    )
                    dpg.add_menu_item(
                        label="Adjust Chaos",
                        callback=self._show_chaos_dialog
                    )

                with dpg.menu(label="Help"):
                    dpg.add_menu_item(
                        label="Quick Reference",
                        callback=self._show_help
                    )
                    dpg.add_menu_item(
                        label="About",
                        callback=self._show_about
                    )

            # Main content area
            with dpg.group(horizontal=True, tag="main_content"):
                # Create panels
                self.dashboard = DashboardPanel(parent="main_content")
                self.event_log = EventLogPanel(parent="main_content")
                self.map_view = MapTimelinePanel(parent="main_content")

        # Create floating windows (hidden by default)
        self.npc_graph = NPCGraphPanel()

        # Create dialogs
        self.campaign_dialog = CampaignSelectDialog(self.game_state)
        self.action_dialog = DomainActionDialog()

        # Set primary window
        dpg.set_primary_window("main_window", True)

    def _setup_callbacks(self):
        """Wire up callbacks between components."""
        # Dashboard callbacks
        self.dashboard.on_action(self._on_dashboard_action)
        self.dashboard.on_advance_turn(self._on_advance_turn)

        # Event log callbacks
        self.event_log.on_choice_selected(self._on_event_choice)
        self.event_log.on_oracle_requested(self._on_oracle_requested)

        # Campaign dialog callbacks
        self.campaign_dialog.on_campaign_started(self._on_campaign_started)
        self.campaign_dialog.on_campaign_loaded(self._on_campaign_loaded)

        # Action dialog callbacks
        self.action_dialog.on_action_executed(self._on_action_executed)

    def _on_startup(self):
        """Called after startup to show initial dialog."""
        # Try to load autosave first
        if self.game_state.load_save("autosave"):
            if self.game_state.active_campaign:
                self._on_campaign_loaded(self.game_state.active_campaign)
                return

        # Otherwise show campaign selection
        self.campaign_dialog.show()

    def _on_campaign_started(self, campaign: CampaignState):
        """Handle new campaign start."""
        self._setup_campaign(campaign)

    def _on_campaign_loaded(self, campaign: CampaignState):
        """Handle campaign load."""
        self._setup_campaign(campaign)

    def _setup_campaign(self, campaign: CampaignState):
        """Set up controllers and UI for active campaign."""
        # Initialize controllers
        self.turn_controller = DomainTurnController(self.game_state)
        self.event_handler = EventHandler(campaign)
        self.relationship_controller = RelationshipController(campaign)

        # Wire controller callbacks
        self.turn_controller.on_event(self._on_event_triggered)

        # Update all panels
        self.dashboard.set_campaign(campaign)
        self.event_log.set_campaign(campaign)
        self.map_view.set_campaign(campaign)
        self.npc_graph.set_campaign(campaign)

        # Update dialog
        self.action_dialog.set_campaign(campaign)

        # Start first turn's events
        events = self.turn_controller.start_turn()
        if events:
            self.event_log.show_event(events[0])

    def _on_event_triggered(self, event: DomainEvent):
        """Handle new event triggered by turn controller."""
        self.event_log.show_event(event)

    def _on_event_choice(self, event: DomainEvent, choice: EventChoice):
        """Handle player choosing an event option."""
        if not self.event_handler:
            return

        # Check if oracle roll needed
        if choice.oracle_prompt:
            result = self.event_handler.roll_oracle(
                choice.oracle_prompt,
                "even"  # Default likelihood
            )
            outcome = f"{result['answer_text']} - {choice.oracle_prompt}"
            self.event_log.show_oracle_result(result)
        else:
            outcome = choice.consequences

        # Resolve the choice
        resolution = self.event_handler.resolve_choice(event, choice, outcome)

        # Refresh UI
        self.dashboard.refresh()
        self.event_log.refresh()
        self.map_view.refresh()

        # Check for more events
        if self.game_state.active_campaign:
            pending = self.game_state.active_campaign.get_available_events()
            if pending:
                self.event_log.show_event(pending[0])

    def _on_oracle_requested(self, event: DomainEvent):
        """Handle oracle request for an event."""
        self._show_oracle_dialog()

    def _on_dashboard_action(self, action_type: str):
        """Handle action button from dashboard."""
        if action_type == "oracle":
            self._show_oracle_dialog()
        elif action_type == "domain":
            self._show_action_dialog()
        elif action_type == "diplomacy":
            self._show_action_dialog()  # Pre-select diplomacy
        elif action_type == "espionage":
            self._show_action_dialog()  # Pre-select espionage

    def _on_advance_turn(self):
        """Handle advance turn button."""
        if not self.turn_controller:
            return

        # Check if there are pending events
        if self.game_state.active_campaign:
            pending = self.game_state.active_campaign.get_available_events()
            if pending:
                # Can't advance with unresolved events
                return

        # Advance turn
        new_turn = self.turn_controller.advance_turn()

        # Refresh UI
        self.dashboard.refresh()
        self.event_log.refresh()
        self.map_view.refresh()

        # Start new turn's events
        events = self.turn_controller.start_turn()
        if events:
            self.event_log.show_event(events[0])

    def _on_action_executed(self, result: dict):
        """Handle domain action execution."""
        if not self.turn_controller or not self.game_state.active_campaign:
            return

        # Deduct action
        success = self.turn_controller.take_domain_action(
            result["action"],
            result.get("target", "")
        )

        if success:
            # Apply costs
            cost = result.get("cost", {})
            campaign = self.game_state.active_campaign

            if isinstance(cost.get("rp"), int):
                current = campaign.variables.get("regency_points", 0)
                campaign.variables["regency_points"] = max(0, current - cost["rp"])

            if isinstance(cost.get("gb"), int):
                current = campaign.variables.get("gold_bars", 0)
                campaign.variables["gold_bars"] = max(0, current - cost["gb"])

            # Refresh dashboard
            self.dashboard.refresh()

    def _show_campaign_dialog(self):
        """Show campaign selection dialog."""
        self.campaign_dialog.show()

    def _show_action_dialog(self):
        """Show domain action dialog."""
        self.action_dialog.show()

    def _toggle_npc_graph(self):
        """Toggle NPC relationship graph."""
        self.npc_graph.toggle()

    def _show_oracle_dialog(self):
        """Show oracle question dialog."""
        if dpg.does_item_exist("oracle_dialog"):
            dpg.delete_item("oracle_dialog")

        with dpg.window(
            label="Ask the Oracle",
            modal=True,
            tag="oracle_dialog",
            width=400,
            height=250,
            pos=[config.window.width // 2 - 200, config.window.height // 2 - 125]
        ):
            dpg.add_text("Enter your question:")
            question_input = dpg.add_input_text(
                multiline=True,
                width=-1,
                height=60,
                tag="oracle_question_input"
            )

            dpg.add_text("Likelihood:")
            likelihood = dpg.add_combo(
                items=["Impossible", "Unlikely", "Even", "Likely", "Certain"],
                default_value="Even",
                tag="oracle_likelihood",
                width=-1
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Ask",
                    callback=self._execute_oracle,
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("oracle_dialog"),
                    width=100
                )

    def _execute_oracle(self):
        """Execute oracle roll from dialog."""
        question = dpg.get_value("oracle_question_input")
        likelihood = dpg.get_value("oracle_likelihood").lower()

        if self.event_handler:
            result = self.event_handler.roll_oracle(question, likelihood)
            self.event_log.show_oracle_result(result)

        dpg.delete_item("oracle_dialog")

    def _show_chaos_dialog(self):
        """Show chaos adjustment dialog."""
        if not self.game_state.active_campaign:
            return

        if dpg.does_item_exist("chaos_dialog"):
            dpg.delete_item("chaos_dialog")

        current = self.game_state.active_campaign.chaos_factor

        with dpg.window(
            label="Chaos Factor",
            modal=True,
            tag="chaos_dialog",
            width=300,
            height=150,
            pos=[config.window.width // 2 - 150, config.window.height // 2 - 75]
        ):
            dpg.add_text(f"Current Chaos: {current}")
            dpg.add_slider_int(
                default_value=current,
                min_value=1,
                max_value=9,
                tag="chaos_slider",
                width=-1
            )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=self._apply_chaos,
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("chaos_dialog"),
                    width=100
                )

    def _apply_chaos(self):
        """Apply chaos factor change."""
        new_value = dpg.get_value("chaos_slider")
        if self.game_state.active_campaign:
            self.game_state.active_campaign.chaos_factor = new_value
            self.dashboard.set_chaos_factor(new_value)
        dpg.delete_item("chaos_dialog")

    def _save_game(self):
        """Save current game state."""
        if self.game_state.save_all("autosave"):
            # Show brief notification
            pass

    def _show_help(self):
        """Show help window."""
        if dpg.does_item_exist("help_window"):
            dpg.show_item("help_window")
            return

        with dpg.window(
            label="Quick Reference",
            tag="help_window",
            width=500,
            height=400,
            pos=[50, 50]
        ):
            dpg.add_text("Birthright Campaign Manager", color=(200, 180, 140))
            dpg.add_separator()

            dpg.add_text("Domain Turns:", color=(200, 180, 140))
            dpg.add_text("""
Each turn represents one season of game time.
You have 3 domain actions per turn.
Resolve all events before advancing.
            """, wrap=480)

            dpg.add_text("Oracle System:", color=(200, 180, 140))
            dpg.add_text("""
Ask yes/no questions to the Oracle.
Chaos factor affects probability.
Random events may trigger on extreme rolls.
            """, wrap=480)

            dpg.add_text("Keyboard Shortcuts:", color=(200, 180, 140))
            dpg.add_text("""
Ctrl+S - Save game
Ctrl+N - New campaign
R - Toggle relationship graph
            """, wrap=480)

    def _show_about(self):
        """Show about dialog."""
        if dpg.does_item_exist("about_dialog"):
            dpg.delete_item("about_dialog")

        with dpg.window(
            label="About",
            modal=True,
            tag="about_dialog",
            width=400,
            height=200,
            pos=[config.window.width // 2 - 200, config.window.height // 2 - 100]
        ):
            dpg.add_text("Birthright Campaign Manager", color=(200, 180, 140))
            dpg.add_text("Version 1.0.0")
            dpg.add_spacer(height=10)
            dpg.add_text("A solo play tool for Birthright D&D campaigns.")
            dpg.add_text("Part of the Oracle project.")
            dpg.add_spacer(height=20)
            dpg.add_button(
                label="OK",
                callback=lambda: dpg.delete_item("about_dialog"),
                width=-1
            )

    def _exit(self):
        """Exit the application."""
        self._save_game()
        dpg.stop_dearpygui()


def main():
    """Entry point for the application."""
    app = BirthrightApp()
    app.run()


if __name__ == "__main__":
    main()
