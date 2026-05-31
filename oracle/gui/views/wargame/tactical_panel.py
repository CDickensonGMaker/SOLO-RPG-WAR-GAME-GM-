"""
Tactical Panel - Enhanced AI integration with unit-aware decisions.

Provides:
- Real WargameAI class integration
- Unit-aware threat assessment
- Target priority based on actual enemy units
- Doctrine and aggression configuration
- Morale checks with roster integration
"""

from typing import Callable, Optional, Any
import dearpygui.dearpygui as dpg

from oracle.gui.models.roster_model import get_battle_roster, BattleRosterModel
from oracle.gui.models.wargame_data import get_wargame_data
from oracle.roster import RosterUnit, UnitStatus
from oracle.wargame import (
    WargameAI,
    Doctrine,
    Aggression,
    TacticalDecision,
    ThreatAssessment,
    ThreatLevel,
)


# Callback types
DecisionCallback = Callable[[TacticalDecision], None]
TargetCallback = Callable[[str, str], None]  # (target_name, reason)
EventCallback = Callable[[str], None]  # (event_text)


class TacticalAIPanel:
    """
    Enhanced tactical AI panel with unit-aware decision making.

    Integrates the WargameAI with actual roster data to provide
    context-aware tactical recommendations.
    """

    def __init__(
        self,
        parent: str,
        on_decision: Optional[DecisionCallback] = None,
        on_target_selected: Optional[TargetCallback] = None,
        on_event: Optional[EventCallback] = None,
        width: int = 320,
    ):
        """
        Create the tactical AI panel.

        Args:
            parent: Parent DearPyGui item tag
            on_decision: Callback when AI generates a decision
            on_target_selected: Callback when a target is selected
            on_event: Callback when a battle event is generated
            width: Panel width
        """
        self.parent = parent
        self._on_decision = on_decision
        self._on_target_selected = on_target_selected
        self._on_event = on_event
        self.width = width

        self._ai = WargameAI()
        self._battle = get_battle_roster()
        self._wargame_data = get_wargame_data()

        # UI tags
        self._tag = f"tactical_panel_{id(self)}"
        self._doctrine_tag = f"{self._tag}_doctrine"
        self._aggression_tag = f"{self._tag}_aggression"
        self._result_tag = f"{self._tag}_result"
        self._target_list_tag = f"{self._tag}_targets"

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
            dpg.add_text("Tactical AI", color=(200, 140, 140))
            dpg.add_separator()

            # AI Configuration
            with dpg.collapsing_header(label="AI Configuration", default_open=True):
                # Doctrine
                dpg.add_text("Doctrine:", color=(150, 150, 150))
                dpg.add_combo(
                    items=[d.display for d in Doctrine],
                    default_value=Doctrine.ELITE.display,
                    callback=self._on_doctrine_change,
                    tag=self._doctrine_tag,
                    width=-1,
                )
                dpg.add_text(
                    Doctrine.ELITE.description,
                    tag=f"{self._tag}_doctrine_desc",
                    wrap=280,
                    color=(120, 120, 120),
                )

                dpg.add_spacer(height=5)

                # Aggression
                dpg.add_text("Aggression:", color=(150, 150, 150))
                dpg.add_combo(
                    items=[a.display for a in Aggression],
                    default_value=Aggression.BALANCED.display,
                    callback=self._on_aggression_change,
                    tag=self._aggression_tag,
                    width=-1,
                )

            # Tactical Actions
            with dpg.collapsing_header(label="Tactical Actions", default_open=True):
                dpg.add_button(
                    label="Analyze Situation",
                    callback=self._analyze_situation,
                    width=-1,
                )
                dpg.add_button(
                    label="Get AI Decision",
                    callback=self._generate_decision,
                    width=-1,
                )
                dpg.add_button(
                    label="Roll Target Priority",
                    callback=self._roll_target_priority,
                    width=-1,
                )
                dpg.add_button(
                    label="Generate Battle Event",
                    callback=self._generate_event,
                    width=-1,
                )

            # Target Priority List
            with dpg.collapsing_header(label="Enemy Targets", default_open=True):
                with dpg.child_window(
                    height=100,
                    border=False,
                    tag=self._target_list_tag
                ):
                    dpg.add_text("Analyze to see targets", color=(100, 100, 100))

            # Result Display
            dpg.add_separator()
            dpg.add_text("Analysis Result:", color=(180, 160, 120))
            with dpg.child_window(height=150, border=False, tag=self._result_tag):
                dpg.add_text(
                    "Use actions above to generate tactical analysis",
                    wrap=280,
                    color=(100, 100, 100),
                )

            # Relevant Rules Section
            dpg.add_separator()
            with dpg.collapsing_header(label="Relevant Rules", default_open=False):
                with dpg.child_window(height=120, border=False, tag=f"{self._tag}_rules"):
                    dpg.add_text(
                        "Rules relevant to current situation",
                        color=(100, 100, 100),
                    )
                dpg.add_button(
                    label="Refresh Rules",
                    callback=self._update_relevant_rules,
                    width=-1,
                )

    def _on_doctrine_change(self, sender, app_data, user_data):
        """Handle doctrine selection."""
        for doctrine in Doctrine:
            if doctrine.display == app_data:
                self._ai.doctrine = doctrine
                dpg.set_value(
                    f"{self._tag}_doctrine_desc",
                    doctrine.description
                )
                break

    def _on_aggression_change(self, sender, app_data, user_data):
        """Handle aggression selection."""
        for aggression in Aggression:
            if aggression.display == app_data:
                self._ai.aggression = aggression
                break

    def _build_situation_string(self) -> str:
        """
        Build a situation description from actual roster data.

        Creates a string describing enemy forces for AI analysis.
        """
        enemy_roster = self._battle.enemy_roster
        if not enemy_roster or not enemy_roster.units:
            return "Unknown enemy forces"

        descriptions = []

        for unit in enemy_roster.active_units:
            parts = []

            # Unit name and type
            parts.append(unit.name)

            # Model count
            if unit.models_max > 1:
                parts.append(f"({unit.models_current} models)")

            # Status
            if unit.status == UnitStatus.DAMAGED:
                parts.append("damaged")
            elif unit.status == UnitStatus.WOUNDED:
                parts.append("heavily wounded")
            elif unit.status == UnitStatus.ROUTING:
                parts.append("routing")

            # Threat level from tactical hints
            if unit.threat_level:
                if unit.threat_level.lower() in ("high", "very_high", "extreme"):
                    parts.append("high threat")

            # Equipment hints
            if unit.weapons:
                weapon_hints = []
                for w in unit.weapons:
                    name = w.get("name", "").lower()
                    if any(kw in name for kw in ("heavy", "plasma", "melta", "lascannon")):
                        weapon_hints.append("heavy weapon")
                    if any(kw in name for kw in ("flamer", "template")):
                        weapon_hints.append("flamer")
                    if any(kw in name for kw in ("sniper", "rifle")):
                        weapon_hints.append("sniper")
                if weapon_hints:
                    parts.extend(weapon_hints[:2])  # Max 2 hints

            descriptions.append(" ".join(parts))

        # Add friendly context
        friendly_roster = self._battle.friendly_roster
        if friendly_roster:
            friendly_count = len(friendly_roster.active_units)
            enemy_count = len(enemy_roster.active_units)
            if friendly_count < enemy_count:
                descriptions.append("outnumbered")
            elif friendly_count > enemy_count * 1.5:
                descriptions.append("numerical advantage")

        return ". ".join(descriptions) if descriptions else "Unknown enemy forces"

    def _analyze_situation(self):
        """Analyze the current tactical situation."""
        situation = self._build_situation_string()
        threats = self._ai.analyze_threats(situation)

        self._update_target_list(threats)
        self._display_threat_analysis(threats, situation)

    def _update_target_list(self, threats: list[ThreatAssessment]):
        """Update the target priority list."""
        if dpg.does_item_exist(self._target_list_tag):
            dpg.delete_item(self._target_list_tag, children_only=True)

        with dpg.group(parent=self._target_list_tag):
            if not threats:
                dpg.add_text("No threats detected", color=(100, 100, 100))
                return

            for threat in threats:
                color = {
                    ThreatLevel.HIGH: (200, 100, 100),
                    ThreatLevel.MEDIUM: (200, 180, 100),
                    ThreatLevel.LOW: (100, 180, 100),
                }.get(threat.level, (150, 150, 150))

                with dpg.group(horizontal=True):
                    dpg.add_text(f"[{threat.level.value}]", color=color)
                    dpg.add_selectable(
                        label=threat.target,
                        callback=lambda s, a, t=threat: self._on_target_clicked(t),
                        width=180,
                    )

    def _on_target_clicked(self, threat: ThreatAssessment):
        """Handle target click."""
        if self._on_target_selected:
            self._on_target_selected(threat.target, threat.reason)

    def _display_threat_analysis(self, threats: list[ThreatAssessment], situation: str):
        """Display threat analysis results."""
        if dpg.does_item_exist(self._result_tag):
            dpg.delete_item(self._result_tag, children_only=True)

        with dpg.group(parent=self._result_tag):
            dpg.add_text("THREAT ANALYSIS", color=(200, 160, 120))
            dpg.add_separator()

            dpg.add_text("Situation:", color=(150, 150, 150))
            dpg.add_text(situation, wrap=280, color=(130, 130, 130))

            dpg.add_spacer(height=5)

            dpg.add_text("Detected Threats:", color=(150, 150, 150))
            for threat in threats:
                icon = {
                    ThreatLevel.HIGH: "!!!",
                    ThreatLevel.MEDIUM: " ! ",
                    ThreatLevel.LOW: "   ",
                }.get(threat.level, "   ")

                dpg.add_text(f"{icon} {threat.target}: {threat.reason}", wrap=280)

    def _generate_decision(self):
        """Generate a full tactical decision."""
        situation = self._build_situation_string()
        decision = self._ai.decide(situation)

        self._display_decision(decision)
        self._update_target_list(decision.threats)

        if self._on_decision:
            self._on_decision(decision)

    def _display_decision(self, decision: TacticalDecision):
        """Display the tactical decision."""
        if dpg.does_item_exist(self._result_tag):
            dpg.delete_item(self._result_tag, children_only=True)

        with dpg.group(parent=self._result_tag):
            dpg.add_text("TACTICAL DECISION", color=(200, 160, 120))
            dpg.add_separator()

            # Doctrine/Aggression
            dpg.add_text(
                f"Doctrine: {decision.doctrine.display}",
                color=(150, 150, 150)
            )
            dpg.add_text(
                f"Aggression: {decision.aggression.display}",
                color=(150, 150, 150)
            )

            dpg.add_spacer(height=5)

            # Options considered
            dpg.add_text("Options Evaluated:", color=(150, 150, 150))
            for i, opt in enumerate(decision.options[:3], 1):
                weight_bar = "#" * int(opt.modified_weight * 2)
                dpg.add_text(f"  {i}. {opt.description}", wrap=270)
                dpg.add_text(f"     [{weight_bar}]", color=(100, 140, 100))

            dpg.add_spacer(height=5)

            # Decision
            dpg.add_text("DECISION:", color=(200, 180, 100))
            dpg.add_text(
                f">>> {decision.selected.description.upper()}",
                color=(220, 200, 140),
                wrap=280
            )

            # Add unit-specific recommendations
            self._add_unit_recommendations(decision)

    def _add_unit_recommendations(self, decision: TacticalDecision):
        """Add unit-specific recommendations based on decision."""
        friendly_roster = self._battle.friendly_roster
        enemy_roster = self._battle.enemy_roster

        if not friendly_roster or not enemy_roster:
            return

        dpg.add_spacer(height=8)
        dpg.add_text("Unit Assignments:", color=(150, 150, 150))

        action_type = decision.selected.action_type

        # Match friendly units to enemy units based on action
        for friendly_unit in friendly_roster.active_units[:3]:
            recommendation = self._get_unit_recommendation(
                friendly_unit, enemy_roster.active_units, action_type
            )
            if recommendation:
                dpg.add_text(f"  {friendly_unit.name}:", color=(140, 180, 140))
                dpg.add_text(f"    -> {recommendation}", color=(130, 130, 130), wrap=260)

    def _get_unit_recommendation(
        self,
        unit: RosterUnit,
        enemy_units: list[RosterUnit],
        action_type: str
    ) -> str:
        """Get a recommendation for a specific unit."""
        if not enemy_units:
            return "Hold position - no targets"

        # Get unit's tactical role and preferred targets
        role = unit.tactical_role.lower() if unit.tactical_role else ""
        preferred = [t.lower() for t in (unit.stats.get("preferred_targets", []) or [])]

        # Find best match
        for enemy in enemy_units:
            enemy_type = enemy.slot_type.value.lower()
            enemy_name = enemy.name.lower()

            # Check preferred targets
            if any(p in enemy_type or p in enemy_name for p in preferred):
                return f"Target {enemy.name} (preferred target)"

        # Fallback based on action type
        if action_type == "focus_fire":
            # Target most damaged or weakest
            damaged = [e for e in enemy_units if e.status in (UnitStatus.DAMAGED, UnitStatus.WOUNDED)]
            if damaged:
                return f"Focus fire on {damaged[0].name} (damaged)"
            return f"Focus fire on {enemy_units[0].name}"

        elif action_type == "suppress":
            return f"Suppress {enemy_units[0].name}"

        elif action_type == "flank":
            return "Move to flanking position"

        elif action_type in ("hold", "defensive"):
            return "Hold current position and overwatch"

        elif action_type in ("advance", "assault"):
            return f"Advance toward {enemy_units[0].name}"

        elif action_type == "retreat":
            return "Fall back to cover"

        return f"Engage {enemy_units[0].name}"

    def _roll_target_priority(self):
        """Roll to determine which friendly unit enemy targets."""
        friendly_roster = self._battle.friendly_roster
        if not friendly_roster or not friendly_roster.active_units:
            self._set_result("No friendly units to target")
            return

        # Build target list from friendly units
        targets = []
        for unit in friendly_roster.active_units:
            desc = unit.name
            if unit.status == UnitStatus.DAMAGED:
                desc += " (wounded)"
            if "heavy" in unit.name.lower():
                desc += " (heavy weapon)"
            targets.append(desc)

        selected = self._ai.roll_priority(targets)

        self._set_result(
            f"TARGET PRIORITY\n\n"
            f"Enemy selects: {selected}\n\n"
            f"Other potential targets:\n" +
            "\n".join(f"  - {t}" for t in targets if t != selected)
        )

    def _generate_event(self):
        """Generate a random battle event."""
        event = self._ai.roll_event()
        self._set_result(f"BATTLE EVENT\n\n{event}")

        # Notify callback
        if self._on_event:
            self._on_event(event)

    def _update_relevant_rules(self, sender=None, app_data=None, user_data=None):
        """Update the relevant rules display based on current phase and situation."""
        rules_tag = f"{self._tag}_rules"
        if dpg.does_item_exist(rules_tag):
            dpg.delete_item(rules_tag, children_only=True)

        # Get current phase from battle state
        current_phase = self._battle.battle_state.current_phase.lower()

        # Check if game system is selected
        if not self._wargame_data.current_system:
            with dpg.group(parent=rules_tag):
                dpg.add_text("No game system selected", color=(100, 100, 100))
            return

        # Search for relevant rules based on phase
        phase_keywords = {
            "movement": ["movement", "move", "advance", "charge", "terrain"],
            "psychic": ["psychic", "magic", "spell", "cast", "deny"],
            "shooting": ["shooting", "shoot", "ranged", "hit", "wound", "save", "cover"],
            "assault": ["melee", "combat", "fight", "charge", "pile in", "fall back"],
            "combat": ["melee", "combat", "fight", "charge", "pile in"],
            "morale": ["morale", "leadership", "rout", "flee", "rally", "panic"],
            "rally": ["rally", "regroup", "morale"],
        }

        keywords = phase_keywords.get(current_phase, [current_phase])
        relevant_rules = []

        for keyword in keywords:
            results = self._wargame_data.search_rules(keyword)
            for rule in results:
                if rule not in relevant_rules:
                    relevant_rules.append(rule)
                if len(relevant_rules) >= 5:  # Limit to 5 rules
                    break
            if len(relevant_rules) >= 5:
                break

        # Display rules
        with dpg.group(parent=rules_tag):
            if not relevant_rules:
                dpg.add_text(
                    f"No rules found for {current_phase} phase",
                    color=(100, 100, 100),
                )
            else:
                dpg.add_text(
                    f"Rules for {current_phase.title()} Phase:",
                    color=(180, 160, 120),
                )
                for rule in relevant_rules[:5]:
                    # Truncate description for display
                    desc = rule.description[:80] + "..." if len(rule.description) > 80 else rule.description
                    dpg.add_text(f"• {rule.name}", color=(160, 180, 160))
                    dpg.add_text(f"  {desc}", color=(120, 120, 120), wrap=270)

    def _set_result(self, text: str):
        """Set the result display text."""
        if dpg.does_item_exist(self._result_tag):
            dpg.delete_item(self._result_tag, children_only=True)

        with dpg.group(parent=self._result_tag):
            dpg.add_text(text, wrap=280)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_doctrine(self, doctrine: Doctrine):
        """Set AI doctrine programmatically."""
        self._ai.doctrine = doctrine
        dpg.set_value(self._doctrine_tag, doctrine.display)
        dpg.set_value(f"{self._tag}_doctrine_desc", doctrine.description)

    def set_aggression(self, aggression: Aggression):
        """Set AI aggression programmatically."""
        self._ai.aggression = aggression
        dpg.set_value(self._aggression_tag, aggression.display)

    def check_morale(self, unit: RosterUnit) -> str:
        """
        Check morale for a unit based on casualties.

        Args:
            unit: The unit to check

        Returns:
            Morale result string
        """
        # Calculate casualties percentage
        total_wounds = unit.wounds_max * unit.models_max
        current_wounds = (unit.wounds_max * (unit.models_current - 1)) + unit.wounds_current
        casualties_pct = 1.0 - (current_wounds / total_wounds)

        result = self._ai.roll_morale(casualties_pct)

        self._set_result(
            f"MORALE CHECK: {unit.name}\n\n"
            f"Casualties: {int(casualties_pct * 100)}%\n"
            f"Result: {result}"
        )

        return result

    def get_decision(self) -> Optional[TacticalDecision]:
        """Generate and return a decision without displaying."""
        situation = self._build_situation_string()
        return self._ai.decide(situation)

    def _rebuild_in_parent(self, new_parent: str):
        """Rebuild the panel content in a new parent (for pop-out support)."""
        # Delete existing root if it exists
        root_tag = f"{self._tag}_root"
        if dpg.does_item_exist(root_tag):
            dpg.delete_item(root_tag)

        # Update parent and rebuild
        self.parent = new_parent
        self._build()
