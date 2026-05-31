"""
Chat Panel - Conversational interface with the GM.

Provides a chat-style interface for interacting with the
Game Master brain, asking questions, and receiving narrative responses.
"""

from typing import Callable, Optional, List
from datetime import datetime
import dearpygui.dearpygui as dpg

from oracle.gm.brain import GameMasterBrain, OracleResult


class ChatMessage:
    """Represents a single chat message."""

    def __init__(self, text: str, sender: str, msg_type: str = "normal"):
        self.text = text
        self.sender = sender  # "user", "gm", "system"
        self.msg_type = msg_type  # "normal", "oracle", "dice", "event"
        self.timestamp = datetime.now()


class ChatPanel:
    """
    Chat interface panel for GM interaction.

    Displays conversation history and provides input for
    asking questions and making statements to the GM.
    """

    def __init__(self, parent: str, gm_brain: GameMasterBrain):
        self.parent = parent
        self.gm = gm_brain
        self.messages: List[ChatMessage] = []

        # UI element tags
        self._panel_tag = None
        self._chat_log_tag = None
        self._input_tag = None

        # Callbacks
        self._on_oracle_result: Optional[Callable] = None

        self._build()

    def _build(self):
        """Build the chat panel UI."""
        # Use unique tag prefix to avoid conflicts
        self._tag_prefix = f"chat_panel_{id(self)}"
        self._panel_tag = f"{self._tag_prefix}_root"
        self._chat_log_tag = f"{self._tag_prefix}_log"
        self._input_tag = f"{self._tag_prefix}_input"

        # Use group instead of child_window to avoid double-nesting issues
        with dpg.group(parent=self.parent, tag=self._panel_tag):
            # Header
            with dpg.group(horizontal=True):
                dpg.add_text("Game Master", color=(200, 180, 140))
                dpg.add_spacer(width=-120)

                # Quick action buttons
                dpg.add_button(
                    label="Oracle",
                    callback=self._show_oracle_quick,
                    width=50
                )
                dpg.add_button(
                    label="Dice",
                    callback=self._show_dice_quick,
                    width=50
                )

            dpg.add_separator()

            # Chat log area - this child_window is needed for scrolling
            with dpg.child_window(
                height=-70,
                border=False,
                tag=self._chat_log_tag
            ):
                pass  # Content added dynamically

            dpg.add_separator()

            # Input area
            with dpg.group():
                dpg.add_input_text(
                    hint="Ask a question or describe an action...",
                    width=-1,
                    on_enter=True,
                    callback=self._on_input_enter,
                    tag=self._input_tag
                )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Send",
                        callback=self._on_send,
                        width=80
                    )
                    dpg.add_button(
                        label="Ask Oracle",
                        callback=self._on_ask_oracle,
                        width=100
                    )
                    dpg.add_button(
                        label="Roll Dice",
                        callback=self._on_roll_dice,
                        width=100
                    )

    def initialize(self):
        """Initialize the chat with GM greeting."""
        greeting = self.gm.greet()
        self._add_message(ChatMessage(greeting, "gm"))

    def _add_message(self, msg: ChatMessage):
        """Add a message to the chat log."""
        self.messages.append(msg)
        self._render_message(msg)

        # Scroll to bottom
        # dpg.set_y_scroll("chat_log_container", dpg.get_y_scroll_max("chat_log_container"))

    def _render_message(self, msg: ChatMessage):
        """Render a single message in the chat log."""
        with dpg.group(parent=self._chat_log_tag):
            # Sender label with color
            if msg.sender == "user":
                color = (100, 180, 220)
                label = "You"
            elif msg.sender == "gm":
                color = (200, 180, 140)
                label = "GM"
            else:
                color = (150, 150, 150)
                label = "System"

            # Time
            time_str = msg.timestamp.strftime("%H:%M")

            with dpg.group(horizontal=True):
                dpg.add_text(f"[{time_str}]", color=(100, 100, 100))
                dpg.add_text(f"{label}:", color=color)

            # Message content with special formatting for types
            if msg.msg_type == "oracle":
                # Oracle results get special styling
                dpg.add_text(msg.text, wrap=480, color=(180, 200, 140))
            elif msg.msg_type == "dice":
                dpg.add_text(msg.text, wrap=480, color=(140, 180, 220))
            elif msg.msg_type == "event":
                dpg.add_text(msg.text, wrap=480, color=(220, 180, 140))
            else:
                dpg.add_text(msg.text, wrap=480)

            dpg.add_spacer(height=5)

    def _on_input_enter(self, sender, app_data, user_data):
        """Handle enter key in input field."""
        self._on_send()

    def _on_send(self):
        """Send the current input to the GM."""
        text = dpg.get_value(self._input_tag)
        if not text or not text.strip():
            return

        # Clear input
        dpg.set_value(self._input_tag, "")

        # Add user message
        user_msg = ChatMessage(text.strip(), "user")
        self._add_message(user_msg)

        # Get GM response
        response = self.gm.process_input(text.strip())

        # Add GM response
        gm_msg = ChatMessage(response, "gm")
        self._add_message(gm_msg)

    def _on_ask_oracle(self):
        """Convert input to oracle question."""
        text = dpg.get_value(self._input_tag)
        if not text or not text.strip():
            self._show_oracle_dialog()
            return

        # Clear input
        dpg.set_value(self._input_tag, "")

        question = text.strip().rstrip("?")

        # Add user question
        user_msg = ChatMessage(f"Oracle: {question}?", "user")
        self._add_message(user_msg)

        # Get oracle result
        result = self.gm.ask_oracle(question)

        # Format response
        response = f"**{result.answer_text}**\n\n{result.interpretation}"
        if result.random_event:
            response += f"\n\n[Random Event!] {result.random_event_text}"

        gm_msg = ChatMessage(response, "gm", "oracle")
        self._add_message(gm_msg)

        # Notify listeners
        if self._on_oracle_result:
            self._on_oracle_result(result)

    def _on_roll_dice(self):
        """Roll dice from input."""
        text = dpg.get_value(self._input_tag)
        if not text or not text.strip():
            self._show_dice_dialog()
            return

        # Clear input
        dpg.set_value(self._input_tag, "")

        # Add user message
        user_msg = ChatMessage(f"Rolling: {text.strip()}", "user")
        self._add_message(user_msg)

        # Roll dice
        result = self.gm.roll_dice(text.strip())

        # Add result
        gm_msg = ChatMessage(result.description, "gm", "dice")
        self._add_message(gm_msg)

    def _show_oracle_quick(self):
        """Show quick oracle dialog."""
        self._show_oracle_dialog()

    def _show_dice_quick(self):
        """Show quick dice dialog."""
        self._show_dice_dialog()

    def _show_oracle_dialog(self):
        """Show oracle question dialog."""
        if dpg.does_item_exist("oracle_quick_dialog"):
            dpg.delete_item("oracle_quick_dialog")

        with dpg.window(
            label="Ask the Oracle",
            modal=True,
            tag="oracle_quick_dialog",
            width=400,
            height=280,
            pos=[200, 150]
        ):
            dpg.add_text("Enter your yes/no question:")
            dpg.add_input_text(
                multiline=True,
                width=-1,
                height=60,
                tag="oracle_q_input"
            )

            dpg.add_text("Likelihood:")
            dpg.add_combo(
                items=["Impossible", "Very Unlikely", "Unlikely", "Even", "Likely", "Very Likely", "Certain"],
                default_value="Even",
                tag="oracle_q_likelihood",
                width=-1
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Ask",
                    callback=self._execute_oracle_dialog,
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("oracle_quick_dialog"),
                    width=100
                )

    def _execute_oracle_dialog(self):
        """Execute oracle from dialog."""
        question = dpg.get_value("oracle_q_input")
        likelihood = dpg.get_value("oracle_q_likelihood").lower().replace(" ", "_")

        if not question or not question.strip():
            dpg.delete_item("oracle_quick_dialog")
            return

        # Add user question
        user_msg = ChatMessage(f"Oracle ({likelihood}): {question.strip()}?", "user")
        self._add_message(user_msg)

        # Get result
        result = self.gm.ask_oracle(question.strip(), likelihood)

        # Format response
        response = f"**{result.answer_text}**\n\n{result.interpretation}"
        if result.random_event:
            response += f"\n\n[Random Event!] {result.random_event_text}"

        gm_msg = ChatMessage(response, "gm", "oracle")
        self._add_message(gm_msg)

        dpg.delete_item("oracle_quick_dialog")

    def _show_dice_dialog(self):
        """Show dice rolling dialog."""
        if dpg.does_item_exist("dice_quick_dialog"):
            dpg.delete_item("dice_quick_dialog")

        with dpg.window(
            label="Roll Dice",
            modal=True,
            tag="dice_quick_dialog",
            width=350,
            height=200,
            pos=[200, 150]
        ):
            dpg.add_text("Enter dice notation:")
            dpg.add_input_text(
                hint="e.g., 2d6+3, 1d20, 4d6kh3",
                width=-1,
                tag="dice_q_input"
            )

            dpg.add_text("Quick rolls:", color=(150, 150, 150))
            with dpg.group(horizontal=True):
                for notation in ["1d20", "2d6", "1d100", "4d6kh3"]:
                    dpg.add_button(
                        label=notation,
                        callback=self._quick_dice_roll,
                        user_data=notation,
                        width=70
                    )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Roll",
                    callback=self._execute_dice_dialog,
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("dice_quick_dialog"),
                    width=100
                )

    def _quick_dice_roll(self, sender, app_data, user_data):
        """Handle quick dice button."""
        notation = user_data
        dpg.set_value("dice_q_input", notation)
        self._execute_dice_dialog()

    def _execute_dice_dialog(self):
        """Execute dice roll from dialog."""
        notation = dpg.get_value("dice_q_input")

        if not notation or not notation.strip():
            dpg.delete_item("dice_quick_dialog")
            return

        # Add user message
        user_msg = ChatMessage(f"Rolling: {notation.strip()}", "user")
        self._add_message(user_msg)

        # Roll dice
        result = self.gm.roll_dice(notation.strip())

        # Add result
        gm_msg = ChatMessage(result.description, "gm", "dice")
        self._add_message(gm_msg)

        dpg.delete_item("dice_quick_dialog")

    def add_system_message(self, text: str):
        """Add a system message to the chat."""
        msg = ChatMessage(text, "system")
        self._add_message(msg)

    def add_event_message(self, text: str):
        """Add an event message to the chat."""
        msg = ChatMessage(text, "gm", "event")
        self._add_message(msg)

    def on_oracle_result(self, callback: Callable):
        """Register callback for oracle results."""
        self._on_oracle_result = callback

    def clear(self):
        """Clear the chat history."""
        self.messages.clear()
        if dpg.does_item_exist(self._chat_log_tag):
            dpg.delete_item(self._chat_log_tag, children_only=True)
