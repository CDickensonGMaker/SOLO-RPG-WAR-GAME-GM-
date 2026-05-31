"""
Session Panel - Displays current session state and controls.

Shows scene information, chaos factor, active threads,
tracked NPCs, and provides session management controls.
"""

from typing import Callable, Optional, List
import dearpygui.dearpygui as dpg

from oracle.gm.brain import GameMasterBrain
from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread


class SessionPanel:
    """
    Session state display panel.

    Shows current scene, chaos factor, active threads,
    and tracked entities for the GM session.
    """

    def __init__(self, parent: str, gm_brain: GameMasterBrain):
        self.parent = parent
        self.gm = gm_brain

        # UI element tags
        self._panel_tag = None
        self._scene_section = None
        self._threads_section = None
        self._npcs_section = None
        self._chaos_slider = None

        # Callbacks
        self._on_scene_change: Optional[Callable] = None
        self._on_chaos_change: Optional[Callable] = None

        self._build()

    def _build(self):
        """Build the session panel UI."""
        # Use unique tag prefix to avoid conflicts
        self._tag_prefix = f"session_panel_{id(self)}"
        self._panel_tag = f"{self._tag_prefix}_root"
        self._scene_section = f"{self._tag_prefix}_scene"
        self._threads_section = f"{self._tag_prefix}_threads"
        self._npcs_section = f"{self._tag_prefix}_npcs"
        self._chaos_slider = f"{self._tag_prefix}_chaos_slider"
        self._mode_text_tag = f"{self._tag_prefix}_mode_text"
        self._setting_text_tag = f"{self._tag_prefix}_setting_text"
        self._chaos_value_tag = f"{self._tag_prefix}_chaos_value"

        # Use group instead of child_window to avoid double-nesting issues
        with dpg.group(parent=self.parent, tag=self._panel_tag):
            # Header
            dpg.add_text("Session", color=(200, 180, 140))
            dpg.add_separator()

            # Mode and Setting
            with dpg.group(horizontal=True):
                dpg.add_text("Mode:", color=(150, 150, 150))
                dpg.add_text("RPG", tag=self._mode_text_tag)

            with dpg.group(horizontal=True):
                dpg.add_text("Setting:", color=(150, 150, 150))
                dpg.add_text("Fantasy", tag=self._setting_text_tag)

            dpg.add_spacer(height=10)

            # Chaos Factor
            dpg.add_text("Chaos Factor", color=(180, 160, 120))
            with dpg.group(horizontal=True):
                dpg.add_slider_int(
                    default_value=5,
                    min_value=1,
                    max_value=9,
                    width=180,
                    callback=self._on_chaos_slider,
                    tag=self._chaos_slider
                )
                dpg.add_text("5", tag=self._chaos_value_tag)

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Current Scene
            dpg.add_text("Current Scene", color=(180, 160, 120))
            with dpg.child_window(height=100, border=False, tag=self._scene_section):
                pass  # Content rendered dynamically
            self._render_scene_section()

            dpg.add_button(
                label="Change Scene",
                callback=self._show_scene_dialog,
                width=-1
            )

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Active Threads
            with dpg.collapsing_header(label="Plot Threads", default_open=True):
                with dpg.child_window(height=100, border=False, tag=self._threads_section):
                    pass  # Content rendered dynamically
                self._render_threads_section()

                dpg.add_button(
                    label="Add Thread",
                    callback=self._show_thread_dialog,
                    width=-1
                )

            # NPCs
            with dpg.collapsing_header(label="NPCs"):
                with dpg.child_window(height=100, border=False, tag=self._npcs_section):
                    pass  # Content rendered dynamically
                self._render_npcs_section()

                dpg.add_button(
                    label="Add NPC",
                    callback=self._show_npc_dialog,
                    width=-1
                )

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Session Controls
            dpg.add_text("Session", color=(180, 160, 120))
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    callback=self._on_save,
                    width=80
                )
                dpg.add_button(
                    label="Load",
                    callback=self._on_load,
                    width=80
                )
                dpg.add_button(
                    label="New",
                    callback=self._on_new,
                    width=80
                )

    def _render_scene_section(self):
        """Render the current scene info."""
        if dpg.does_item_exist(self._scene_section):
            dpg.delete_item(self._scene_section, children_only=True)

        scene = self.gm.memory.current_scene

        with dpg.group(parent=self._scene_section):
            dpg.add_text(scene.get("location", "Unknown"), color=(140, 180, 200))

            with dpg.group(horizontal=True):
                dpg.add_text("Mood:", color=(150, 150, 150))
                dpg.add_text(scene.get("mood", "neutral").title())

            with dpg.group(horizontal=True):
                dpg.add_text("Time:", color=(150, 150, 150))
                time_text = f"{scene.get('time_of_day', 'day').title()}, {scene.get('weather', 'clear').title()}"
                dpg.add_text(time_text)

            npcs = scene.get("present_npcs", [])
            if npcs:
                dpg.add_text(f"Present: {', '.join(npcs)}", color=(150, 150, 150), wrap=260)

    def _render_threads_section(self):
        """Render active plot threads."""
        if dpg.does_item_exist(self._threads_section):
            dpg.delete_item(self._threads_section, children_only=True)

        threads = self.gm.memory.get_active_threads()

        with dpg.group(parent=self._threads_section):
            if not threads:
                dpg.add_text("No active threads", color=(100, 100, 100))
            else:
                for thread in threads[:5]:
                    with dpg.group(horizontal=True):
                        # Importance indicator
                        if thread.importance >= 7:
                            color = (220, 100, 100)
                        elif thread.importance >= 4:
                            color = (220, 180, 100)
                        else:
                            color = (150, 150, 150)

                        dpg.add_text("*", color=color)
                        dpg.add_text(thread.name[:30], wrap=230)

    def _render_npcs_section(self):
        """Render tracked NPCs."""
        if dpg.does_item_exist(self._npcs_section):
            dpg.delete_item(self._npcs_section, children_only=True)

        npcs = self.gm.memory.get_active_npcs()

        with dpg.group(parent=self._npcs_section):
            if not npcs:
                dpg.add_text("No tracked NPCs", color=(100, 100, 100))
            else:
                for npc in npcs[:5]:
                    with dpg.group(horizontal=True):
                        # Disposition indicator
                        if npc.disposition > 30:
                            color = (100, 200, 100)
                        elif npc.disposition < -30:
                            color = (200, 100, 100)
                        else:
                            color = (180, 180, 100)

                        dpg.add_text("*", color=color)
                        dpg.add_text(npc.name[:25])

    def _on_chaos_slider(self, sender, app_data, user_data):
        """Handle chaos slider change."""
        new_value = app_data
        self.gm.memory.chaos_factor = new_value
        dpg.set_value(self._chaos_value_tag, str(new_value))

        # Update GM personality tone
        self.gm.personality.set_tone_from_context(new_value)

        if self._on_chaos_change:
            self._on_chaos_change(new_value)

    def _show_scene_dialog(self):
        """Show scene change dialog."""
        if dpg.does_item_exist("scene_dialog"):
            dpg.delete_item("scene_dialog")

        with dpg.window(
            label="Set Scene",
            modal=True,
            tag="scene_dialog",
            width=400,
            height=350,
            pos=[200, 100]
        ):
            dpg.add_text("Location:")
            dpg.add_input_text(
                hint="e.g., Dark forest clearing",
                width=-1,
                tag="scene_location_input"
            )

            dpg.add_text("Description:")
            dpg.add_input_text(
                multiline=True,
                width=-1,
                height=60,
                tag="scene_desc_input"
            )

            dpg.add_text("Mood:")
            dpg.add_combo(
                items=["Peaceful", "Neutral", "Tense", "Dangerous", "Mysterious", "Grim", "Festive"],
                default_value="Neutral",
                tag="scene_mood_input",
                width=-1
            )

            with dpg.group(horizontal=True):
                dpg.add_text("Time:")
                dpg.add_combo(
                    items=["Dawn", "Day", "Dusk", "Night"],
                    default_value="Day",
                    tag="scene_time_input",
                    width=100
                )
                dpg.add_text("Weather:")
                dpg.add_combo(
                    items=["Clear", "Cloudy", "Rain", "Storm", "Snow", "Fog"],
                    default_value="Clear",
                    tag="scene_weather_input",
                    width=100
                )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Set Scene",
                    callback=self._apply_scene,
                    width=120
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("scene_dialog"),
                    width=100
                )

    def _apply_scene(self):
        """Apply the scene change."""
        location = dpg.get_value("scene_location_input")
        description = dpg.get_value("scene_desc_input")
        mood = dpg.get_value("scene_mood_input").lower()
        time_of_day = dpg.get_value("scene_time_input").lower()
        weather = dpg.get_value("scene_weather_input").lower()

        if not location:
            dpg.delete_item("scene_dialog")
            return

        # Set the scene via GM
        response = self.gm.set_scene(
            location=location,
            description=description,
            mood=mood
        )

        # Update time/weather separately
        self.gm.memory.set_scene(time_of_day=time_of_day, weather=weather)

        # Refresh display
        self._render_scene_section()

        dpg.delete_item("scene_dialog")

        if self._on_scene_change:
            self._on_scene_change(location, response)

    def _show_thread_dialog(self):
        """Show add thread dialog."""
        if dpg.does_item_exist("thread_dialog"):
            dpg.delete_item("thread_dialog")

        with dpg.window(
            label="Add Plot Thread",
            modal=True,
            tag="thread_dialog",
            width=400,
            height=220,
            pos=[200, 150]
        ):
            dpg.add_text("Thread Name:")
            dpg.add_input_text(
                hint="e.g., Find the missing heir",
                width=-1,
                tag="thread_name_input"
            )

            dpg.add_text("Description:")
            dpg.add_input_text(
                multiline=True,
                width=-1,
                height=60,
                tag="thread_desc_input"
            )

            dpg.add_text("Importance (1-10):")
            dpg.add_slider_int(
                default_value=5,
                min_value=1,
                max_value=10,
                width=-1,
                tag="thread_importance_input"
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add Thread",
                    callback=self._add_thread,
                    width=120
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("thread_dialog"),
                    width=100
                )

    def _add_thread(self):
        """Add a new plot thread."""
        name = dpg.get_value("thread_name_input")
        description = dpg.get_value("thread_desc_input")
        importance = dpg.get_value("thread_importance_input")

        if not name:
            dpg.delete_item("thread_dialog")
            return

        self.gm.add_thread(name, description or "", importance)
        self._render_threads_section()

        dpg.delete_item("thread_dialog")

    def _show_npc_dialog(self):
        """Show add NPC dialog."""
        if dpg.does_item_exist("npc_dialog"):
            dpg.delete_item("npc_dialog")

        with dpg.window(
            label="Add NPC",
            modal=True,
            tag="npc_dialog",
            width=400,
            height=280,
            pos=[200, 100]
        ):
            dpg.add_text("NPC Name:")
            dpg.add_input_text(
                hint="e.g., Marcus the Innkeeper",
                width=-1,
                tag="npc_name_input"
            )

            dpg.add_text("Description:")
            dpg.add_input_text(
                multiline=True,
                width=-1,
                height=60,
                tag="npc_desc_input"
            )

            dpg.add_text("Traits (comma-separated):")
            dpg.add_input_text(
                hint="e.g., cunning, greedy, cautious",
                width=-1,
                tag="npc_traits_input"
            )

            dpg.add_text("Disposition (-100 to 100):")
            dpg.add_slider_int(
                default_value=0,
                min_value=-100,
                max_value=100,
                width=-1,
                tag="npc_disposition_input"
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add NPC",
                    callback=self._add_npc,
                    width=120
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("npc_dialog"),
                    width=100
                )

    def _add_npc(self):
        """Add a new NPC."""
        name = dpg.get_value("npc_name_input")
        description = dpg.get_value("npc_desc_input")
        traits_text = dpg.get_value("npc_traits_input")
        disposition = dpg.get_value("npc_disposition_input")

        if not name:
            dpg.delete_item("npc_dialog")
            return

        traits = [t.strip() for t in traits_text.split(",") if t.strip()]

        self.gm.introduce_npc(name, description or "", traits, disposition)
        self._render_npcs_section()

        dpg.delete_item("npc_dialog")

    def _on_save(self):
        """Handle save button."""
        if dpg.does_item_exist("save_dialog"):
            dpg.delete_item("save_dialog")

        with dpg.window(
            label="Save Session",
            modal=True,
            tag="save_dialog",
            width=350,
            height=120,
            pos=[200, 200]
        ):
            dpg.add_text("Filename:")
            dpg.add_input_text(
                hint="session_name",
                width=-1,
                tag="save_filename_input"
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    callback=self._execute_save,
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("save_dialog"),
                    width=100
                )

    def _execute_save(self):
        """Execute save."""
        filename = dpg.get_value("save_filename_input")
        if not filename:
            filename = "oracle_session"

        if not filename.endswith(".json"):
            filename += ".json"

        try:
            self.gm.save_session(filename)
            dpg.delete_item("save_dialog")
        except Exception as e:
            print(f"Save error: {e}")
            dpg.delete_item("save_dialog")

    def _on_load(self):
        """Handle load button."""
        # TODO: Implement file browser dialog
        pass

    def _on_new(self):
        """Handle new session button."""
        # Reset GM state
        self.gm.memory = SessionMemory()
        self.refresh()

    def refresh(self):
        """Refresh all displayed information."""
        self._render_scene_section()
        self._render_threads_section()
        self._render_npcs_section()

        # Update chaos slider
        dpg.set_value(self._chaos_slider, self.gm.memory.chaos_factor)
        dpg.set_value(self._chaos_value_tag, str(self.gm.memory.chaos_factor))

        # Update mode/setting text
        dpg.set_value(self._mode_text_tag, self.gm.memory.mode.upper())
        dpg.set_value(self._setting_text_tag, self.gm.memory.setting.replace("_", " ").title())

    def set_mode(self, mode: str):
        """Set the current mode."""
        self.gm.set_mode(mode)
        dpg.set_value(self._mode_text_tag, mode.upper())

    def set_setting(self, setting: str):
        """Set the current setting."""
        self.gm.set_setting(setting)
        dpg.set_value(self._setting_text_tag, setting.replace("_", " ").title())

    def on_scene_change(self, callback: Callable):
        """Register callback for scene changes."""
        self._on_scene_change = callback

    def on_chaos_change(self, callback: Callable):
        """Register callback for chaos changes."""
        self._on_chaos_change = callback
