"""
Domain Action Dialog - Modal for selecting and executing domain actions.

Features:
- Action selection grid
- Target pickers
- Cost/requirement display
- Oracle roll integration
"""

from typing import Optional, Callable, List, Dict, Any
import dearpygui.dearpygui as dpg

from oracle.gui.models.campaign import CampaignState
from oracle.gui.config import config


class DomainActionDialog:
    """
    Modal dialog for executing domain actions.

    Domain actions are the regent-level actions that shape realms:
    diplomacy, military, espionage, domain management, etc.
    """

    def __init__(self, campaign: Optional[CampaignState] = None):
        self.campaign = campaign

        # Widget tags
        self._window_tag = None
        self._action_grid_tag = None
        self._details_tag = None
        self._target_tag = None

        # Selection state
        self._selected_action: Optional[str] = None
        self._selected_target: Optional[str] = None

        # Action definitions
        self._actions = self._define_actions()

        # Callbacks
        self._on_action_executed: List[Callable] = []

        self._build()

    def _define_actions(self) -> Dict[str, Dict[str, Any]]:
        """Define available domain actions."""
        return {
            # Administrative Actions
            "rule": {
                "name": "Rule Province",
                "category": "administrative",
                "cost": {"rp": 1, "gb": 0},
                "description": "Increase a province's level through governance",
                "dc": 15,
                "requires_target": True,
                "target_type": "province"
            },
            "create_holding": {
                "name": "Create Holding",
                "category": "administrative",
                "cost": {"rp": 2, "gb": 5},
                "description": "Establish a new holding in a province",
                "dc": 15,
                "requires_target": True,
                "target_type": "province"
            },

            # Diplomatic Actions
            "diplomacy": {
                "name": "Diplomacy",
                "category": "diplomatic",
                "cost": {"rp": 1, "gb": 1},
                "description": "Negotiate with another regent",
                "dc": "varies",
                "requires_target": True,
                "target_type": "regent"
            },
            "decree": {
                "name": "Decree",
                "category": "diplomatic",
                "cost": {"rp": 2, "gb": 0},
                "description": "Issue an official proclamation",
                "dc": 12,
                "requires_target": False
            },

            # Military Actions
            "muster_armies": {
                "name": "Muster Armies",
                "category": "military",
                "cost": {"rp": 0, "gb": "varies"},
                "description": "Raise military forces",
                "dc": 10,
                "requires_target": True,
                "target_type": "province"
            },
            "fortify": {
                "name": "Fortify",
                "category": "military",
                "cost": {"rp": 1, "gb": 10},
                "description": "Build or improve fortifications",
                "dc": 15,
                "requires_target": True,
                "target_type": "province"
            },
            "move_troops": {
                "name": "Move Troops",
                "category": "military",
                "cost": {"rp": 0, "gb": 0},
                "description": "Relocate military units",
                "dc": 0,
                "requires_target": True,
                "target_type": "province"
            },

            # Espionage Actions
            "espionage": {
                "name": "Espionage",
                "category": "covert",
                "cost": {"rp": 1, "gb": 2},
                "description": "Gather intelligence or conduct sabotage",
                "dc": "contested",
                "requires_target": True,
                "target_type": "regent"
            },
            "assassinate": {
                "name": "Assassinate",
                "category": "covert",
                "cost": {"rp": 3, "gb": 10},
                "description": "Eliminate a target (extreme risk)",
                "dc": 20,
                "requires_target": True,
                "target_type": "npc"
            },

            # Economic Actions
            "trade_route": {
                "name": "Trade Route",
                "category": "economic",
                "cost": {"rp": 1, "gb": 3},
                "description": "Establish a trade agreement",
                "dc": 12,
                "requires_target": True,
                "target_type": "regent"
            },
            "contest_holding": {
                "name": "Contest Holding",
                "category": "economic",
                "cost": {"rp": 2, "gb": 2},
                "description": "Challenge another regent's holding",
                "dc": "contested",
                "requires_target": True,
                "target_type": "holding"
            },

            # Magical Actions
            "realm_spell": {
                "name": "Cast Realm Spell",
                "category": "magical",
                "cost": {"rp": "varies", "gb": "varies"},
                "description": "Invoke powerful realm magic",
                "dc": "varies",
                "requires_target": True,
                "target_type": "varies"
            },
            "ley_line": {
                "name": "Forge Ley Line",
                "category": "magical",
                "cost": {"rp": 3, "gb": 5},
                "description": "Create magical connection between sources",
                "dc": 18,
                "requires_target": True,
                "target_type": "source"
            },
        }

    def _build(self):
        """Build the dialog UI."""
        with dpg.window(
            label="Domain Actions",
            modal=True,
            show=False,
            width=650,
            height=450,
            tag="domain_action_dialog",
            pos=[config.window.width // 2 - 325, config.window.height // 2 - 225],
            on_close=self.hide
        ):
            self._window_tag = dpg.last_item()

            with dpg.group(horizontal=True):
                # Action grid (left side)
                with dpg.child_window(width=280, height=-50):
                    dpg.add_text("Select Action", color=(200, 180, 140))
                    dpg.add_separator()

                    # Category tabs
                    with dpg.tab_bar():
                        for category in ["administrative", "diplomatic", "military", "covert", "economic", "magical"]:
                            with dpg.tab(label=category.title()[:6]):
                                self._build_action_list(category)

                # Details and target (right side)
                with dpg.child_window(width=-1, height=-50):
                    dpg.add_text("Action Details", color=(200, 180, 140))
                    dpg.add_separator()

                    self._details_tag = dpg.add_group(tag="action_details")

                    dpg.add_spacer(height=20)

                    dpg.add_text("Target", color=(200, 180, 140))
                    dpg.add_separator()

                    self._target_tag = dpg.add_group(tag="action_target")

            # Bottom buttons
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Execute Action",
                    callback=self._on_execute_clicked,
                    width=150
                )
                dpg.add_button(
                    label="Ask Oracle",
                    callback=self._on_oracle_clicked,
                    width=100
                )
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Cancel",
                    callback=self.hide,
                    width=100
                )

    def _build_action_list(self, category: str):
        """Build action list for a category."""
        actions_in_cat = [
            (aid, a) for aid, a in self._actions.items()
            if a["category"] == category
        ]

        for action_id, action in actions_in_cat:
            dpg.add_selectable(
                label=action["name"],
                callback=lambda s, a, aid=action_id: self._on_action_selected(aid)
            )

    def _on_action_selected(self, action_id: str):
        """Handle action selection."""
        self._selected_action = action_id
        self._refresh_details()
        self._refresh_target()

    def _refresh_details(self):
        """Refresh action details display."""
        dpg.delete_item(self._details_tag, children_only=True)

        if not self._selected_action:
            dpg.add_text(
                "Select an action",
                parent=self._details_tag,
                color=(150, 150, 150)
            )
            return

        action = self._actions[self._selected_action]

        with dpg.group(parent=self._details_tag):
            dpg.add_text(action["name"], color=(255, 255, 255))

            dpg.add_spacer(height=5)

            # Description
            dpg.add_text(action["description"], wrap=200, color=(180, 180, 180))

            dpg.add_spacer(height=10)

            # Cost
            cost = action["cost"]
            rp_cost = cost.get("rp", 0)
            gb_cost = cost.get("gb", 0)

            dpg.add_text("Cost:", color=(200, 180, 140))
            dpg.add_text(
                f"  RP: {rp_cost}  |  GB: {gb_cost}",
                color=(220, 200, 100)
            )

            # DC
            dc = action.get("dc", "varies")
            dpg.add_text(f"  DC: {dc}", color=(180, 180, 180))

            dpg.add_spacer(height=10)

            # Current resources (if campaign set)
            if self.campaign:
                current_rp = self.campaign.variables.get("regency_points", 0)
                current_gb = self.campaign.variables.get("gold_bars", 0)

                can_afford = True
                if isinstance(rp_cost, int) and rp_cost > current_rp:
                    can_afford = False
                if isinstance(gb_cost, int) and gb_cost > current_gb:
                    can_afford = False

                dpg.add_text("Your Resources:", color=(150, 150, 150))
                dpg.add_text(f"  RP: {current_rp}  |  GB: {current_gb}")

                if not can_afford:
                    dpg.add_text("Insufficient resources!", color=(255, 100, 100))

    def _refresh_target(self):
        """Refresh target selection area."""
        dpg.delete_item(self._target_tag, children_only=True)

        if not self._selected_action:
            return

        action = self._actions[self._selected_action]

        if not action.get("requires_target", False):
            dpg.add_text(
                "No target required",
                parent=self._target_tag,
                color=(150, 150, 150)
            )
            return

        target_type = action.get("target_type", "varies")

        with dpg.group(parent=self._target_tag):
            dpg.add_text(f"Select {target_type.title()}:")

            # Target input based on type
            if target_type == "regent":
                # Would list regents from relationships
                targets = self._get_regent_targets()
                dpg.add_combo(
                    items=targets,
                    callback=self._on_target_selected,
                    width=-1
                )
            elif target_type == "province":
                # Would list provinces
                targets = self._get_province_targets()
                dpg.add_combo(
                    items=targets,
                    callback=self._on_target_selected,
                    width=-1
                )
            else:
                dpg.add_input_text(
                    hint=f"Enter {target_type}",
                    callback=self._on_target_selected,
                    width=-1
                )

    def _get_regent_targets(self) -> List[str]:
        """Get list of regent targets."""
        if self.campaign:
            return [rel.npc_name for rel in self.campaign.relationships.values()]
        return ["(No regents available)"]

    def _get_province_targets(self) -> List[str]:
        """Get list of province targets."""
        # Would come from map data
        return [
            "Imperial City", "Avanil", "Boeruine", "Mhoried",
            "Diemed", "Medoere", "Roesone", "Aerenwe"
        ]

    def _on_target_selected(self, sender, value):
        """Handle target selection."""
        self._selected_target = value

    def _on_execute_clicked(self):
        """Handle execute action button."""
        if not self._selected_action:
            return

        action = self._actions[self._selected_action]

        if action.get("requires_target") and not self._selected_target:
            # Show error
            return

        # Execute the action
        result = {
            "action": self._selected_action,
            "action_name": action["name"],
            "target": self._selected_target,
            "cost": action["cost"]
        }

        self.hide()

        for callback in self._on_action_executed:
            callback(result)

    def _on_oracle_clicked(self):
        """Handle oracle button for action resolution."""
        if not self._selected_action:
            return

        action = self._actions[self._selected_action]
        dc = action.get("dc", 15)

        prompt = f"Does the {action['name']} action succeed? (DC {dc})"

        # Would integrate with Oracle system
        # For now, just show the prompt
        pass

    def set_campaign(self, campaign: CampaignState):
        """Set the active campaign."""
        self.campaign = campaign

    def show(self):
        """Show the dialog."""
        dpg.show_item(self._window_tag)

    def hide(self):
        """Hide the dialog."""
        dpg.hide_item(self._window_tag)
        self._selected_action = None
        self._selected_target = None

    def on_action_executed(self, callback: Callable):
        """Register callback for action execution."""
        self._on_action_executed.append(callback)
