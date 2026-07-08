"""Oracle mode picker — one front door for the three apps.

A small window with three buttons; the chosen app launches as its own
process and the picker closes. The true in-process merge is deferred
(war-room decree 2026-07-07, Phase 2): the three apps use colliding
global tags, so they stay separate processes under one launcher skin.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import dearpygui.dearpygui as dpg

from oracle.gui import style

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_MODES = [
    ("Solo RPG", "Mythic-style GM emulator — oracle, scenes, threads, NPCs",
     "oracle.gui.oracle_app"),
    ("Wargame", "Tactical AI opponent — armies, turns, battle narration",
     "oracle.gui.wargame_app"),
    ("Birthright", "Domain campaign — regency, holdings, domain turns",
     "oracle.gui.launcher"),
]


def _launch_mode(sender, app_data, user_data) -> None:
    module = user_data
    subprocess.Popen([sys.executable, "-m", module], cwd=str(_REPO_ROOT))
    dpg.stop_dearpygui()


def main() -> None:
    dpg.create_context()
    style.apply_style()

    with dpg.window(tag="picker_window"):
        dpg.add_spacer(height=8)
        dpg.add_text("ORACLE", color=(200, 175, 130, 255))
        dpg.add_text("Solo tabletop gaming assistant")
        dpg.add_separator()
        dpg.add_spacer(height=4)
        for name, blurb, module in _MODES:
            dpg.add_button(
                label=name,
                width=-1,
                height=44,
                tag=f"picker_btn_{module}",
                callback=_launch_mode,
                user_data=module,
            )
            dpg.add_text(blurb, color=(140, 135, 125, 255))
            dpg.add_spacer(height=6)

    dpg.create_viewport(title="Oracle", width=420, height=380, resizable=False)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("picker_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
