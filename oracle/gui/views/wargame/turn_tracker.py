"""
Turn Tracker - Turn and phase management.

Provides:
- Turn number display
- Phase indicator with phase-specific highlights
- Next Phase / Next Turn buttons
- Turn history log
- Phase-appropriate action suggestions
- Battle events display with consequences
- Dynamic phase loading from game system TOML files
"""

from typing import Callable, Optional, List
from dataclasses import dataclass
import dearpygui.dearpygui as dpg

from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.gui.models.wargame_data import get_wargame_data, WargameDataModel


@dataclass
class BattleEvent:
    """A battle event with optional consequences."""
    text: str
    turn: int
    phase: str
    consequence: Optional[str] = None
    affects_units: List[str] = None

    def __post_init__(self):
        if self.affects_units is None:
            self.affects_units = []


# Callback types
PhaseChangeCallback = Callable[[str, int], None]  # (phase_name, turn_number)
EventCallback = Callable[[BattleEvent], None]


class TurnTrackerPanel:
    """
    Panel for tracking turns and phases during battle.

    Shows current turn and phase, with controls to advance
    and a log of turn history. Dynamically loads phases from
    the current game system's TOML configuration.
    """

    # Default fallback phases if no system is loaded
    DEFAULT_PHASES = [
        "Movement",
        "Shooting",
        "Combat",
        "Morale",
    ]

    # Phase color mappings (keys are lowercase for flexible matching)
    PHASE_COLORS = {
        "movement": (100, 180, 100),
        "psychic": (180, 100, 200),
        "shooting": (200, 140, 100),
        "assault": (200, 100, 100),
        "combat": (200, 100, 100),
        "melee": (200, 100, 100),
        "rally": (100, 140, 180),
        "morale": (180, 180, 100),
        "charge": (200, 160, 100),
        "initiative": (140, 180, 200),
        "activation": (160, 200, 160),
        "action": (160, 200, 160),
        "actions": (160, 200, 160),
        "round": (140, 160, 180),
        "end": (120, 120, 140),
        "unit activation": (160, 200, 160),
        "melee combat": (200, 100, 100),
        "movement phase": (100, 180, 100),
        "shooting phase": (200, 140, 100),
        "close combat phase": (200, 100, 100),
        "psychology phase": (180, 100, 200),
        "round structure": (140, 160, 180),
    }

    def __init__(
        self,
        parent: str,
        on_phase_change: Optional[PhaseChangeCallback] = None,
        on_event: Optional[EventCallback] = None,
        phases: Optional[list[str]] = None,
        width: int = -1,
    ):
        """
        Create the turn tracker panel.

        Args:
            parent: Parent DearPyGui item tag
            on_phase_change: Callback when phase changes
            on_event: Callback when a battle event occurs
            phases: Custom phase list (loads from system TOML if None)
            width: Panel width
        """
        self.parent = parent
        self._on_phase_change = on_phase_change
        self._on_event = on_event
        self.width = width

        # Get wargame data model for phase loading
        self._wargame_data = get_wargame_data()

        # Load phases from game system or use provided/default
        if phases:
            self._phases = phases.copy()
        else:
            self._phases = self._load_phases_from_system()

        # Store phase details for tooltips
        self._phase_details = self._wargame_data.get_phase_details()
        self._turn_structure = self._wargame_data.get_turn_structure()

        self._battle = get_battle_roster()

        # Battle events history
        self._events: List[BattleEvent] = []

        # UI tags
        self._tag = f"turn_tracker_{id(self)}"
        self._turn_tag = f"{self._tag}_turn"
        self._phase_tag = f"{self._tag}_phase"
        self._phase_desc_tag = f"{self._tag}_phase_desc"
        self._actions_tag = f"{self._tag}_actions"
        self._log_tag = f"{self._tag}_log"
        self._events_tag = f"{self._tag}_events"
        self._phase_buttons_tag = f"{self._tag}_phase_buttons"
        self._turn_structure_tag = f"{self._tag}_turn_structure"

        # Update battle state with our phases
        self._battle.battle_state.phases = self._phases.copy()

        # Register observers
        self._battle.add_roster_observer(self._on_roster_changed)
        self._wargame_data.add_observer(self._on_system_changed)

        self._build()

    def _load_phases_from_system(self) -> List[str]:
        """Load phases from the current game system."""
        phases = self._wargame_data.get_phases()
        if phases:
            return phases
        return self.DEFAULT_PHASES.copy()

    def _get_phase_color(self, phase_name: str) -> tuple:
        """Get color for a phase name."""
        key = phase_name.lower()
        if key in self.PHASE_COLORS:
            return self.PHASE_COLORS[key]
        # Try partial match
        for color_key, color in self.PHASE_COLORS.items():
            if color_key in key or key in color_key:
                return color
        return (150, 150, 150)  # Default gray

    def _get_phase_actions(self, phase_name: str) -> List[str]:
        """Get action suggestions for a phase."""
        # Look up in phase details
        for detail in self._phase_details:
            if detail.get("name", "").lower() == phase_name.lower():
                actions = detail.get("available_actions", [])
                if actions:
                    return actions
                steps = detail.get("steps", [])
                if steps:
                    # Convert steps to action strings
                    return [s if isinstance(s, str) else s.get("action", str(s)) for s in steps[:5]]
        return [f"Execute {phase_name} phase actions"]

    def _on_system_changed(self, event: str, data):
        """Handle game system change - reload phases."""
        if event == "system_changed":
            self._phases = self._load_phases_from_system()
            self._phase_details = self._wargame_data.get_phase_details()
            self._turn_structure = self._wargame_data.get_turn_structure()

            # Update battle state
            self._battle.battle_state.phases = self._phases.copy()
            if self._battle.battle_state.current_phase not in self._phases:
                self._battle.battle_state.current_phase = self._phases[0] if self._phases else "Movement"

            # Rebuild UI
            self._rebuild_phase_buttons()
            self._update_display()

    def _build(self):
        """Build the UI components."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            dpg.add_text("Turn Tracker", color=(200, 160, 120))
            dpg.add_separator()

            # Turn structure info (shows if alternating activation, etc.)
            turn_name = self._turn_structure.get("name", "")
            if turn_name and turn_name != "Standard":
                dpg.add_text(
                    f"[{turn_name}]",
                    tag=self._turn_structure_tag,
                    color=(140, 140, 180),
                )
                dpg.add_spacer(height=3)

            # Turn and Phase display
            with dpg.group(horizontal=True):
                dpg.add_text("Turn:", color=(150, 150, 150))
                dpg.add_text("1", tag=self._turn_tag, color=(220, 200, 160))

                dpg.add_spacer(width=20)

                dpg.add_text("Phase:", color=(150, 150, 150))
                first_phase = self._phases[0] if self._phases else "Unknown"
                dpg.add_text(
                    first_phase,
                    tag=self._phase_tag,
                    color=self._get_phase_color(first_phase),
                )

            dpg.add_spacer(height=5)

            # Phase selector buttons (in a group that can be rebuilt)
            with dpg.group(tag=self._phase_buttons_tag):
                self._render_phase_buttons()

            dpg.add_spacer(height=8)

            # Phase actions
            with dpg.collapsing_header(label="Phase Actions", default_open=True):
                with dpg.group(tag=self._actions_tag):
                    self._render_phase_actions()

            # Controls
            dpg.add_spacer(height=5)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Next Phase",
                    callback=self._next_phase,
                    width=100,
                )
                dpg.add_button(
                    label="Next Turn",
                    callback=self._next_turn,
                    width=100,
                )

            # Battle Events
            dpg.add_spacer(height=8)
            with dpg.collapsing_header(label="Battle Events", default_open=True):
                with dpg.child_window(height=120, border=True, tag=self._events_tag):
                    dpg.add_text("No events yet", color=(100, 100, 100))

            # Turn log
            dpg.add_spacer(height=8)
            with dpg.collapsing_header(label="Turn Log", default_open=False):
                with dpg.child_window(height=100, border=False, tag=self._log_tag):
                    dpg.add_text("Battle started", color=(100, 100, 100))

    def _render_phase_buttons(self):
        """Render phase selector buttons."""
        # Calculate button width based on number of phases
        num_phases = len(self._phases)
        if num_phases <= 4:
            btn_width = 60
        elif num_phases <= 6:
            btn_width = 45
        else:
            btn_width = 35

        with dpg.group(horizontal=True, parent=self._phase_buttons_tag):
            for phase in self._phases:
                # Abbreviate phase name for button
                label = phase[:4] if len(phase) > 4 else phase
                dpg.add_button(
                    label=label,
                    callback=lambda s, a, p=phase: self._set_phase(p),
                    width=btn_width,
                )
                # Add tooltip with full phase name and description
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text(phase, color=(200, 180, 140))
                    # Find description
                    for detail in self._phase_details:
                        if detail.get("name", "").lower() == phase.lower():
                            desc = detail.get("description", "")
                            if desc:
                                dpg.add_text(desc, wrap=200, color=(150, 150, 150))
                            break

    def _rebuild_phase_buttons(self):
        """Rebuild phase selector buttons for new phase list."""
        if dpg.does_item_exist(self._phase_buttons_tag):
            dpg.delete_item(self._phase_buttons_tag, children_only=True)
            self._render_phase_buttons()

        # Also update turn structure display
        if dpg.does_item_exist(self._turn_structure_tag):
            turn_name = self._turn_structure.get("name", "")
            if turn_name and turn_name != "Standard":
                dpg.set_value(self._turn_structure_tag, f"[{turn_name}]")
                dpg.configure_item(self._turn_structure_tag, show=True)
            else:
                dpg.configure_item(self._turn_structure_tag, show=False)

    def _render_phase_actions(self):
        """Render phase-specific action suggestions."""
        if dpg.does_item_exist(self._actions_tag):
            dpg.delete_item(self._actions_tag, children_only=True)

        phase = self._battle.battle_state.current_phase
        actions = self._get_phase_actions(phase)

        with dpg.group(parent=self._actions_tag):
            for action in actions:
                dpg.add_text(f"  - {action}", color=(130, 130, 130))

    def _on_roster_changed(self, model: BattleRosterModel):
        """Handle roster/battle state changes."""
        self._update_display()

    def _update_display(self):
        """Update the display from battle state."""
        state = self._battle.battle_state

        dpg.set_value(self._turn_tag, str(state.turn_number))

        phase_color = self._get_phase_color(state.current_phase)
        dpg.set_value(self._phase_tag, state.current_phase)
        dpg.configure_item(self._phase_tag, color=phase_color)

        self._render_phase_actions()
        self._update_log()

    def _update_log(self):
        """Update the turn log display."""
        if dpg.does_item_exist(self._log_tag):
            dpg.delete_item(self._log_tag, children_only=True)

        with dpg.group(parent=self._log_tag):
            log = self._battle.battle_state.turn_log
            # Show last 10 entries
            for entry in log[-10:]:
                dpg.add_text(entry, color=(120, 120, 120))

            if not log:
                dpg.add_text("Battle started", color=(100, 100, 100))

    def _set_phase(self, phase: str):
        """Set phase directly."""
        if self._battle.set_phase(phase):
            self._update_display()
            if self._on_phase_change:
                self._on_phase_change(phase, self._battle.battle_state.turn_number)

    def _next_phase(self):
        """Advance to next phase."""
        old_turn = self._battle.battle_state.turn_number
        new_phase = self._battle.advance_phase()
        new_turn = self._battle.battle_state.turn_number

        self._update_display()

        if self._on_phase_change:
            self._on_phase_change(new_phase, new_turn)

    def _next_turn(self):
        """Advance to next turn."""
        state = self._battle.battle_state
        state.turn_number += 1
        state.current_phase = self._phases[0] if self._phases else "Movement"
        state.turn_log.append(f"--- Turn {state.turn_number} ---")

        self._update_display()

        if self._on_phase_change:
            self._on_phase_change(state.current_phase, state.turn_number)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def current_turn(self) -> int:
        """Get current turn number."""
        return self._battle.battle_state.turn_number

    @property
    def current_phase(self) -> str:
        """Get current phase name."""
        return self._battle.battle_state.current_phase

    def set_phases(self, phases: list[str]):
        """
        Set custom phase list.

        Args:
            phases: List of phase names
        """
        self._phases = phases.copy()
        self._battle.battle_state.phases = phases.copy()
        self._do_rebuild_phase_buttons()
        self._update_display()

    def _do_rebuild_phase_buttons(self):
        """Rebuild phase selector buttons for new phase list."""
        # Delegate to the main implementation
        self._rebuild_phase_buttons()

    def log_event(self, event: str):
        """Add an event to the turn log."""
        self._battle.battle_state.log_event(event)
        self._update_log()

    def add_battle_event(
        self,
        text: str,
        consequence: Optional[str] = None,
        affects_units: Optional[List[str]] = None,
    ) -> BattleEvent:
        """
        Add a battle event with optional consequence.

        Args:
            text: Event description
            consequence: Optional consequence text
            affects_units: List of unit names affected

        Returns:
            The created BattleEvent
        """
        event = BattleEvent(
            text=text,
            turn=self._battle.battle_state.turn_number,
            phase=self._battle.battle_state.current_phase,
            consequence=consequence,
            affects_units=affects_units or [],
        )
        self._events.append(event)
        self._update_events_display()

        # Also log to turn log
        log_text = f"EVENT: {text}"
        if consequence:
            log_text += f" -> {consequence}"
        self._battle.battle_state.log_event(log_text)
        self._update_log()

        # Callback
        if self._on_event:
            self._on_event(event)

        return event

    def _update_events_display(self):
        """Update the battle events display."""
        if dpg.does_item_exist(self._events_tag):
            dpg.delete_item(self._events_tag, children_only=True)

        with dpg.group(parent=self._events_tag):
            if not self._events:
                dpg.add_text("No events yet", color=(100, 100, 100))
                return

            # Show last 5 events (most recent first)
            for event in reversed(self._events[-5:]):
                # Event header
                with dpg.group(horizontal=True):
                    dpg.add_text(f"T{event.turn}", color=(180, 180, 100))
                    dpg.add_text(f"[{event.phase[:3]}]", color=(120, 120, 150))

                # Event text
                dpg.add_text(f"  {event.text}", color=(200, 180, 140), wrap=280)

                # Consequence if any
                if event.consequence:
                    dpg.add_text(f"    -> {event.consequence}", color=(200, 120, 120), wrap=280)

                dpg.add_spacer(height=3)

    @property
    def events(self) -> List[BattleEvent]:
        """Get all battle events."""
        return self._events.copy()

    def clear_events(self):
        """Clear all battle events."""
        self._events = []
        self._update_events_display()

    def reset(self):
        """Reset to turn 1, first phase."""
        state = self._battle.battle_state
        state.turn_number = 1
        state.current_phase = self._phases[0] if self._phases else "Movement"
        state.turn_log = ["--- Battle Started ---"]
        self._events = []
        self._update_display()
        self._update_events_display()


class CompactTurnDisplay:
    """
    Compact turn display for sidebar use.

    Shows just turn number and phase with minimal controls.
    """

    def __init__(
        self,
        parent: str,
        on_advance: Optional[Callable] = None,
    ):
        self.parent = parent
        self._on_advance = on_advance
        self._battle = get_battle_roster()

        self._tag = f"compact_turn_{id(self)}"
        self._build()

        self._battle.add_roster_observer(self._on_roster_changed)

    def _build(self):
        """Build compact display."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            with dpg.group(horizontal=True):
                dpg.add_text("T", color=(150, 150, 150))
                dpg.add_text(
                    str(self._battle.battle_state.turn_number),
                    tag=f"{self._tag}_turn",
                    color=(220, 200, 160)
                )
                dpg.add_text(" | ", color=(100, 100, 100))
                dpg.add_text(
                    self._battle.battle_state.current_phase,
                    tag=f"{self._tag}_phase",
                    color=(100, 180, 100)
                )
                dpg.add_button(
                    label=">",
                    callback=self._advance,
                    width=25,
                )

    def _on_roster_changed(self, model: BattleRosterModel):
        """Handle changes."""
        dpg.set_value(
            f"{self._tag}_turn",
            str(self._battle.battle_state.turn_number)
        )
        dpg.set_value(
            f"{self._tag}_phase",
            self._battle.battle_state.current_phase
        )

    def _advance(self):
        """Advance phase."""
        self._battle.advance_phase()
        if self._on_advance:
            self._on_advance()
