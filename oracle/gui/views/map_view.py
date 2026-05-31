"""
Map and Timeline Panel - Right panel showing Cerilia map and timeline.

Displays:
- Stylized Cerilia region map
- Province nodes with realm colors
- Turn timeline widget
- Season/year display
"""

from typing import Optional, Callable, List, Dict, Any, Tuple
import dearpygui.dearpygui as dpg
import math

from oracle.gui.models.campaign import CampaignState, Season
from oracle.gui.config import config


class MapTimelinePanel:
    """
    Right panel showing map visualization and timeline.

    The map is a simplified node-graph representation of Cerilia,
    with provinces shown as colored nodes and connections between them.
    """

    def __init__(self, parent: int):
        self.parent = parent
        self.campaign: Optional[CampaignState] = None

        # Widget tags
        self._map_drawlist_tag = None
        self._timeline_container_tag = None

        # Province data (simplified for initial implementation)
        self._provinces: Dict[str, Dict] = {}
        self._connections: List[Tuple[str, str]] = []

        # Map dimensions
        self._map_width = 0
        self._map_height = 0

        # Callbacks
        self._on_province_click: List[Callable] = []

        self._init_province_data()
        self._build()

    def _init_province_data(self):
        """Initialize province positions and data."""
        # Simplified Anuirean provinces
        self._provinces = {
            # Central Anuire
            "imperial_city": {"name": "Imperial City", "pos": (0.5, 0.45), "realm": "vacant", "level": 7},
            "avanil": {"name": "Avanil", "pos": (0.45, 0.5), "realm": "avan", "level": 6},
            "boeruine": {"name": "Boeruine", "pos": (0.35, 0.35), "realm": "boeruine", "level": 5},
            "mhoried": {"name": "Mhoried", "pos": (0.4, 0.25), "realm": "mhoried", "level": 4},
            "diemed": {"name": "Diemed", "pos": (0.55, 0.55), "realm": "diemed", "level": 5},
            "medoere": {"name": "Medoere", "pos": (0.6, 0.5), "realm": "medoere", "level": 3},
            "roesone": {"name": "Roesone", "pos": (0.65, 0.45), "realm": "roesone", "level": 4},
            "aerenwe": {"name": "Aerenwe", "pos": (0.7, 0.5), "realm": "aerenwe", "level": 4},
            "talinie": {"name": "Talinie", "pos": (0.3, 0.25), "realm": "talinie", "level": 4},
            "cariele": {"name": "Cariele", "pos": (0.25, 0.3), "realm": "cariele", "level": 3},
            "tuornen": {"name": "Tuornen", "pos": (0.5, 0.35), "realm": "tuornen", "level": 4},
            "alamie": {"name": "Alamie", "pos": (0.55, 0.4), "realm": "alamie", "level": 4},

            # Northern threats
            "gorgons_crown": {"name": "Gorgon's Crown", "pos": (0.35, 0.15), "realm": "gorgon", "level": 0},

            # Eastern
            "elinie": {"name": "Elinie", "pos": (0.65, 0.35), "realm": "elinie", "level": 4},
            "coeranys": {"name": "Coeranys", "pos": (0.7, 0.4), "realm": "coeranys", "level": 3},

            # Western forests
            "erebannien": {"name": "Erebannien", "pos": (0.2, 0.45), "realm": "sidhelien", "level": 0},

            # Southern
            "endier": {"name": "Endier", "pos": (0.6, 0.6), "realm": "endier", "level": 5},
        }

        # Province connections
        self._connections = [
            ("imperial_city", "avanil"),
            ("imperial_city", "alamie"),
            ("imperial_city", "tuornen"),
            ("avanil", "boeruine"),
            ("avanil", "diemed"),
            ("boeruine", "mhoried"),
            ("boeruine", "talinie"),
            ("mhoried", "gorgons_crown"),
            ("mhoried", "tuornen"),
            ("talinie", "cariele"),
            ("cariele", "erebannien"),
            ("tuornen", "alamie"),
            ("alamie", "elinie"),
            ("alamie", "roesone"),
            ("diemed", "medoere"),
            ("diemed", "endier"),
            ("medoere", "roesone"),
            ("roesone", "aerenwe"),
            ("elinie", "coeranys"),
            ("coeranys", "aerenwe"),
        ]

    def _build(self):
        """Build the map and timeline UI."""
        width = int(config.window.width * config.window.map_width)
        self._map_width = width - 20
        self._map_height = int(config.window.height * 0.6)

        with dpg.child_window(
            parent=self.parent,
            width=width,
            height=-1,
            tag="map_panel"
        ):
            # Map section
            dpg.add_text("CERILIA", color=(200, 180, 140))
            dpg.add_separator()

            # Draw list for map
            with dpg.drawlist(
                width=self._map_width,
                height=self._map_height,
                tag="map_drawlist"
            ):
                self._map_drawlist_tag = dpg.last_item()

            dpg.add_spacer(height=15)

            # Timeline section
            dpg.add_text("TIMELINE", color=(200, 180, 140))
            dpg.add_separator()

            self._timeline_container_tag = dpg.add_group(tag="timeline_container")

            # Legend
            dpg.add_spacer(height=10)
            dpg.add_text("LEGEND", color=(200, 180, 140))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                self._add_legend_item("Player", (100, 200, 100))
                self._add_legend_item("Ally", (100, 150, 200))
                self._add_legend_item("Neutral", (150, 150, 150))

            with dpg.group(horizontal=True):
                self._add_legend_item("Hostile", (200, 150, 100))
                self._add_legend_item("Enemy", (200, 80, 80))
                self._add_legend_item("Awnshegh", (50, 50, 50))

        self._draw_map()

    def _add_legend_item(self, label: str, color: Tuple[int, int, int]):
        """Add a legend item."""
        dpg.add_text("●", color=color)
        dpg.add_text(label, color=(180, 180, 180))
        dpg.add_spacer(width=10)

    def _draw_map(self):
        """Draw the map visualization."""
        if not self._map_drawlist_tag:
            return

        dpg.delete_item(self._map_drawlist_tag, children_only=True)

        # Background
        dpg.draw_rectangle(
            (0, 0),
            (self._map_width, self._map_height),
            fill=(30, 40, 50, 255),
            parent=self._map_drawlist_tag
        )

        # Draw connections first
        for p1, p2 in self._connections:
            if p1 in self._provinces and p2 in self._provinces:
                pos1 = self._get_screen_pos(self._provinces[p1]["pos"])
                pos2 = self._get_screen_pos(self._provinces[p2]["pos"])
                dpg.draw_line(
                    pos1, pos2,
                    color=(80, 80, 100, 200),
                    thickness=1,
                    parent=self._map_drawlist_tag
                )

        # Draw provinces
        for prov_id, data in self._provinces.items():
            self._draw_province(prov_id, data)

    def _get_screen_pos(self, normalized_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert normalized (0-1) position to screen coordinates."""
        x = int(normalized_pos[0] * self._map_width)
        y = int(normalized_pos[1] * self._map_height)
        return (x, y)

    def _get_realm_color(self, realm: str) -> Tuple[int, int, int, int]:
        """Get color for a realm."""
        colors = {
            "player": (100, 200, 100, 255),
            "avan": (180, 100, 100, 255),
            "boeruine": (100, 100, 180, 255),
            "mhoried": (150, 150, 100, 255),
            "gorgon": (40, 40, 40, 255),
            "sidhelien": (80, 180, 150, 255),
            "vacant": (100, 100, 100, 255),
        }
        return colors.get(realm, (120, 120, 120, 255))

    def _draw_province(self, prov_id: str, data: Dict):
        """Draw a single province node."""
        pos = self._get_screen_pos(data["pos"])
        color = self._get_realm_color(data["realm"])
        level = data["level"]

        # Node size based on province level
        radius = 8 + level

        # Draw node
        dpg.draw_circle(
            pos,
            radius,
            fill=color,
            color=(200, 200, 200, 255),
            thickness=1,
            parent=self._map_drawlist_tag
        )

        # Draw label
        label_pos = (pos[0] - 20, pos[1] + radius + 5)
        dpg.draw_text(
            label_pos,
            data["name"],
            color=(180, 180, 180, 255),
            size=10,
            parent=self._map_drawlist_tag
        )

    def set_campaign(self, campaign: CampaignState):
        """Set the active campaign and refresh display."""
        self.campaign = campaign
        self._update_province_ownership()
        self._draw_map()
        self._refresh_timeline()

    def _update_province_ownership(self):
        """Update province ownership based on campaign state."""
        if not self.campaign:
            return

        # Would update province colors based on campaign variables
        # For now, provinces keep their default colors
        pass

    def _refresh_timeline(self):
        """Refresh the timeline display."""
        dpg.delete_item(self._timeline_container_tag, children_only=True)

        if not self.campaign:
            dpg.add_text(
                "No active campaign",
                parent=self._timeline_container_tag,
                color=(150, 150, 150)
            )
            return

        turn = self.campaign.turn

        with dpg.group(parent=self._timeline_container_tag):
            # Year and season display
            season_emoji = {
                Season.SPRING: "🌱",
                Season.SUMMER: "☀️",
                Season.AUTUMN: "🍂",
                Season.WINTER: "❄️"
            }

            dpg.add_text(
                f"{turn.year} MR - {turn.season.value.title()}",
                color=(220, 200, 160)
            )

            dpg.add_spacer(height=5)

            # Turn progress bar
            turns_in_act = self._get_act_turn_range()
            if turns_in_act:
                progress = (turn.turn_number - turns_in_act[0]) / max(1, turns_in_act[1] - turns_in_act[0])
                progress = min(1.0, max(0.0, progress))

                dpg.add_text(f"Act {self.campaign.current_act} Progress:")

                # Progress bar (simplified)
                bar_width = 200
                filled = int(bar_width * progress)

                with dpg.drawlist(width=bar_width + 4, height=20):
                    dpg.draw_rectangle(
                        (0, 5), (bar_width + 4, 15),
                        color=(100, 100, 100, 255),
                        fill=(50, 50, 50, 255)
                    )
                    if filled > 0:
                        dpg.draw_rectangle(
                            (2, 7), (2 + filled, 13),
                            fill=(150, 120, 80, 255)
                        )

            # Recent turns
            dpg.add_spacer(height=10)
            dpg.add_text("Recent History:", color=(150, 150, 150))

            for entry in self.campaign.event_history[-5:]:
                turn_num = entry.get("turn", "?")
                event_name = entry.get("event_name", "Unknown")
                dpg.add_text(
                    f"  T{turn_num}: {event_name[:30]}...",
                    color=(120, 120, 120)
                )

    def _get_act_turn_range(self) -> Optional[Tuple[int, int]]:
        """Get the turn range for the current act."""
        # Would load from campaign data
        act_ranges = {
            1: (1, 12),
            2: (13, 30),
            3: (31, 48)
        }
        if self.campaign:
            return act_ranges.get(self.campaign.current_act)
        return None

    def on_province_clicked(self, callback: Callable):
        """Register callback for province clicks."""
        self._on_province_click.append(callback)

    def highlight_province(self, province_id: str):
        """Highlight a specific province on the map."""
        # Would add highlight effect
        self._draw_map()

    def set_province_owner(self, province_id: str, owner: str):
        """Update the owner of a province."""
        if province_id in self._provinces:
            self._provinces[province_id]["realm"] = owner
            self._draw_map()

    def refresh(self):
        """Refresh the entire panel."""
        self._draw_map()
        self._refresh_timeline()
