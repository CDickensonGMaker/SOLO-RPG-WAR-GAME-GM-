"""
Wargame Panel - Tactical AI opponent controls and battle mechanics.

Provides wargame-specific functionality:
- AI opponent configuration (doctrine, aggression)
- Battle scale and situation tracking
- Tactical decision generation
- Target priority calculation
- Morale checks
- Battle event generation
- Force/unit tracking
"""

from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import dearpygui.dearpygui as dpg


class Doctrine(Enum):
    """AI tactical doctrine types."""
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    GUERRILLA = "guerrilla"
    BLITZ = "blitz"
    ATTRITION = "attrition"


class Scale(Enum):
    """Battle scale for wargame mode."""
    SKIRMISH = "skirmish"          # Squad/fire team level
    TACTICAL = "tactical"          # Platoon/Company
    OPERATIONAL = "operational"    # Battalion/Regiment
    STRATEGIC = "strategic"        # Division+


class UnitStatus(Enum):
    """Unit combat status."""
    FRESH = "fresh"
    ENGAGED = "engaged"
    PINNED = "pinned"
    WAVERING = "wavering"
    ROUTING = "routing"
    DESTROYED = "destroyed"


@dataclass
class Force:
    """A military force or unit being tracked."""
    name: str
    side: str  # "friendly", "enemy", "neutral"
    strength: int = 100  # Percentage
    morale: int = 100
    status: UnitStatus = UnitStatus.FRESH
    unit_type: str = "infantry"
    notes: List[str] = field(default_factory=list)


@dataclass
class WargameState:
    """Current wargame state."""
    doctrine: Doctrine = Doctrine.BALANCED
    aggression: int = 5  # 1-10
    scale: Scale = Scale.TACTICAL
    turn: int = 1
    phase: str = "planning"  # planning, movement, combat, morale

    # Forces
    friendly_forces: List[Force] = field(default_factory=list)
    enemy_forces: List[Force] = field(default_factory=list)

    # Situation
    terrain: str = "open"
    weather: str = "clear"
    visibility: str = "good"
    supply_status: str = "adequate"

    # Combat log
    combat_log: List[str] = field(default_factory=list)


class WargamePanel:
    """
    Wargame control panel with tactical AI.

    Provides AI opponent decision-making, morale checks,
    target priority, and battle event generation.
    """

    DOCTRINES = {
        Doctrine.AGGRESSIVE: {
            "name": "Aggressive",
            "desc": "Attack at every opportunity. Press advantages ruthlessly.",
            "attack_mod": 2,
            "defense_mod": -1,
            "morale_mod": 1
        },
        Doctrine.DEFENSIVE: {
            "name": "Defensive",
            "desc": "Hold ground. Counter-attack only when advantageous.",
            "attack_mod": -1,
            "defense_mod": 2,
            "morale_mod": 0
        },
        Doctrine.BALANCED: {
            "name": "Balanced",
            "desc": "Flexible response. Adapt to circumstances.",
            "attack_mod": 0,
            "defense_mod": 0,
            "morale_mod": 0
        },
        Doctrine.GUERRILLA: {
            "name": "Guerrilla",
            "desc": "Hit and run. Avoid decisive engagement.",
            "attack_mod": 1,
            "defense_mod": -2,
            "morale_mod": -1
        },
        Doctrine.BLITZ: {
            "name": "Blitz",
            "desc": "Maximum speed. Bypass strongpoints. Exploit gaps.",
            "attack_mod": 2,
            "defense_mod": -2,
            "morale_mod": 2
        },
        Doctrine.ATTRITION: {
            "name": "Attrition",
            "desc": "Wear down the enemy. Preserve own forces.",
            "attack_mod": -1,
            "defense_mod": 1,
            "morale_mod": -1
        }
    }

    SCALES = {
        Scale.SKIRMISH: {
            "name": "Skirmish",
            "desc": "Squad/Fire Team (4-12 soldiers)",
            "unit_examples": ["Fire Team", "Squad", "Patrol"]
        },
        Scale.TACTICAL: {
            "name": "Tactical",
            "desc": "Platoon/Company (30-200 soldiers)",
            "unit_examples": ["Platoon", "Company", "Tank Section"]
        },
        Scale.OPERATIONAL: {
            "name": "Operational",
            "desc": "Battalion/Regiment (500-5000 soldiers)",
            "unit_examples": ["Battalion", "Regiment", "Battle Group"]
        },
        Scale.STRATEGIC: {
            "name": "Strategic",
            "desc": "Division+ (10000+ soldiers)",
            "unit_examples": ["Division", "Corps", "Army Group"]
        }
    }

    TERRAIN_TYPES = ["open", "woods", "urban", "hills", "mountains", "marsh", "desert", "jungle"]
    WEATHER_TYPES = ["clear", "overcast", "rain", "storm", "snow", "fog", "extreme_heat"]

    def __init__(self, parent: str):
        self.parent = parent
        self.state = WargameState()

        # Callbacks
        self._on_decision: Optional[Callable] = None
        self._on_event: Optional[Callable] = None

        self._build()

    def _build(self):
        """Build the wargame panel UI."""
        with dpg.child_window(
            parent=self.parent,
            width=320,
            height=-1,
            border=True,
            tag="wargame_panel"
        ):
            # Header
            dpg.add_text("Tactical AI", color=(200, 140, 140))
            dpg.add_separator()

            # AI Configuration Section
            with dpg.collapsing_header(label="AI Configuration", default_open=True):
                # Doctrine
                dpg.add_text("Doctrine:", color=(150, 150, 150))
                dpg.add_combo(
                    items=[d.value.title() for d in Doctrine],
                    default_value="Balanced",
                    callback=self._on_doctrine_change,
                    tag="doctrine_combo",
                    width=-1
                )
                dpg.add_text("", tag="doctrine_desc", wrap=300, color=(120, 120, 120))

                dpg.add_spacer(height=5)

                # Aggression
                dpg.add_text("Aggression:", color=(150, 150, 150))
                with dpg.group(horizontal=True):
                    dpg.add_slider_int(
                        default_value=5,
                        min_value=1,
                        max_value=10,
                        callback=self._on_aggression_change,
                        tag="aggression_slider",
                        width=200
                    )
                    dpg.add_text("5", tag="aggression_value")

                dpg.add_spacer(height=5)

                # Scale
                dpg.add_text("Battle Scale:", color=(150, 150, 150))
                dpg.add_combo(
                    items=[s.value.title() for s in Scale],
                    default_value="Tactical",
                    callback=self._on_scale_change,
                    tag="scale_combo",
                    width=-1
                )
                dpg.add_text("", tag="scale_desc", wrap=300, color=(120, 120, 120))

            # Situation Section
            with dpg.collapsing_header(label="Situation", default_open=True):
                with dpg.group(horizontal=True):
                    dpg.add_text("Turn:", color=(150, 150, 150))
                    dpg.add_text("1", tag="turn_number")
                    dpg.add_spacer(width=20)
                    dpg.add_text("Phase:", color=(150, 150, 150))
                    dpg.add_text("Planning", tag="phase_text")

                dpg.add_spacer(height=5)

                with dpg.group(horizontal=True):
                    dpg.add_text("Terrain:")
                    dpg.add_combo(
                        items=[t.title() for t in self.TERRAIN_TYPES],
                        default_value="Open",
                        callback=self._on_terrain_change,
                        tag="terrain_combo",
                        width=100
                    )

                with dpg.group(horizontal=True):
                    dpg.add_text("Weather:")
                    dpg.add_combo(
                        items=[w.replace("_", " ").title() for w in self.WEATHER_TYPES],
                        default_value="Clear",
                        callback=self._on_weather_change,
                        tag="weather_combo",
                        width=100
                    )

            # Tactical Actions Section
            with dpg.collapsing_header(label="Tactical Actions", default_open=True):
                dpg.add_button(
                    label="Get AI Decision",
                    callback=self._generate_decision,
                    width=-1
                )
                dpg.add_button(
                    label="Target Priority",
                    callback=self._show_priority_dialog,
                    width=-1
                )
                dpg.add_button(
                    label="Morale Check",
                    callback=self._show_morale_dialog,
                    width=-1
                )
                dpg.add_button(
                    label="Battle Event",
                    callback=self._generate_event,
                    width=-1
                )

                dpg.add_separator()

                dpg.add_button(
                    label="Advance Turn",
                    callback=self._advance_turn,
                    width=-1
                )

            # Forces Section
            with dpg.collapsing_header(label="Forces"):
                dpg.add_text("Friendly:", color=(100, 180, 100))
                with dpg.child_window(height=60, border=False, tag="friendly_forces_list"):
                    dpg.add_text("No forces tracked", color=(100, 100, 100))

                dpg.add_button(
                    label="Add Friendly Unit",
                    callback=lambda: self._show_add_force_dialog("friendly"),
                    width=-1
                )

                dpg.add_spacer(height=5)

                dpg.add_text("Enemy:", color=(180, 100, 100))
                with dpg.child_window(height=60, border=False, tag="enemy_forces_list"):
                    dpg.add_text("No forces tracked", color=(100, 100, 100))

                dpg.add_button(
                    label="Add Enemy Unit",
                    callback=lambda: self._show_add_force_dialog("enemy"),
                    width=-1
                )

            # Result Display
            dpg.add_separator()
            dpg.add_text("Result:", color=(180, 160, 120))
            with dpg.child_window(height=100, border=False, tag="wargame_result_area"):
                dpg.add_text("", tag="wargame_result_text", wrap=300)

        # Initialize descriptions
        self._update_doctrine_desc()
        self._update_scale_desc()

    def _on_doctrine_change(self, sender, app_data, user_data):
        """Handle doctrine selection change."""
        doctrine_str = app_data.lower()
        self.state.doctrine = Doctrine(doctrine_str)
        self._update_doctrine_desc()

    def _on_aggression_change(self, sender, app_data, user_data):
        """Handle aggression slider change."""
        self.state.aggression = app_data
        dpg.set_value("aggression_value", str(app_data))

    def _on_scale_change(self, sender, app_data, user_data):
        """Handle scale selection change."""
        scale_str = app_data.lower()
        self.state.scale = Scale(scale_str)
        self._update_scale_desc()

    def _on_terrain_change(self, sender, app_data, user_data):
        """Handle terrain change."""
        self.state.terrain = app_data.lower()

    def _on_weather_change(self, sender, app_data, user_data):
        """Handle weather change."""
        self.state.weather = app_data.lower().replace(" ", "_")

    def _update_doctrine_desc(self):
        """Update doctrine description text."""
        info = self.DOCTRINES[self.state.doctrine]
        dpg.set_value("doctrine_desc", info["desc"])

    def _update_scale_desc(self):
        """Update scale description text."""
        info = self.SCALES[self.state.scale]
        dpg.set_value("scale_desc", info["desc"])

    def _generate_decision(self):
        """Generate an AI tactical decision."""
        doctrine = self.state.doctrine
        aggression = self.state.aggression
        terrain = self.state.terrain

        # Decision tables by doctrine
        decisions = {
            Doctrine.AGGRESSIVE: [
                "Assault the enemy position immediately",
                "Launch flanking attack on exposed unit",
                "Press the advantage - all units advance",
                "Concentrate fire on weakest enemy element",
                "Commit reserves to exploit breakthrough",
                "Close assault - fix and destroy"
            ],
            Doctrine.DEFENSIVE: [
                "Hold current positions and await enemy",
                "Establish interlocking fields of fire",
                "Prepare fallback positions",
                "Counter-attack only if success is certain",
                "Conserve ammunition - fire discipline",
                "Request reinforcements before engaging"
            ],
            Doctrine.BALANCED: [
                "Probe enemy defenses before committing",
                "Advance by bounds with overwatch",
                "Secure flanks before main effort",
                "Maintain tactical reserve",
                "Exploit opportunities without overextending",
                "Balance offense and defense"
            ],
            Doctrine.GUERRILLA: [
                "Ambush from concealed positions",
                "Hit supply lines and withdraw",
                "Avoid decisive engagement - fade away",
                "Night raid on rear areas",
                "Mine routes and observe",
                "Strike isolated units only"
            ],
            Doctrine.BLITZ: [
                "Maximum speed advance - bypass resistance",
                "Exploit any gap in enemy line",
                "Deep penetration to disrupt command",
                "Encircle and isolate - don't reduce",
                "Maintain momentum at all costs",
                "Air assets for close support"
            ],
            Doctrine.ATTRITION: [
                "Methodical advance under fire support",
                "Reduce enemy positions systematically",
                "Accept slow progress for low casualties",
                "Mass fires before any assault",
                "Rotate units to preserve strength",
                "Siege approach - cut off and starve"
            ]
        }

        # Select base decision
        options = decisions[doctrine]

        # Modify by aggression
        if aggression >= 8:
            # Very aggressive - favor offensive options
            decision = random.choice(options[:3]) if len(options) > 3 else random.choice(options)
        elif aggression <= 3:
            # Very cautious - favor defensive options
            decision = random.choice(options[3:]) if len(options) > 3 else random.choice(options)
        else:
            decision = random.choice(options)

        # Terrain modifiers
        terrain_notes = {
            "urban": "Urban terrain favors defense - consider building-by-building approach",
            "woods": "Woods limit visibility - close range engagement likely",
            "open": "Open ground - maximize fire support before movement",
            "hills": "Heights provide advantage - secure high ground",
            "mountains": "Mountain warfare - air support limited, supply critical",
            "marsh": "Marsh terrain - movement restricted, channel enemy advance",
            "desert": "Desert - water supply critical, night operations favorable",
            "jungle": "Jungle - close combat, ambush risk high"
        }

        terrain_note = terrain_notes.get(terrain, "")

        # Weather impact
        weather_impact = ""
        if self.state.weather in ["rain", "storm", "fog"]:
            weather_impact = f"\nWeather ({self.state.weather}): Reduced visibility affects coordination"
        elif self.state.weather == "snow":
            weather_impact = "\nSnow: Movement slowed, tracks visible, cold weather casualties risk"
        elif self.state.weather == "extreme_heat":
            weather_impact = "\nExtreme heat: Water critical, limit daylight operations"

        # Random complication chance
        complication = ""
        if random.random() < 0.2:  # 20% chance
            complications = [
                "Intelligence reports enemy reinforcements approaching",
                "Supply situation deteriorating",
                "Adjacent unit requesting support",
                "Communication difficulties reported",
                "Civilian presence in engagement area",
                "Unexpected terrain obstacle encountered"
            ]
            complication = f"\n\n[Complication] {random.choice(complications)}"

        # Format result
        result = f"**AI Decision ({doctrine.value.title()}, Aggression {aggression}/10)**\n\n"
        result += f"{decision}\n\n"
        if terrain_note:
            result += f"[Terrain] {terrain_note}"
        if weather_impact:
            result += weather_impact
        if complication:
            result += complication

        self._set_result(result)

        if self._on_decision:
            self._on_decision(result)

    def _show_priority_dialog(self):
        """Show target priority dialog."""
        if dpg.does_item_exist("priority_dialog"):
            dpg.delete_item("priority_dialog")

        with dpg.window(
            label="Target Priority",
            modal=True,
            tag="priority_dialog",
            width=400,
            height=300,
            pos=[200, 150]
        ):
            dpg.add_text("Enter potential targets (comma-separated):")
            dpg.add_input_text(
                hint="e.g., Tank platoon, Infantry company, Artillery battery",
                width=-1,
                tag="priority_targets_input"
            )

            dpg.add_spacer(height=10)

            dpg.add_text("Priority factors:", color=(150, 150, 150))
            dpg.add_checkbox(label="Threat to friendly forces", tag="priority_threat", default_value=True)
            dpg.add_checkbox(label="High value target", tag="priority_value", default_value=False)
            dpg.add_checkbox(label="Target of opportunity", tag="priority_opportunity", default_value=False)

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Calculate Priority",
                    callback=self._calculate_priority,
                    width=140
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("priority_dialog"),
                    width=100
                )

    def _calculate_priority(self):
        """Calculate target priority."""
        targets_text = dpg.get_value("priority_targets_input")
        if not targets_text:
            dpg.delete_item("priority_dialog")
            return

        targets = [t.strip() for t in targets_text.split(",") if t.strip()]

        is_threat = dpg.get_value("priority_threat")
        is_hv = dpg.get_value("priority_value")
        is_opportunity = dpg.get_value("priority_opportunity")

        # Score and sort targets
        scored_targets = []
        for target in targets:
            score = random.randint(1, 100)

            # Doctrine modifiers
            if self.state.doctrine == Doctrine.AGGRESSIVE:
                score += 10 if is_threat else 0
            elif self.state.doctrine == Doctrine.DEFENSIVE:
                score += 20 if is_threat else -10
            elif self.state.doctrine == Doctrine.GUERRILLA:
                score += 15 if is_opportunity else -5

            # Aggression modifier
            score += (self.state.aggression - 5) * 2

            scored_targets.append((target, score))

        # Sort by score
        scored_targets.sort(key=lambda x: -x[1])

        # Format result
        result = "**Target Priority Assessment**\n\n"
        for i, (target, score) in enumerate(scored_targets, 1):
            priority = "HIGH" if score > 70 else "MEDIUM" if score > 40 else "LOW"
            result += f"{i}. {target} [{priority}]\n"

        result += f"\nFactors: {'Threat ' if is_threat else ''}{'HVT ' if is_hv else ''}{'Opportunity' if is_opportunity else ''}"

        self._set_result(result)
        dpg.delete_item("priority_dialog")

    def _show_morale_dialog(self):
        """Show morale check dialog."""
        if dpg.does_item_exist("morale_dialog"):
            dpg.delete_item("morale_dialog")

        with dpg.window(
            label="Morale Check",
            modal=True,
            tag="morale_dialog",
            width=350,
            height=280,
            pos=[200, 150]
        ):
            dpg.add_text("Unit Name:")
            dpg.add_input_text(
                hint="e.g., 1st Platoon",
                width=-1,
                tag="morale_unit_input"
            )

            dpg.add_text("Casualties (%):")
            dpg.add_slider_int(
                default_value=20,
                min_value=0,
                max_value=100,
                width=-1,
                tag="morale_casualties_slider"
            )

            dpg.add_text("Modifiers:", color=(150, 150, 150))
            dpg.add_checkbox(label="Under heavy fire", tag="morale_heavy_fire")
            dpg.add_checkbox(label="Leader casualty", tag="morale_leader_lost")
            dpg.add_checkbox(label="Flanked/Surrounded", tag="morale_flanked")
            dpg.add_checkbox(label="Friendly support nearby", tag="morale_support", default_value=True)

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Check Morale",
                    callback=self._check_morale,
                    width=120
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("morale_dialog"),
                    width=100
                )

    def _check_morale(self):
        """Perform morale check."""
        unit_name = dpg.get_value("morale_unit_input") or "Unit"
        casualties = dpg.get_value("morale_casualties_slider")

        heavy_fire = dpg.get_value("morale_heavy_fire")
        leader_lost = dpg.get_value("morale_leader_lost")
        flanked = dpg.get_value("morale_flanked")
        support = dpg.get_value("morale_support")

        # Base morale threshold (decreases with casualties)
        threshold = 70 - int(casualties * 0.6)

        # Modifiers
        if heavy_fire:
            threshold -= 15
        if leader_lost:
            threshold -= 20
        if flanked:
            threshold -= 25
        if support:
            threshold += 10

        # Aggression affects morale
        threshold += (self.state.aggression - 5) * 2

        # Doctrine modifier
        doctrine_mod = self.DOCTRINES[self.state.doctrine]["morale_mod"]
        threshold += doctrine_mod * 5

        threshold = max(5, min(95, threshold))

        # Roll
        roll = random.randint(1, 100)

        # Determine result
        if roll <= threshold - 30:
            status = "HOLDING FIRM"
            description = f"{unit_name} maintains excellent cohesion despite casualties."
            color = (100, 200, 100)
        elif roll <= threshold:
            status = "HOLDING"
            description = f"{unit_name} holds position but morale is shaken."
            color = (180, 200, 100)
        elif roll <= threshold + 20:
            status = "WAVERING"
            description = f"{unit_name} is wavering. May withdraw if pressure continues."
            color = (200, 180, 100)
        elif roll <= threshold + 40:
            status = "FALLING BACK"
            description = f"{unit_name} begins organized withdrawal."
            color = (200, 140, 100)
        else:
            status = "ROUTING"
            description = f"{unit_name} breaks! Unit is routing in disorder."
            color = (200, 100, 100)

        result = f"**Morale Check: {unit_name}**\n\n"
        result += f"Casualties: {casualties}%\n"
        result += f"Roll: {roll} vs {threshold}\n\n"
        result += f"**Status: {status}**\n{description}"

        self._set_result(result)
        dpg.delete_item("morale_dialog")

    def _generate_event(self):
        """Generate a random battle event."""
        scale = self.state.scale

        events = {
            Scale.SKIRMISH: [
                "Sniper spotted in elevated position!",
                "IED/booby trap discovered on approach",
                "Civilian vehicle approaching checkpoint",
                "Radio communications lost temporarily",
                "Enemy reinforcements (fire team) spotted approaching",
                "Friendly wounded needs immediate evacuation",
                "Enemy attempting to flank left/right",
                "Ammunition running critically low",
                "Suspicious activity in nearby structure",
                "Enemy drone overhead"
            ],
            Scale.TACTICAL: [
                "Artillery fire mission available on call",
                "Air support (CAS) checking in on station",
                "Enemy armor column spotted moving to sector",
                "Supply convoy ambushed on MSR",
                "Adjacent unit requests immediate support",
                "Enemy breakthrough attempt on flank",
                "Weather deteriorating - visibility reduced",
                "Communications equipment malfunction",
                "Mass casualty event at aid station",
                "Civilian evacuation blocking route"
            ],
            Scale.OPERATIONAL: [
                "Strategic reserve committed to battle",
                "Enemy counterattack developing on secondary front",
                "Main supply route interdicted by enemy action",
                "Political pressure to accelerate timeline",
                "Intelligence indicates enemy weakness in sector",
                "Friendly unit encircled - relief force needed",
                "Enemy conducting strategic withdrawal",
                "Allied force coordination problems emerging",
                "Air superiority contested in sector",
                "Chemical/NBC threat detected"
            ],
            Scale.STRATEGIC: [
                "Enemy theater-level offensive launched",
                "Allied nation committing additional forces",
                "War weariness affecting home front morale",
                "New weapons system deployed operationally",
                "Peace negotiations announced - ceasefire possible",
                "Neutral nation protests border violations",
                "Economic sanctions affecting supply chain",
                "Key enemy commander eliminated",
                "Refugee crisis developing in sector",
                "International media presence complicating operations"
            ]
        }

        event = random.choice(events[scale])

        # Determine severity
        severity_roll = random.randint(1, 100)
        if severity_roll <= 20:
            severity = "CRITICAL"
            severity_color = (200, 100, 100)
        elif severity_roll <= 50:
            severity = "SIGNIFICANT"
            severity_color = (200, 180, 100)
        else:
            severity = "ROUTINE"
            severity_color = (150, 150, 150)

        result = f"**Battle Event ({scale.value.title()} Scale)**\n\n"
        result += f"[{severity}] {event}\n\n"

        # Suggest response based on doctrine
        responses = {
            Doctrine.AGGRESSIVE: "Recommended: Aggressive response - use this to press attack",
            Doctrine.DEFENSIVE: "Recommended: Consolidate positions - maintain defensive posture",
            Doctrine.BALANCED: "Recommended: Assess situation - respond proportionally",
            Doctrine.GUERRILLA: "Recommended: Exploit chaos - hit and fade",
            Doctrine.BLITZ: "Recommended: Maintain momentum - bypass if possible",
            Doctrine.ATTRITION: "Recommended: Methodical response - preserve force strength"
        }

        result += f"\n{responses[self.state.doctrine]}"

        self._set_result(result)

        if self._on_event:
            self._on_event(event, severity)

    def _advance_turn(self):
        """Advance to next turn."""
        self.state.turn += 1
        dpg.set_value("turn_number", str(self.state.turn))

        # Cycle phase
        phases = ["planning", "movement", "combat", "morale"]
        current_idx = phases.index(self.state.phase)
        self.state.phase = phases[(current_idx + 1) % len(phases)]
        dpg.set_value("phase_text", self.state.phase.title())

        self._set_result(f"**Turn {self.state.turn} - {self.state.phase.title()} Phase**\n\nReady for orders.")

    def _show_add_force_dialog(self, side: str):
        """Show dialog to add a force."""
        dialog_tag = f"add_force_{side}_dialog"

        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        with dpg.window(
            label=f"Add {side.title()} Unit",
            modal=True,
            tag=dialog_tag,
            width=350,
            height=220,
            pos=[200, 150]
        ):
            dpg.add_text("Unit Name:")
            dpg.add_input_text(
                hint="e.g., 1st Platoon, Alpha Company",
                width=-1,
                tag=f"force_name_{side}"
            )

            dpg.add_text("Unit Type:")
            dpg.add_combo(
                items=["Infantry", "Armor", "Artillery", "Cavalry", "Support", "Air", "Naval"],
                default_value="Infantry",
                width=-1,
                tag=f"force_type_{side}"
            )

            dpg.add_text("Initial Strength (%):")
            dpg.add_slider_int(
                default_value=100,
                min_value=10,
                max_value=100,
                width=-1,
                tag=f"force_strength_{side}"
            )

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add Unit",
                    callback=lambda: self._add_force(side),
                    width=100
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(dialog_tag),
                    width=100
                )

    def _add_force(self, side: str):
        """Add a force to tracking."""
        name = dpg.get_value(f"force_name_{side}")
        unit_type = dpg.get_value(f"force_type_{side}")
        strength = dpg.get_value(f"force_strength_{side}")

        if not name:
            dpg.delete_item(f"add_force_{side}_dialog")
            return

        force = Force(
            name=name,
            side=side,
            strength=strength,
            unit_type=unit_type.lower()
        )

        if side == "friendly":
            self.state.friendly_forces.append(force)
            self._render_forces("friendly")
        else:
            self.state.enemy_forces.append(force)
            self._render_forces("enemy")

        dpg.delete_item(f"add_force_{side}_dialog")

    def _render_forces(self, side: str):
        """Render forces list."""
        list_tag = f"{side}_forces_list"
        forces = self.state.friendly_forces if side == "friendly" else self.state.enemy_forces

        if dpg.does_item_exist(list_tag):
            dpg.delete_item(list_tag, children_only=True)

        with dpg.group(parent=list_tag):
            if not forces:
                dpg.add_text("No forces tracked", color=(100, 100, 100))
            else:
                for force in forces:
                    color = (100, 180, 100) if force.strength > 50 else (180, 100, 100)
                    dpg.add_text(f"{force.name} ({force.strength}%)", color=color)

    def _set_result(self, text: str):
        """Set the result display text."""
        dpg.set_value("wargame_result_text", text)

    def on_decision(self, callback: Callable):
        """Register callback for tactical decisions."""
        self._on_decision = callback

    def on_event(self, callback: Callable):
        """Register callback for battle events."""
        self._on_event = callback

    def get_state(self) -> WargameState:
        """Get current wargame state."""
        return self.state
