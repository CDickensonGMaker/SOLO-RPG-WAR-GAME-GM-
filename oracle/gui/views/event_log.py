"""
Event Log Panel - Central panel showing events, choices, and history.

Displays:
- Current pending event with choice buttons
- Scrolling event history
- Event severity icons
- Category filtering
"""

from typing import Optional, Callable, List, Dict, Any
import dearpygui.dearpygui as dpg

from oracle.gui.models.campaign import (
    CampaignState, DomainEvent, EventChoice, EventSeverity
)
from oracle.gui.config import config


class EventLogPanel:
    """
    Central panel displaying campaign events and history.

    Shows the current pending event with clickable choice buttons,
    and maintains a scrolling log of past events and outcomes.
    """

    def __init__(self, parent: int):
        self.parent = parent
        self.campaign: Optional[CampaignState] = None

        # Widget tags
        self._event_container_tag = None
        self._history_container_tag = None
        self._current_event_tag = None

        # Callbacks
        self._on_choice: List[Callable] = []
        self._on_oracle_request: List[Callable] = []

        # Current event being displayed
        self._current_event: Optional[DomainEvent] = None

        self._build()

    def _build(self):
        """Build the event log UI."""
        width = int(config.window.width * config.window.event_log_width)

        with dpg.child_window(
            parent=self.parent,
            width=width,
            height=-1,
            tag="event_log_panel"
        ):
            # Current Event Section
            dpg.add_text("CURRENT EVENT", color=(200, 180, 140))
            dpg.add_separator()

            self._event_container_tag = dpg.add_group(tag="event_container")

            # Show empty state
            with dpg.group(parent=self._event_container_tag):
                dpg.add_text(
                    "No pending events",
                    color=(150, 150, 150),
                    tag="no_event_text"
                )

            dpg.add_spacer(height=20)

            # Event History Section
            dpg.add_text("EVENT HISTORY", color=(200, 180, 140))
            dpg.add_separator()

            # Filter buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="All",
                    callback=lambda: self._filter_history("all"),
                    small=True
                )
                dpg.add_button(
                    label="Story",
                    callback=lambda: self._filter_history("story"),
                    small=True
                )
                dpg.add_button(
                    label="Random",
                    callback=lambda: self._filter_history("random"),
                    small=True
                )
                dpg.add_button(
                    label="Choices",
                    callback=lambda: self._filter_history("choices"),
                    small=True
                )

            dpg.add_spacer(height=5)

            # Scrollable history container
            with dpg.child_window(
                height=-1,
                border=False,
                tag="history_scroll"
            ):
                self._history_container_tag = dpg.add_group(tag="history_container")

    def set_campaign(self, campaign: CampaignState):
        """Set the active campaign and refresh display."""
        self.campaign = campaign
        self.refresh()

    def refresh(self):
        """Refresh the entire panel."""
        self._refresh_current_event()
        self._refresh_history()

    def _refresh_current_event(self):
        """Refresh current event display."""
        # Clear existing content
        dpg.delete_item(self._event_container_tag, children_only=True)

        if not self.campaign or not self.campaign.pending_event:
            dpg.add_text(
                "No pending events",
                parent=self._event_container_tag,
                color=(150, 150, 150)
            )
            return

        event = self.campaign.pending_event
        self._current_event = event

        with dpg.group(parent=self._event_container_tag):
            # Event header with severity indicator
            severity_color = self._get_severity_color(event.severity)

            with dpg.group(horizontal=True):
                # Severity indicator
                dpg.add_text("●", color=severity_color)
                dpg.add_text(event.name, color=(255, 255, 255))

            dpg.add_spacer(height=5)

            # Event type and turn
            dpg.add_text(
                f"[{event.event_type.upper()}] Turn {self.campaign.turn.turn_number}",
                color=(150, 150, 150)
            )

            dpg.add_spacer(height=10)

            # Event description
            # Wrap text manually for better display
            desc_lines = self._wrap_text(event.description, 60)
            for line in desc_lines:
                dpg.add_text(line, color=(220, 220, 210))

            dpg.add_spacer(height=15)

            # Choices
            dpg.add_text("CHOICES:", color=(200, 180, 140))
            dpg.add_spacer(height=5)

            for i, choice in enumerate(event.choices):
                with dpg.group(horizontal=False):
                    # Choice button
                    btn_color = (80, 80, 100) if choice.difficulty == "hard" else (60, 80, 60)

                    dpg.add_button(
                        label=f"{i+1}. {choice.text}",
                        callback=lambda s, a, c=choice: self._on_choice_clicked(c),
                        width=-1
                    )

                    # Difficulty indicator
                    if choice.difficulty != "normal":
                        dpg.add_text(
                            f"  [{choice.difficulty.upper()}]",
                            color=(200, 150, 100)
                        )

                    # Consequence preview if available
                    if choice.consequences:
                        dpg.add_text(
                            f"  → {choice.consequences}",
                            color=(150, 150, 150)
                        )

                    dpg.add_spacer(height=3)

            # Oracle prompt button if any choice has one
            has_oracle = any(c.oracle_prompt for c in event.choices)
            if has_oracle:
                dpg.add_spacer(height=10)
                dpg.add_button(
                    label="Ask the Oracle",
                    callback=self._on_oracle_clicked,
                    width=-1
                )

    def _refresh_history(self):
        """Refresh event history display."""
        dpg.delete_item(self._history_container_tag, children_only=True)

        if not self.campaign:
            return

        # Show events in reverse chronological order
        history = list(reversed(self.campaign.event_history[-20:]))  # Last 20 events

        if not history:
            dpg.add_text(
                "No events yet",
                parent=self._history_container_tag,
                color=(150, 150, 150)
            )
            return

        for entry in history:
            self._add_history_entry(entry)

    def _add_history_entry(self, entry: Dict[str, Any]):
        """Add a history entry to the display."""
        with dpg.group(parent=self._history_container_tag):
            # Header line with turn and event name
            with dpg.group(horizontal=True):
                dpg.add_text(
                    f"T{entry.get('turn', '?')}",
                    color=(100, 100, 150)
                )
                dpg.add_text(
                    entry.get('event_name', 'Unknown Event'),
                    color=(200, 200, 200)
                )

            # Choice made
            choice = entry.get('choice', '')
            if choice:
                dpg.add_text(
                    f"  Choice: {choice}",
                    color=(150, 180, 150)
                )

            # Outcome summary
            outcome = entry.get('outcome', '')
            if outcome:
                # Truncate long outcomes
                if len(outcome) > 80:
                    outcome = outcome[:77] + "..."
                dpg.add_text(
                    f"  → {outcome}",
                    color=(150, 150, 150)
                )

            dpg.add_separator()

    def _get_severity_color(self, severity: EventSeverity) -> tuple:
        """Get color for event severity."""
        colors = {
            EventSeverity.FLAVOR: (128, 128, 128),
            EventSeverity.MINOR: (100, 180, 100),
            EventSeverity.MODERATE: (200, 200, 100),
            EventSeverity.MAJOR: (230, 150, 80),
            EventSeverity.CRITICAL: (230, 80, 80),
        }
        return colors.get(severity, (128, 128, 128))

    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to specified width."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def _on_choice_clicked(self, choice: EventChoice):
        """Handle choice button click."""
        for callback in self._on_choice:
            callback(self._current_event, choice)

    def _on_oracle_clicked(self):
        """Handle oracle button click."""
        if self._current_event:
            for callback in self._on_oracle_request:
                callback(self._current_event)

    def _filter_history(self, filter_type: str):
        """Filter history display."""
        # Would implement actual filtering
        self._refresh_history()

    def on_choice_selected(self, callback: Callable):
        """Register callback for choice selection."""
        self._on_choice.append(callback)

    def on_oracle_requested(self, callback: Callable):
        """Register callback for oracle requests."""
        self._on_oracle_request.append(callback)

    def show_event(self, event: DomainEvent):
        """Display a specific event."""
        if self.campaign:
            self.campaign.pending_event = event
            self._refresh_current_event()

    def add_to_history(self, entry: Dict[str, Any]):
        """Add an entry to the history."""
        self._add_history_entry(entry)

    def show_oracle_result(self, result: Dict[str, Any]):
        """Display oracle roll result."""
        # Add to current event display or show as popup
        if dpg.does_item_exist("oracle_result_popup"):
            dpg.delete_item("oracle_result_popup")

        with dpg.window(
            label="Oracle Result",
            modal=True,
            tag="oracle_result_popup",
            width=400,
            height=200,
            pos=[
                config.window.width // 2 - 200,
                config.window.height // 2 - 100
            ]
        ):
            dpg.add_text(f"Question: {result.get('prompt', '')}")
            dpg.add_spacer(height=10)

            answer_text = result.get('answer_text', 'Unknown')
            answer_color = (100, 200, 100) if 'YES' in answer_text else (200, 100, 100)
            dpg.add_text(
                answer_text,
                color=answer_color
            )

            dpg.add_spacer(height=5)
            dpg.add_text(
                f"Roll: {result.get('roll', 0)} (Chaos: {result.get('chaos_factor', 5)})",
                color=(150, 150, 150)
            )

            if result.get('random_event_triggered'):
                dpg.add_text(
                    "Random event triggered!",
                    color=(255, 200, 100)
                )

            dpg.add_spacer(height=15)
            dpg.add_button(
                label="OK",
                callback=lambda: dpg.delete_item("oracle_result_popup"),
                width=-1
            )
