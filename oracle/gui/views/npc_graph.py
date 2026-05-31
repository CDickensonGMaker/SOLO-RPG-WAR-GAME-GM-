"""
NPC Relationship Graph Panel - Visualization of NPC relationships.

Displays:
- NetworkX-based relationship graph
- Ally/rival/enemy edge coloring
- Click-to-view regent details
- Filter controls
"""

from typing import Optional, Callable, List, Dict, Any, Tuple
import dearpygui.dearpygui as dpg
import math

from oracle.gui.models.campaign import CampaignState, Relationship, RelationshipType
from oracle.gui.controllers.relationship import RelationshipController, NPCNode
from oracle.gui.config import config


class NPCGraphPanel:
    """
    Floating/dockable panel showing NPC relationship graph.

    Uses a force-directed layout to display NPCs as nodes
    with edges colored by relationship type.
    """

    def __init__(self, parent: int = None):
        self.parent = parent
        self.campaign: Optional[CampaignState] = None
        self.controller: Optional[RelationshipController] = None

        # Widget tags
        self._window_tag = None
        self._graph_drawlist_tag = None
        self._details_container_tag = None

        # Graph dimensions
        self._graph_width = 400
        self._graph_height = 300

        # Selected NPC
        self._selected_npc: Optional[str] = None

        # Filter
        self._show_unknown = False

        # Callbacks
        self._on_npc_selected: List[Callable] = []

        self._build()

    def _build(self):
        """Build the NPC graph UI."""
        # Create as a floating window that can be toggled
        with dpg.window(
            label="NPC Relationships",
            width=500,
            height=450,
            show=False,
            tag="npc_graph_window",
            on_close=self.hide
        ):
            self._window_tag = dpg.last_item()

            # Filter controls
            with dpg.group(horizontal=True):
                dpg.add_text("Filter:")
                dpg.add_checkbox(
                    label="Show Unknown",
                    default_value=False,
                    callback=self._on_filter_changed
                )
                dpg.add_button(
                    label="Refresh",
                    callback=self.refresh,
                    small=True
                )

            dpg.add_separator()

            # Split view: graph left, details right
            with dpg.group(horizontal=True):
                # Graph area
                with dpg.child_window(width=self._graph_width, height=self._graph_height + 50):
                    dpg.add_text("Relationship Graph", color=(200, 180, 140))
                    with dpg.drawlist(
                        width=self._graph_width - 10,
                        height=self._graph_height,
                        tag="npc_graph_drawlist"
                    ):
                        self._graph_drawlist_tag = dpg.last_item()

                # Details area
                with dpg.child_window(width=-1, height=self._graph_height + 50):
                    dpg.add_text("NPC Details", color=(200, 180, 140))
                    dpg.add_separator()
                    self._details_container_tag = dpg.add_group(tag="npc_details_container")

            # Summary section
            dpg.add_separator()
            dpg.add_text("Summary", color=(200, 180, 140))
            self._summary_container_tag = dpg.add_group(tag="npc_summary_container")

    def set_campaign(self, campaign: CampaignState):
        """Set the active campaign and initialize controller."""
        self.campaign = campaign
        if campaign:
            self.controller = RelationshipController(campaign)
        else:
            self.controller = None
        self.refresh()

    def show(self):
        """Show the NPC graph window."""
        dpg.show_item(self._window_tag)
        self.refresh()

    def hide(self):
        """Hide the NPC graph window."""
        dpg.hide_item(self._window_tag)

    def toggle(self):
        """Toggle window visibility."""
        if dpg.is_item_shown(self._window_tag):
            self.hide()
        else:
            self.show()

    def refresh(self):
        """Refresh the graph and details."""
        self._draw_graph()
        self._refresh_details()
        self._refresh_summary()

    def _draw_graph(self):
        """Draw the relationship graph."""
        if not self._graph_drawlist_tag:
            return

        dpg.delete_item(self._graph_drawlist_tag, children_only=True)

        if not self.controller:
            dpg.draw_text(
                (10, 50),
                "No campaign active",
                color=(150, 150, 150),
                size=14,
                parent=self._graph_drawlist_tag
            )
            return

        # Get graph data
        graph_data = self.controller.build_graph_data()

        # Draw background
        dpg.draw_rectangle(
            (0, 0),
            (self._graph_width - 10, self._graph_height),
            fill=(30, 35, 40, 255),
            parent=self._graph_drawlist_tag
        )

        # Draw edges first
        for edge in graph_data["edges"]:
            source_node = next((n for n in graph_data["nodes"] if n.id == edge.source), None)
            target_node = next((n for n in graph_data["nodes"] if n.id == edge.target), None)

            if source_node and target_node:
                pos1 = self._graph_to_screen(source_node.position)
                pos2 = self._graph_to_screen(target_node.position)

                # Convert color tuple to int
                color = tuple(int(c * 255) for c in edge.color[:3]) + (int(edge.color[3] * 150),)

                dpg.draw_line(
                    pos1, pos2,
                    color=color,
                    thickness=max(1, int(edge.weight * 3)),
                    parent=self._graph_drawlist_tag
                )

        # Draw nodes
        for node in graph_data["nodes"]:
            if not node.known and not self._show_unknown:
                continue

            pos = self._graph_to_screen(node.position)
            color = tuple(int(c * 255) for c in node.color)

            # Node size varies by type
            radius = 15 if node.id == "player" else 10

            # Draw node
            dpg.draw_circle(
                pos,
                radius,
                fill=color,
                color=(200, 200, 200, 255) if node.id == self._selected_npc else (100, 100, 100, 255),
                thickness=2 if node.id == self._selected_npc else 1,
                parent=self._graph_drawlist_tag
            )

            # Draw label
            label_pos = (pos[0] - len(node.name) * 3, pos[1] + radius + 5)
            dpg.draw_text(
                label_pos,
                node.name,
                color=(180, 180, 180, 255),
                size=10,
                parent=self._graph_drawlist_tag
            )

    def _graph_to_screen(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert normalized graph position to screen coordinates."""
        x = int(pos[0] * (self._graph_width - 30)) + 15
        y = int(pos[1] * (self._graph_height - 30)) + 15
        return (x, y)

    def _refresh_details(self):
        """Refresh the NPC details panel."""
        dpg.delete_item(self._details_container_tag, children_only=True)

        if not self.controller or not self._selected_npc:
            dpg.add_text(
                "Click an NPC to view details",
                parent=self._details_container_tag,
                color=(150, 150, 150)
            )
            return

        rel = self.controller.get_relationship(self._selected_npc)
        if not rel:
            return

        formatted = self.controller.format_relationship_for_display(rel)

        with dpg.group(parent=self._details_container_tag):
            # Name
            dpg.add_text(formatted["npc_name"], color=(255, 255, 255))

            # Relationship type
            type_color = formatted["color"]
            type_color_int = tuple(int(c * 255) for c in type_color[:3])
            dpg.add_text(
                formatted["type_label"],
                color=type_color_int
            )

            dpg.add_spacer(height=5)

            # Disposition bar
            dpg.add_text(f"Disposition: {formatted['disposition']}")

            # Simple bar representation
            bar_value = formatted["disposition_bar"]
            bar_width = 150
            filled = int(bar_width * bar_value)

            with dpg.drawlist(width=bar_width + 4, height=15):
                # Background
                dpg.draw_rectangle(
                    (0, 0), (bar_width + 4, 15),
                    fill=(50, 50, 50, 255)
                )
                # Midline
                dpg.draw_line(
                    (bar_width // 2 + 2, 0),
                    (bar_width // 2 + 2, 15),
                    color=(100, 100, 100, 255)
                )
                # Fill
                if filled > 0:
                    fill_color = type_color_int + (255,)
                    dpg.draw_rectangle(
                        (2, 2), (2 + filled, 13),
                        fill=fill_color
                    )

            dpg.add_spacer(height=5)

            # Description
            desc = self.controller.get_disposition_description(formatted["disposition"])
            dpg.add_text(desc, color=(180, 180, 180), wrap=180)

            # Recent notes
            if formatted["recent_notes"]:
                dpg.add_spacer(height=10)
                dpg.add_text("Recent Changes:", color=(150, 150, 150))
                for note in formatted["recent_notes"]:
                    dpg.add_text(f"  {note}", color=(120, 120, 120))

    def _refresh_summary(self):
        """Refresh the summary section."""
        dpg.delete_item(self._summary_container_tag, children_only=True)

        if not self.controller:
            return

        summary = self.controller.get_relationship_summary()

        with dpg.group(parent=self._summary_container_tag, horizontal=True):
            self._add_summary_item("Allies", summary["ally"] + summary["devoted"], (100, 200, 100))
            self._add_summary_item("Friendly", summary["friendly"], (150, 200, 150))
            self._add_summary_item("Neutral", summary["neutral"], (150, 150, 150))
            self._add_summary_item("Hostile", summary["hostile"], (200, 150, 100))
            self._add_summary_item("Enemies", summary["enemy"], (200, 80, 80))

    def _add_summary_item(self, label: str, count: int, color: Tuple[int, int, int]):
        """Add a summary item."""
        dpg.add_text(f"{label}: {count}", color=color)
        dpg.add_spacer(width=15)

    def _on_filter_changed(self, sender, value):
        """Handle filter checkbox change."""
        self._show_unknown = value
        self._draw_graph()

    def select_npc(self, npc_id: str):
        """Select an NPC to show details."""
        self._selected_npc = npc_id
        self._draw_graph()
        self._refresh_details()

        for callback in self._on_npc_selected:
            callback(npc_id)

    def on_npc_selected(self, callback: Callable):
        """Register callback for NPC selection."""
        self._on_npc_selected.append(callback)
