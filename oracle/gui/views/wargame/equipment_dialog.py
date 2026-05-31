"""
Equipment Customization Dialog - Weapon and armor selection for units.

Provides:
- Equipment selection modal for army builder
- Points cost display and modification
- Weapon/armor swap interface
- Equipment validation
"""

from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass
import dearpygui.dearpygui as dpg

from oracle.gui.models.wargame_data import get_wargame_data
from oracle.gamesystems import UnitProfile, WeaponProfile


# Callback types
EquipmentChangedCallback = Callable[[str, List[WeaponProfile], int], None]  # (unit_name, weapons, points_delta)


@dataclass
class EquipmentOption:
    """An equipment option that can be selected."""
    name: str
    category: str  # "weapon", "armor", "wargear"
    profile: Optional[WeaponProfile] = None
    points_cost: int = 0
    replaces: Optional[str] = None  # Name of equipment this replaces
    description: str = ""


class EquipmentDialog:
    """
    Modal dialog for customizing unit equipment.

    Allows swapping weapons and adding wargear with
    points cost tracking.
    """

    def __init__(
        self,
        on_confirm: Optional[EquipmentChangedCallback] = None,
    ):
        """
        Create the equipment dialog.

        Args:
            on_confirm: Callback when equipment changes are confirmed
        """
        self._on_confirm = on_confirm
        self._wargame_data = get_wargame_data()

        # Current state
        self._current_unit: Optional[UnitProfile] = None
        self._selected_equipment: Dict[str, EquipmentOption] = {}
        self._base_points: int = 0
        self._points_delta: int = 0

        # UI tags
        self._tag = "equipment_dialog"
        self._window_tag = f"{self._tag}_window"
        self._unit_name_tag = f"{self._tag}_unit_name"
        self._base_weapons_tag = f"{self._tag}_base_weapons"
        self._options_tag = f"{self._tag}_options"
        self._selected_tag = f"{self._tag}_selected"
        self._points_tag = f"{self._tag}_points"

    def show(self, unit: UnitProfile):
        """
        Show the equipment dialog for a unit.

        Args:
            unit: The unit to customize
        """
        self._current_unit = unit
        self._base_points = unit.points_cost
        self._selected_equipment = {}
        self._points_delta = 0

        # Clean up existing dialog
        if dpg.does_item_exist(self._window_tag):
            dpg.delete_item(self._window_tag)

        self._build()

    def _build(self):
        """Build the dialog UI."""
        if not self._current_unit:
            return

        with dpg.window(
            label="Equipment Customization",
            modal=True,
            tag=self._window_tag,
            width=600,
            height=500,
            pos=[300, 150],
            on_close=self._on_cancel,
        ):
            # Header
            dpg.add_text(
                f"Customize: {self._current_unit.name}",
                tag=self._unit_name_tag,
                color=(200, 180, 140),
            )
            dpg.add_text(
                f"Faction: {self._current_unit.faction}",
                color=(150, 150, 150),
            )
            dpg.add_separator()

            # Main content - two columns
            with dpg.group(horizontal=True):
                # Left: Base equipment
                with dpg.child_window(width=280, height=350, border=True):
                    dpg.add_text("Current Equipment", color=(140, 180, 140))
                    dpg.add_separator()

                    # Weapons
                    dpg.add_text("Weapons:", color=(150, 150, 150))
                    with dpg.group(tag=self._base_weapons_tag):
                        self._render_base_weapons()

                    dpg.add_spacer(height=10)

                    # Wargear
                    if self._current_unit.wargear:
                        dpg.add_text("Wargear:", color=(150, 150, 150))
                        for item in self._current_unit.wargear:
                            dpg.add_text(f"  - {item}", color=(130, 130, 130))

                    dpg.add_spacer(height=10)

                    # Special rules
                    if self._current_unit.special_rules:
                        dpg.add_text("Special Rules:", color=(150, 150, 150))
                        for rule in self._current_unit.special_rules[:5]:
                            dpg.add_text(f"  * {rule}", color=(130, 130, 130))

                dpg.add_spacer(width=10)

                # Right: Options
                with dpg.child_window(width=280, height=350, border=True):
                    dpg.add_text("Equipment Options", color=(180, 140, 140))
                    dpg.add_separator()

                    with dpg.group(tag=self._options_tag):
                        self._render_equipment_options()

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Points display
            with dpg.group(horizontal=True):
                dpg.add_text("Base Cost:", color=(150, 150, 150))
                dpg.add_text(f"{self._base_points} pts", color=(180, 180, 180))

                dpg.add_spacer(width=20)

                dpg.add_text("Modifications:", color=(150, 150, 150))
                dpg.add_text(
                    f"{self._points_delta:+d} pts",
                    tag=self._points_tag,
                    color=(140, 200, 140) if self._points_delta <= 0 else (200, 140, 140),
                )

                dpg.add_spacer(width=20)

                dpg.add_text("Total:", color=(150, 150, 150))
                total = self._base_points + self._points_delta
                dpg.add_text(
                    f"{total} pts",
                    tag=f"{self._tag}_total",
                    color=(220, 200, 160),
                )

            dpg.add_spacer(height=10)

            # Buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Confirm",
                    callback=self._on_confirm_click,
                    width=120,
                )
                dpg.add_button(
                    label="Cancel",
                    callback=self._on_cancel,
                    width=120,
                )
                dpg.add_button(
                    label="Reset",
                    callback=self._on_reset,
                    width=80,
                )

    def _render_base_weapons(self):
        """Render the base weapons list."""
        if dpg.does_item_exist(self._base_weapons_tag):
            dpg.delete_item(self._base_weapons_tag, children_only=True)

        if not self._current_unit:
            return

        with dpg.group(parent=self._base_weapons_tag):
            for weapon in self._current_unit.weapons:
                # Check if this weapon has been swapped
                is_replaced = weapon.name in [
                    opt.replaces for opt in self._selected_equipment.values()
                    if opt.replaces
                ]

                with dpg.group(horizontal=True):
                    # Weapon name
                    color = (100, 100, 100) if is_replaced else (180, 180, 180)
                    text = weapon.name
                    if is_replaced:
                        text = f"[REPLACED] {weapon.name}"
                    dpg.add_text(text, color=color)

                # Weapon stats
                stats = []
                if weapon.range and weapon.range.lower() != "melee":
                    stats.append(f"Rng: {weapon.range}")
                stats.append(f"S: {weapon.strength}")
                if weapon.ap and weapon.ap != "0" and weapon.ap != "-":
                    stats.append(f"AP: {weapon.ap}")

                dpg.add_text(f"    {' | '.join(stats)}", color=(120, 120, 120))

    def _render_equipment_options(self):
        """Render available equipment options."""
        if dpg.does_item_exist(self._options_tag):
            dpg.delete_item(self._options_tag, children_only=True)

        with dpg.group(parent=self._options_tag):
            # Generate options based on unit type and keywords
            options = self._generate_options()

            if not options:
                dpg.add_text("No options available", color=(100, 100, 100))
                dpg.add_text("(Unit has fixed loadout)", color=(80, 80, 80))
                return

            for category, items in options.items():
                dpg.add_text(f"{category}:", color=(150, 150, 150))

                for opt in items:
                    is_selected = opt.name in self._selected_equipment

                    with dpg.group(horizontal=True):
                        # Checkbox
                        dpg.add_checkbox(
                            default_value=is_selected,
                            callback=lambda s, a, u: self._toggle_option(u),
                            user_data=opt,
                        )

                        # Option text
                        color = (180, 200, 140) if is_selected else (180, 180, 180)
                        label = opt.name
                        if opt.points_cost != 0:
                            label += f" ({opt.points_cost:+d} pts)"
                        if opt.replaces:
                            label += f" [replaces {opt.replaces}]"
                        dpg.add_text(label, color=color)

                dpg.add_spacer(height=5)

    def _generate_options(self) -> Dict[str, List[EquipmentOption]]:
        """Generate equipment options for the current unit."""
        if not self._current_unit:
            return {}

        options: Dict[str, List[EquipmentOption]] = {}

        # Common weapon upgrades based on unit type
        unit_type = self._current_unit.unit_type.value

        # Melee options
        melee_options = []
        if any("melee" in w.type.lower() or w.range.lower() == "melee"
               for w in self._current_unit.weapons):
            melee_options.append(EquipmentOption(
                name="Power Weapon",
                category="weapon",
                points_cost=10,
                replaces="melee weapon",
                description="Enhanced melee weapon with AP bonus",
            ))
            melee_options.append(EquipmentOption(
                name="Thunder Hammer",
                category="weapon",
                points_cost=15,
                replaces="melee weapon",
                description="Devastating two-handed weapon",
            ))

        if melee_options:
            options["Melee Weapons"] = melee_options

        # Ranged options
        ranged_options = []
        if any("ranged" in w.type.lower() or "rifle" in w.type.lower() or
               "pistol" in w.type.lower() or "heavy" in w.type.lower()
               for w in self._current_unit.weapons):
            ranged_options.append(EquipmentOption(
                name="Scope",
                category="wargear",
                points_cost=5,
                description="+1 to hit at long range",
            ))
            ranged_options.append(EquipmentOption(
                name="Extended Magazine",
                category="wargear",
                points_cost=5,
                description="Additional shots",
            ))

        if ranged_options:
            options["Ranged Upgrades"] = ranged_options

        # Character options
        if "character" in [kw.lower() for kw in self._current_unit.keywords]:
            char_options = [
                EquipmentOption(
                    name="Combat Shield",
                    category="armor",
                    points_cost=10,
                    description="Improved save in melee",
                ),
                EquipmentOption(
                    name="Sigil/Talisman",
                    category="wargear",
                    points_cost=15,
                    description="Protection against psychic/magic",
                ),
            ]
            options["Character Gear"] = char_options

        # Infantry options
        if unit_type == "infantry":
            inf_options = [
                EquipmentOption(
                    name="Frag Grenades",
                    category="wargear",
                    points_cost=5,
                    description="Anti-infantry grenades",
                ),
                EquipmentOption(
                    name="Krak Grenades",
                    category="wargear",
                    points_cost=5,
                    description="Anti-armor grenades",
                ),
            ]
            options["Infantry Gear"] = inf_options

        return options

    def _toggle_option(self, option: EquipmentOption):
        """Toggle an equipment option."""
        if option.name in self._selected_equipment:
            # Remove
            del self._selected_equipment[option.name]
            self._points_delta -= option.points_cost
        else:
            # Add
            self._selected_equipment[option.name] = option
            self._points_delta += option.points_cost

        # Update displays
        self._update_points_display()
        self._render_base_weapons()
        self._render_equipment_options()

    def _update_points_display(self):
        """Update the points display."""
        if dpg.does_item_exist(self._points_tag):
            color = (140, 200, 140) if self._points_delta <= 0 else (200, 140, 140)
            dpg.set_value(self._points_tag, f"{self._points_delta:+d} pts")
            dpg.configure_item(self._points_tag, color=color)

        if dpg.does_item_exist(f"{self._tag}_total"):
            total = self._base_points + self._points_delta
            dpg.set_value(f"{self._tag}_total", f"{total} pts")

    def _on_confirm_click(self):
        """Handle confirm button."""
        if self._on_confirm and self._current_unit:
            # Build modified weapons list
            weapons = list(self._current_unit.weapons)

            # Add new weapon profiles for selected options
            for opt in self._selected_equipment.values():
                if opt.profile:
                    weapons.append(opt.profile)

            self._on_confirm(
                self._current_unit.name,
                weapons,
                self._points_delta,
            )

        self._close()

    def _on_cancel(self):
        """Handle cancel button."""
        self._close()

    def _on_reset(self):
        """Reset all selections."""
        self._selected_equipment = {}
        self._points_delta = 0
        self._update_points_display()
        self._render_base_weapons()
        self._render_equipment_options()

    def _close(self):
        """Close the dialog."""
        if dpg.does_item_exist(self._window_tag):
            dpg.delete_item(self._window_tag)


class QuickEquipmentPanel:
    """
    Compact equipment display for unit cards.

    Shows equipped items with quick-swap buttons.
    """

    def __init__(
        self,
        parent: str,
        on_customize: Optional[Callable[[UnitProfile], None]] = None,
        width: int = -1,
    ):
        """
        Create quick equipment panel.

        Args:
            parent: Parent DearPyGui item tag
            on_customize: Callback to open full customization
            width: Panel width
        """
        self.parent = parent
        self._on_customize = on_customize
        self.width = width

        self._tag = f"quick_equip_{id(self)}"
        self._content_tag = f"{self._tag}_content"
        self._current_unit: Optional[UnitProfile] = None

        self._build()

    def _build(self):
        """Build the UI."""
        with dpg.group(parent=self.parent, tag=f"{self._tag}_root"):
            dpg.add_text("Equipment", color=(150, 150, 150))
            with dpg.group(tag=self._content_tag):
                dpg.add_text("No unit selected", color=(100, 100, 100))

    def show_unit(self, unit: UnitProfile):
        """Display equipment for a unit."""
        self._current_unit = unit

        if dpg.does_item_exist(self._content_tag):
            dpg.delete_item(self._content_tag, children_only=True)

        with dpg.group(parent=self._content_tag):
            # List weapons
            for weapon in unit.weapons[:4]:  # Show first 4
                with dpg.group(horizontal=True):
                    dpg.add_text(f"- {weapon.name}", color=(180, 180, 180))

            if len(unit.weapons) > 4:
                dpg.add_text(f"  (+{len(unit.weapons) - 4} more)", color=(120, 120, 120))

            # Customize button
            if self._on_customize:
                dpg.add_spacer(height=5)
                dpg.add_button(
                    label="Customize...",
                    callback=lambda: self._on_customize(unit),
                    width=-1,
                )

    def clear(self):
        """Clear the display."""
        self._current_unit = None
        if dpg.does_item_exist(self._content_tag):
            dpg.delete_item(self._content_tag, children_only=True)
            with dpg.group(parent=self._content_tag):
                dpg.add_text("No unit selected", color=(100, 100, 100))
