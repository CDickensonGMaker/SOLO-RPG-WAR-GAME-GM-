"""Shared visual style for all Oracle GUI apps.

One theme + one font so Solo RPG, Wargame, and Birthright feel like one
product. Palette grown from the Birthright app's original parchment-on-dark
theme (war-room decree 2026-07-07, Phase 2).

Usage, immediately after ``dpg.create_context()``::

    from oracle.gui import style
    style.apply_style()

Pixels only — no game logic belongs in this module.
"""

from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

FONT_SIZE = 17

# System fonts, best first. We reference (not bundle) them; if none exist,
# DearPyGui's built-in 13px font is the silent fallback.
_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/tahoma.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

_FONT_TAG = "oracle_shared_font"
_THEME_TAG = "oracle_shared_theme"


def apply_style() -> None:
    """Bind the shared Oracle font and theme. Call once after create_context()."""
    _bind_font()
    _bind_theme()


def centered_pos(width: int, height: int) -> list:
    """Viewport-centered [x, y] for a dialog/modal of the given size."""
    viewport_w = dpg.get_viewport_client_width() or 1280
    viewport_h = dpg.get_viewport_client_height() or 800
    return [max(0, (viewport_w - width) // 2), max(0, (viewport_h - height) // 2)]


def _bind_font() -> None:
    if dpg.does_item_exist(_FONT_TAG):
        dpg.bind_font(_FONT_TAG)
        return
    for candidate in _FONT_CANDIDATES:
        if candidate.exists():
            with dpg.font_registry():
                dpg.add_font(str(candidate), FONT_SIZE, tag=_FONT_TAG)
            dpg.bind_font(_FONT_TAG)
            return
    # No system font found: keep DearPyGui's default rather than crash.


def _bind_theme() -> None:
    if dpg.does_item_exist(_THEME_TAG):
        dpg.bind_theme(_THEME_TAG)
        return
    with dpg.theme(tag=_THEME_TAG):
        with dpg.theme_component(dpg.mvAll):
            # Palette: dark slate surfaces, warm parchment/leather accents.
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (25, 25, 30, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 42, 255))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (30, 30, 36, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (60, 60, 70, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (222, 216, 202, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (140, 135, 125, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (45, 45, 55, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (55, 55, 65, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (65, 65, 75, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 60, 50, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (90, 75, 60, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (110, 90, 70, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (60, 55, 50, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (75, 68, 60, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (90, 80, 70, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Tab, (55, 50, 45, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (75, 68, 60, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, (90, 80, 70, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (35, 35, 40, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (50, 45, 40, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Separator, (80, 70, 60, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (25, 25, 30, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (70, 65, 58, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, (90, 82, 72, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, (110, 100, 86, 255))
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (200, 175, 130, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (140, 120, 95, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (170, 145, 112, 255))

            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 14)
    dpg.bind_theme(_THEME_TAG)
