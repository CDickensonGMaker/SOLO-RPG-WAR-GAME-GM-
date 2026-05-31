"""
Unit Detail View - Full unit stat block display.

Provides:
- Complete stat line display (M, WS, BS, S, T, W, I, A, Ld, Sv)
- Weapon profiles with full stats
- Special rules with descriptions
- Equipment/wargear options
- AI tactical hints
"""

from typing import Optional
import dearpygui.dearpygui as dpg

from oracle.gui.models.wargame_data import get_wargame_data, UnitCard
from oracle.gamesystems import UnitProfile, WeaponProfile


class UnitDetailPanel:
    """
    Panel showing detailed unit information.

    Displays the complete stat block for a selected unit,
    including weapons, special rules, and tactical hints.
    """

    def __init__(self, parent: str, width: int = -1):
        """
        Create the unit detail panel.

        Args:
            parent: Parent DearPyGui item tag
            width: Panel width (-1 for auto)
        """
        self.parent = parent
        self.width = width

        self._data = get_wargame_data()

        # UI tags
        self._tag = f"unit_detail_{id(self)}"
        self._content_tag = f"{self._tag}_content"

        # Current unit
        self._current_unit: Optional[UnitProfile] = None

        self._build()

    def _build(self):
        """Build the UI components."""
        with dpg.child_window(
            parent=self.parent,
            width=self.width,
            height=-1,
            border=True,
            tag=f"{self._tag}_root"
        ):
            dpg.add_text("Unit Details", color=(200, 160, 120))
            dpg.add_separator()

            # Content area
            with dpg.child_window(
                height=-1,
                border=False,
                tag=self._content_tag
            ):
                dpg.add_text(
                    "Select a unit to view details",
                    color=(100, 100, 100)
                )

    def show_unit(self, unit: UnitProfile | UnitCard):
        """
        Display details for a unit.

        Args:
            unit: UnitProfile or UnitCard to display
        """
        # Get full profile if we have a card
        if isinstance(unit, UnitCard):
            self._current_unit = unit.profile
        else:
            self._current_unit = unit

        self._refresh_display()

    def show_unit_by_name(self, name: str) -> bool:
        """
        Display unit by name lookup.

        Args:
            name: Unit name to look up

        Returns:
            True if unit was found and displayed
        """
        profile = self._data.get_unit_profile(name)
        if profile:
            self._current_unit = profile
            self._refresh_display()
            return True
        return False

    def _refresh_display(self):
        """Refresh the detail display."""
        if dpg.does_item_exist(self._content_tag):
            dpg.delete_item(self._content_tag, children_only=True)

        unit = self._current_unit

        with dpg.group(parent=self._content_tag):
            if not unit:
                dpg.add_text(
                    "Select a unit to view details",
                    color=(100, 100, 100)
                )
                return

            # Unit name and type
            dpg.add_text(unit.name, color=(220, 200, 160))
            dpg.add_text(
                f"{unit.faction} | {unit.unit_type.value.title()}",
                color=(150, 150, 150)
            )

            dpg.add_spacer(height=5)

            # Points and models
            with dpg.group(horizontal=True):
                dpg.add_text(f"Points: {unit.points_cost}", color=(100, 180, 100))
                dpg.add_text(f"  Models: {unit.models_per_unit}")

            dpg.add_spacer(height=8)

            # Stat block
            self._render_stat_block(unit)

            dpg.add_spacer(height=8)

            # Weapons
            if unit.weapons:
                self._render_weapons(unit.weapons)
                dpg.add_spacer(height=8)

            # Wargear
            if unit.wargear:
                self._render_wargear(unit.wargear)
                dpg.add_spacer(height=8)

            # Special Rules
            if unit.special_rules:
                self._render_special_rules(unit.special_rules)
                dpg.add_spacer(height=8)

            # Keywords
            if unit.keywords:
                self._render_keywords(unit.keywords)
                dpg.add_spacer(height=8)

            # Tactical Info
            self._render_tactical_info(unit)

    def _render_stat_block(self, unit: UnitProfile):
        """Render the core stat block."""
        dpg.add_text("STATS", color=(180, 140, 100))

        # Common 40K-style stats
        stat_order = ["M", "WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv"]

        # Header row
        with dpg.group(horizontal=True):
            for stat in stat_order:
                if stat in unit.stats:
                    dpg.add_text(f"{stat:>4}", color=(120, 120, 120))

        # Values row
        with dpg.group(horizontal=True):
            for stat in stat_order:
                if stat in unit.stats:
                    value = str(unit.stats[stat])
                    dpg.add_text(f"{value:>4}", color=(200, 200, 200))

        # Any additional stats not in the standard list
        extra_stats = {k: v for k, v in unit.stats.items() if k not in stat_order}
        if extra_stats:
            dpg.add_spacer(height=3)
            for stat, value in extra_stats.items():
                dpg.add_text(f"{stat}: {value}", color=(150, 150, 150))

    def _render_weapons(self, weapons: list[WeaponProfile]):
        """Render weapon profiles."""
        dpg.add_text("WEAPONS", color=(180, 140, 100))

        for weapon in weapons:
            with dpg.group():
                # Weapon name
                dpg.add_text(f"  {weapon.name}", color=(200, 180, 140))

                # Weapon stats
                stats_line = []
                if weapon.range and weapon.range.lower() != "melee":
                    stats_line.append(f"Range: {weapon.range}")
                stats_line.append(f"S: {weapon.strength}")
                if weapon.ap and weapon.ap not in ["0", "-", ""]:
                    stats_line.append(f"AP: {weapon.ap}")
                stats_line.append(f"D: {weapon.damage}")
                if weapon.shots and weapon.shots != "1":
                    stats_line.append(f"Shots: {weapon.shots}")

                dpg.add_text(
                    f"    {' | '.join(stats_line)}",
                    color=(150, 150, 150)
                )

                # Weapon abilities
                if weapon.abilities:
                    dpg.add_text(
                        f"    [{', '.join(weapon.abilities)}]",
                        color=(140, 160, 140),
                        wrap=280
                    )

    def _render_wargear(self, wargear: list[str]):
        """Render wargear list."""
        dpg.add_text("WARGEAR", color=(180, 140, 100))

        for item in wargear:
            dpg.add_text(f"  - {item}", color=(150, 150, 150))

    def _render_special_rules(self, rules: list[str]):
        """Render special rules."""
        dpg.add_text("SPECIAL RULES", color=(180, 140, 100))

        for rule in rules:
            # Try to look up rule description
            rule_ref = self._data.lookup_rule(rule)
            if rule_ref:
                with dpg.collapsing_header(label=rule, default_open=False):
                    dpg.add_text(
                        rule_ref.description,
                        wrap=260,
                        color=(130, 130, 130)
                    )
            else:
                dpg.add_text(f"  * {rule}", color=(160, 160, 140))

    def _render_keywords(self, keywords: list[str]):
        """Render keywords."""
        dpg.add_text("KEYWORDS", color=(180, 140, 100))
        dpg.add_text(
            f"  {', '.join(keywords)}",
            wrap=280,
            color=(130, 150, 170)
        )

    def _render_tactical_info(self, unit: UnitProfile):
        """Render AI tactical hints."""
        with dpg.collapsing_header(label="Tactical Analysis", default_open=True):
            # Role and threat
            with dpg.group(horizontal=True):
                if unit.tactical_role:
                    dpg.add_text(f"Role: {unit.tactical_role}", color=(140, 180, 140))
                if unit.threat_level:
                    threat_colors = {
                        "low": (100, 150, 100),
                        "medium": (180, 180, 100),
                        "high": (200, 140, 100),
                        "very_high": (200, 100, 100),
                        "extreme": (220, 80, 80),
                    }
                    color = threat_colors.get(unit.threat_level.lower(), (150, 150, 150))
                    dpg.add_text(f"  Threat: {unit.threat_level.upper()}", color=color)

            # Preferred targets
            if unit.preferred_targets:
                dpg.add_text("Best vs:", color=(150, 150, 150))
                dpg.add_text(
                    f"  {', '.join(unit.preferred_targets)}",
                    wrap=260,
                    color=(130, 170, 130)
                )

            # Weaknesses
            if unit.weaknesses:
                dpg.add_text("Vulnerable to:", color=(150, 150, 150))
                dpg.add_text(
                    f"  {', '.join(unit.weaknesses)}",
                    wrap=260,
                    color=(170, 130, 130)
                )

    def clear(self):
        """Clear the detail display."""
        self._current_unit = None
        self._refresh_display()

    @property
    def current_unit(self) -> Optional[UnitProfile]:
        """Get the currently displayed unit."""
        return self._current_unit
