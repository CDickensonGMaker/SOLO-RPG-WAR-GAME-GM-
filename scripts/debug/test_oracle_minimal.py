"""
Minimal Oracle app to isolate the blank screen issue.
"""
import dearpygui.dearpygui as dpg

from oracle.gm.brain import GameMasterBrain
from oracle.gm.personality import PERSONALITIES


class MinimalOracleApp:
    def __init__(self):
        self.gm = GameMasterBrain(personality=PERSONALITIES["classic"])
        self.mode = "rpg"

    def run(self):
        dpg.create_context()
        self._build_ui()

        dpg.create_viewport(title="Oracle Minimal Test", width=1200, height=800)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)

        # Show startup dialog after a brief delay
        dpg.set_frame_callback(30, self._show_startup)

        dpg.start_dearpygui()
        dpg.destroy_context()

    def _build_ui(self):
        """Build minimal UI."""
        with dpg.window(tag="main_window", no_title_bar=True):
            dpg.add_text("Oracle - Minimal Test", color=(200, 180, 140))
            dpg.add_separator()

            # RPG Content - built directly, no separate panel classes
            with dpg.child_window(tag="rpg_content", height=-1, border=False):
                with dpg.group(horizontal=True):
                    # Chat area (left)
                    with dpg.child_window(width=600, height=-1, border=True):
                        dpg.add_text("Chat Panel", color=(200, 180, 140))
                        dpg.add_separator()

                        # Chat log
                        with dpg.child_window(tag="chat_log", height=-80, border=False):
                            dpg.add_text("Messages will appear here...", color=(100, 100, 100))

                        dpg.add_separator()
                        dpg.add_input_text(tag="chat_input", hint="Type a message...", width=-1)
                        dpg.add_button(label="Send", callback=self._on_send, width=100)

                    dpg.add_spacer(width=10)

                    # Session area (right)
                    with dpg.child_window(width=300, height=-1, border=True):
                        dpg.add_text("Session Panel", color=(200, 180, 140))
                        dpg.add_separator()

                        dpg.add_text("Mode: RPG", tag="mode_text")
                        dpg.add_text("Scene: Unknown")
                        dpg.add_slider_int(label="Chaos", default_value=5, min_value=1, max_value=9)

    def _show_startup(self):
        """Show startup dialog."""
        with dpg.window(tag="startup_dialog", label="Welcome", modal=True,
                       width=400, height=300, pos=[400, 250]):
            dpg.add_text("Oracle - Solo Game Master", color=(200, 180, 140))
            dpg.add_separator()
            dpg.add_spacer(height=20)

            dpg.add_button(label="Solo RPG", callback=self._start_rpg, width=-1, height=40)
            dpg.add_text("Click to start RPG mode", color=(100, 100, 100))

            dpg.add_spacer(height=20)

            dpg.add_button(label="Wargame", callback=self._start_wargame, width=-1, height=40)
            dpg.add_text("Click to start Wargame mode", color=(100, 100, 100))

    def _start_rpg(self):
        """Start RPG mode."""
        dpg.delete_item("startup_dialog")
        self._add_chat_message("GM", self.gm.greet())

    def _start_wargame(self):
        """Start Wargame mode."""
        dpg.delete_item("startup_dialog")
        dpg.set_value("mode_text", "Mode: Wargame")
        self._add_chat_message("System", "Wargame mode started.")

    def _add_chat_message(self, sender: str, text: str):
        """Add a message to the chat log."""
        # Clear placeholder if present
        if dpg.does_item_exist("chat_log"):
            dpg.delete_item("chat_log", children_only=True)

        with dpg.group(parent="chat_log"):
            dpg.add_text(f"[{sender}]", color=(200, 180, 140) if sender == "GM" else (100, 180, 220))
            dpg.add_text(text, wrap=550)
            dpg.add_spacer(height=10)

    def _on_send(self):
        """Handle send button."""
        text = dpg.get_value("chat_input")
        if text and text.strip():
            self._add_chat_message("You", text.strip())
            dpg.set_value("chat_input", "")

            # Get GM response
            response = self.gm.process_input(text.strip())
            self._add_chat_message("GM", response)


if __name__ == "__main__":
    app = MinimalOracleApp()
    app.run()
