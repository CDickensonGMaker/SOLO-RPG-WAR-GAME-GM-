"""
GUI Views - Visual components and panels for the Oracle GUI Suite.

Includes panels for both the Birthright Campaign Manager
and the unified Oracle solo GM application.
"""

# Birthright Campaign Manager panels
from oracle.gui.views.dashboard import DashboardPanel
from oracle.gui.views.event_log import EventLogPanel
from oracle.gui.views.map_view import MapTimelinePanel
from oracle.gui.views.npc_graph import NPCGraphPanel

# Oracle unified GUI panels
from oracle.gui.views.chat_panel import ChatPanel
from oracle.gui.views.session_panel import SessionPanel

__all__ = [
    # Birthright panels
    "DashboardPanel",
    "EventLogPanel",
    "MapTimelinePanel",
    "NPCGraphPanel",
    # Oracle panels
    "ChatPanel",
    "SessionPanel"
]
