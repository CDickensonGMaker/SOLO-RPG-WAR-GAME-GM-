"""
Dockable Panel Component

Provides a base class for panels that can be:
- Docked in the main layout
- Popped out to floating windows
- Resized and repositioned
- Persisted across sessions
"""

from typing import Optional, Callable, Tuple
import dearpygui.dearpygui as dpg


# Callback types
PopoutCallback = Callable[[str, bool], None]  # (panel_id, is_floating)


class DockablePanel:
    """
    Base class for panels that can be docked or popped out.

    Provides:
    - Header with title and pop-out button
    - Toggle between docked and floating states
    - Size hints and minimum dimensions
    - State persistence support

    Usage:
        class MyPanel(DockablePanel):
            def _build_content(self):
                dpg.add_text("My content")

        panel = MyPanel(parent="container", title="My Panel")
    """

    def __init__(
        self,
        parent: str,
        title: str,
        width: int = -1,
        height: int = -1,
        min_width: int = 200,
        min_height: int = 150,
        on_popout_change: Optional[PopoutCallback] = None,
        show_header: bool = True,
        header_color: Tuple[int, int, int] = (200, 160, 120),
    ):
        """
        Create a dockable panel.

        Args:
            parent: Parent DearPyGui item tag
            title: Panel title
            width: Initial width (-1 for auto)
            height: Initial height (-1 for auto)
            min_width: Minimum width when popped out
            min_height: Minimum height when popped out
            on_popout_change: Callback when pop-out state changes
            show_header: Whether to show the header with title and buttons
            header_color: Color for the header title
        """
        self.parent = parent
        self.title = title
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self._on_popout_change = on_popout_change
        self.show_header = show_header
        self.header_color = header_color

        # State
        self._is_floating = False
        self._saved_parent = parent
        self._saved_width = width
        self._saved_height = height

        # UI tags
        self._tag = f"dockable_{id(self)}"
        self._root_tag = f"{self._tag}_root"
        self._content_tag = f"{self._tag}_content"
        self._header_tag = f"{self._tag}_header"
        self._popout_btn_tag = f"{self._tag}_popout_btn"
        self._floating_window_tag = f"{self._tag}_floating"

        self._build()

    def _build(self):
        """Build the panel UI."""
        with dpg.child_window(
            parent=self.parent,
            width=self.width,
            height=self.height,
            border=True,
            tag=self._root_tag,
        ):
            # Header with title and pop-out button
            if self.show_header:
                self._build_header()

            # Content area - subclasses override _build_content
            with dpg.group(tag=self._content_tag):
                self._build_content()

    def _build_header(self):
        """Build the panel header with title and controls."""
        with dpg.group(horizontal=True, tag=self._header_tag):
            dpg.add_text(self.title, color=self.header_color)

            # Spacer to push button to right
            dpg.add_spacer(width=-50)

            # Pop-out button
            dpg.add_button(
                label="[^]",
                callback=self._toggle_popout,
                tag=self._popout_btn_tag,
                width=30,
            )
            with dpg.tooltip(self._popout_btn_tag):
                dpg.add_text("Pop out to floating window")

        dpg.add_separator()

    def _build_content(self):
        """
        Build the panel content. Override in subclasses.

        This method is called during __init__ to build the panel's
        main content area. Subclasses should override this to add
        their specific UI elements.
        """
        dpg.add_text("Override _build_content() in subclass", color=(150, 150, 150))

    def _toggle_popout(self, sender=None, app_data=None, user_data=None):
        """Toggle between docked and floating states."""
        if self._is_floating:
            self._dock()
        else:
            self._popout()

    def _popout(self):
        """Convert to floating window."""
        if self._is_floating:
            return

        self._is_floating = True

        # Get current content
        # Note: In DearPyGui, we can't move widgets between parents easily
        # So we recreate the floating window with the content

        # Create floating window
        with dpg.window(
            label=self.title,
            tag=self._floating_window_tag,
            width=max(self.width if self.width > 0 else 400, self.min_width),
            height=max(self.height if self.height > 0 else 300, self.min_height),
            pos=[100, 100],
            on_close=self._on_floating_close,
            no_collapse=False,
        ):
            # Rebuild content in floating window
            with dpg.group(tag=f"{self._content_tag}_float"):
                self._build_content()

        # Hide the docked panel
        dpg.configure_item(self._root_tag, show=False)

        # Update button
        if dpg.does_item_exist(self._popout_btn_tag):
            dpg.configure_item(self._popout_btn_tag, label="[v]")
            # Update tooltip
            parent_tooltip = dpg.get_item_children(self._popout_btn_tag, 1)
            if parent_tooltip:
                for tooltip in parent_tooltip:
                    dpg.delete_item(tooltip)
                with dpg.tooltip(self._popout_btn_tag):
                    dpg.add_text("Dock back to main window")

        # Callback
        if self._on_popout_change:
            self._on_popout_change(self._tag, True)

    def _dock(self):
        """Return to docked state."""
        if not self._is_floating:
            return

        self._is_floating = False

        # Delete floating window
        if dpg.does_item_exist(self._floating_window_tag):
            dpg.delete_item(self._floating_window_tag)

        # Show docked panel
        dpg.configure_item(self._root_tag, show=True)

        # Update button
        if dpg.does_item_exist(self._popout_btn_tag):
            dpg.configure_item(self._popout_btn_tag, label="[^]")
            # Update tooltip
            parent_tooltip = dpg.get_item_children(self._popout_btn_tag, 1)
            if parent_tooltip:
                for tooltip in parent_tooltip:
                    dpg.delete_item(tooltip)
                with dpg.tooltip(self._popout_btn_tag):
                    dpg.add_text("Pop out to floating window")

        # Callback
        if self._on_popout_change:
            self._on_popout_change(self._tag, False)

    def _on_floating_close(self, sender=None, app_data=None, user_data=None):
        """Handle floating window close - dock back."""
        self._dock()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def is_floating(self) -> bool:
        """Check if panel is currently floating."""
        return self._is_floating

    @property
    def tag(self) -> str:
        """Get the panel's unique tag."""
        return self._tag

    @property
    def content_tag(self) -> str:
        """Get the content area tag for adding widgets."""
        if self._is_floating:
            return f"{self._content_tag}_float"
        return self._content_tag

    def refresh(self):
        """Refresh the panel content. Override in subclasses if needed."""
        pass

    def set_width(self, width: int):
        """Set panel width."""
        self.width = width
        if dpg.does_item_exist(self._root_tag):
            dpg.configure_item(self._root_tag, width=width)
        if self._is_floating and dpg.does_item_exist(self._floating_window_tag):
            dpg.configure_item(self._floating_window_tag, width=width)

    def set_height(self, height: int):
        """Set panel height."""
        self.height = height
        if dpg.does_item_exist(self._root_tag):
            dpg.configure_item(self._root_tag, height=height)
        if self._is_floating and dpg.does_item_exist(self._floating_window_tag):
            dpg.configure_item(self._floating_window_tag, height=height)

    def get_state(self) -> dict:
        """Get panel state for persistence."""
        state = {
            "is_floating": self._is_floating,
            "width": self.width,
            "height": self.height,
        }

        if self._is_floating and dpg.does_item_exist(self._floating_window_tag):
            pos = dpg.get_item_pos(self._floating_window_tag)
            state["floating_pos"] = pos

        return state

    def set_state(self, state: dict):
        """Restore panel state from persistence."""
        if state.get("is_floating", False) and not self._is_floating:
            self._popout()
            if "floating_pos" in state and dpg.does_item_exist(self._floating_window_tag):
                dpg.set_item_pos(self._floating_window_tag, state["floating_pos"])

        if "width" in state:
            self.set_width(state["width"])
        if "height" in state:
            self.set_height(state["height"])
