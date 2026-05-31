# Wargame Mode Enhancement Plan

**Goal:** Make wargame mode a complete, distinct experience for playing tabletop miniature games with tactical AI opponents.

**Date:** 2026-05-30
**Status:** Planning

---

## Current State (Verified)

### What Exists and Works

1. **WargameAI Module** (`oracle/wargame.py`)
   - Full tactical AI with `decide()`, `roll_priority()`, `roll_morale()`, `roll_event()`
   - Doctrine and Aggression enums for AI behavior
   - Threat analysis and weighted decision making
   - Render functions for formatted output

2. **WargameState Dataclass** (`oracle_app.py` lines 94-106)
   - Fields: turn, phase, player_casualties, enemy_casualties
   - Fields: player_units, enemy_units, objectives, battle_log
   - Fields: scenario, victory_conditions
   - Note: Duplicated in `wargame_panel.py` - needs consolidation

3. **Command Routing** (`oracle_app.py` lines 738-756)
   - Routes for: `/situation`, `/target`, `/morale`, `/event`, `/phase`, `/casualties`
   - **Problem:** Routes exist but handler methods are not implemented

4. **Wargame View Panels** (`oracle/gui/views/wargame/`)
   - `TurnTrackerPanel` - Turn/phase tracking, loads phases from TOML
   - `TacticalAIPanel` - Full AI integration with roster data
   - `army_builder.py`, `casualty_tracker.py`, `battle_events.py`
   - `force_display.py`, `game_selector.py`, `rules_browser.py`

5. **WargameDataModel** (`oracle/gui/models/wargame_data.py`)
   - `get_phases()` - Loads phase list from game system TOML
   - `get_phase_details()` - Full phase info with steps and actions
   - `get_turn_structure()` - Turn type (alternating activation, etc.)
   - Integration with GameSystemManager

6. **TOML Phase Files** (already exist)
   - `oracle/data/wargames/oldhammer_2e/phases.toml`
   - `oracle/data/wargames/trench_crusade/phases.toml`
   - `oracle/data/wargames/old_world/phases.toml`
   - `oracle/data/wargames/age_of_fantasy/phases.toml`
   - `oracle/data/wargames/grimdark_future/phases.toml`

### What Is Broken/Missing

1. **Command Handlers** - The routing calls methods that do not exist:
   - `_handle_situation_command(text)` - NOT IMPLEMENTED
   - `_handle_target_command(text)` - NOT IMPLEMENTED
   - `_handle_morale_command(text)` - NOT IMPLEMENTED
   - `_handle_event_command()` - NOT IMPLEMENTED
   - `_handle_phase_command(text)` - NOT IMPLEMENTED
   - `_handle_casualties_command(text)` - NOT IMPLEMENTED

2. **WargameState Not Initialized** - `self.wargame_state` is set to `None` but never created

3. **Wargame Opening** - Currently uses RPG quest opening for all game types

4. **Wargame Sidebar** - Sidebar shows RPG elements (scene, quest, NPCs, threads)

5. **Existing Panels Not Integrated** - TacticalAIPanel, TurnTrackerPanel exist but aren't used in oracle_app.py

---

## Implementation Steps

### Step 1: Implement Command Handlers (First Slice - Do This First)

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer
**Testable:** Type commands and see formatted output

Add these methods to OracleApp class:

```python
def _handle_situation_command(self, text: str):
    """AI analyzes situation and decides action."""
    # Extract situation description after /situation or /sit
    situation = text.split(" ", 1)[1] if " " in text else ""
    if not situation:
        self._add_message("system", "Usage: /situation <description of battlefield>")
        return

    self._add_message("user", f"*Situation: {situation}*")

    decision = self.wargame_ai.decide(situation)
    rendered = self.wargame_ai.render_decision(decision)
    self._add_message("gm", rendered, "event")

def _handle_target_command(self, text: str):
    """AI prioritizes targets from list."""
    # Parse comma-separated targets
    target_text = text.split(" ", 1)[1] if " " in text else ""
    if not target_text:
        self._add_message("system", "Usage: /target <target1>, <target2>, ...")
        return

    targets = [t.strip() for t in target_text.split(",")]
    self._add_message("user", f"*Evaluating targets: {', '.join(targets)}*")

    selected = self.wargame_ai.roll_priority(targets)
    self._add_message("gm", f"**Target Priority:** {selected}", "event")

def _handle_morale_command(self, text: str):
    """Check morale at given casualty percentage."""
    # Parse percentage
    parts = text.split()
    if len(parts) < 2:
        self._add_message("system", "Usage: /morale <casualty_percent>")
        return

    try:
        pct = float(parts[1].rstrip("%")) / 100.0
    except ValueError:
        self._add_message("system", "Invalid percentage. Use: /morale 25")
        return

    self._add_message("user", f"*Morale check at {int(pct*100)}% casualties*")
    result = self.wargame_ai.roll_morale(pct)
    self._add_message("gm", f"**Morale Result:** {result}", "event")

def _handle_event_command(self):
    """Roll random battle event."""
    self._add_message("user", "*Rolling battle event...*")
    event = self.wargame_ai.roll_event()
    self._add_message("gm", f"**Battle Event:** {event}", "event")

def _handle_phase_command(self, text: str):
    """Advance or set phase."""
    # Initialize wargame state if needed
    if not self.wargame_state:
        self.wargame_state = WargameState()

    # TODO: Load phases from game system TOML
    phases = ["Movement", "Shooting", "Combat", "Morale"]

    current_idx = phases.index(self.wargame_state.phase) if self.wargame_state.phase in phases else 0
    next_idx = (current_idx + 1) % len(phases)

    if next_idx == 0:
        self.wargame_state.turn += 1

    self.wargame_state.phase = phases[next_idx]

    self._add_message("gm",
        f"**Turn {self.wargame_state.turn} - {self.wargame_state.phase} Phase**",
        "event")

def _handle_casualties_command(self, text: str):
    """Track casualties."""
    if not self.wargame_state:
        self.wargame_state = WargameState()

    # Parse: /casualties player +5 or /casualties enemy +10
    parts = text.split()
    if len(parts) < 3:
        self._add_message("system", "Usage: /casualties <player|enemy> <+/-amount>")
        return

    side = parts[1].lower()
    try:
        amount = int(parts[2])
    except ValueError:
        self._add_message("system", "Invalid amount")
        return

    if side == "player":
        self.wargame_state.player_casualties += amount
        current = self.wargame_state.player_casualties
    else:
        self.wargame_state.enemy_casualties += amount
        current = self.wargame_state.enemy_casualties

    self._add_message("gm",
        f"**Casualties Updated:** {side.title()} now at {current}",
        "event")
```

### Step 2: Initialize WargameState on Session Start

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer
**Testable:** Start wargame session, run `/phase`

In `_initialize_session()`, after creating wargame_ai:

```python
if self.config.game_type == "wargame":
    self.wargame_ai = WargameAI()
    # ... existing doctrine/aggression setup ...

    # Initialize wargame state
    self.wargame_state = WargameState()
    self.wargame_state.turn = 1
    self.wargame_state.phase = "Deployment"
```

### Step 3: Wargame-Specific Opening

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer + gamemaster-designer
**Testable:** Start wargame session, see battle setup instead of quest

Create `_generate_wargame_opening()` method:
- Display game system and doctrine
- Show deployment phase prompt
- Present tactical situation
- List AI force composition (placeholder until roster integration)
- Prompt: "Deploy your forces. What is your battle plan?"

Modify `_generate_opening()` to branch:
```python
def _generate_opening(self):
    if self.config.game_type == "wargame":
        self._generate_wargame_opening()
    else:
        self._generate_rpg_opening()
```

### Step 4: Wargame-Specific Sidebar

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer
**Testable:** Start wargame, see battle info in sidebar

Create `_build_wargame_sidebar()`:
- Battle Status section: Turn, Phase, Game System
- AI Info section: Doctrine, Aggression
- Casualties section: Player %, Enemy %
- Objectives section (placeholder for now)

Modify `_build_sidebar()` to branch based on game type.

### Step 5: Integrate Existing TacticalAIPanel

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer
**Testable:** Click "Analyze Situation" in sidebar, see decision

The TacticalAIPanel already exists with full functionality. Consider:
- Adding it to wargame sidebar as collapsible section
- Or making it a pop-out panel
- Wire its callbacks to chat output

### Step 6: Phase Loading from TOML

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer
**Testable:** Select Trench Crusade, see alternating activation phases

Use WargameDataModel to load phases:
```python
from oracle.gui.models.wargame_data import get_wargame_data

wargame_data = get_wargame_data()
wargame_data.set_system(self.config.game_system)
phases = wargame_data.get_phases()
turn_structure = wargame_data.get_turn_structure()
```

### Step 7: AI Turn Integration (Enhancement)

**Files:** `oracle/gui/oracle_app.py`
**Agent:** dpg-engineer + gamemaster-designer
**Testable:** Advance to "AI Turn" phase, see AI decisions auto-generated

When phase advances to AI's turn:
- Auto-call `wargame_ai.decide()` with current situation
- Display threat assessment
- Show AI's chosen action
- Narrate the action with game-system flavor

---

## Risks and Concerns

1. **Duplicate WargameState** - Two WargameState classes exist. Need to consolidate before adding more code.

2. **Scope Creep** - Full army roster integration, scenario generation, victory conditions are larger features. Keep initial work focused on command handlers.

3. **Testing Gap** - No automated tests for wargame commands. Consider adding basic tests for each handler.

4. **UI Layout** - Sidebar may become crowded with both RPG and wargame elements. Keep them cleanly separated.

---

## First Slice Recommendation

**Implement Step 1 only (Command Handlers)**

This is the smallest useful change:
- Fixes the broken routing
- Makes wargame mode functional
- Uses existing WargameAI code
- Requires no UI changes
- Can be tested immediately by typing commands

After Step 1 works, do Steps 2-3 together (state init + opening), then Step 4 (sidebar).

---

## Agent Assignments

| Step | Primary Agent | Support |
|------|---------------|---------|
| 1 | dpg-engineer | code-reviewer |
| 2 | dpg-engineer | - |
| 3 | dpg-engineer | gamemaster-designer (flavor text) |
| 4 | dpg-engineer | - |
| 5 | dpg-engineer | - |
| 6 | dpg-engineer | - |
| 7 | dpg-engineer | gamemaster-designer (narration) |

---

## Definition of Done

- [x] All 6 command handlers implemented and working
- [x] WargameState initialized on wargame session start
- [x] Wargame opening displays battle setup, not quest
- [x] Sidebar shows wargame-relevant info when in wargame mode
- [x] Code reviewed for golden rule compliance (logic in models, pixels in views)
- [x] Phases loaded from TOML with error handling
- [x] AI turn integration with automatic tactical decisions

## Completion Notes (2026-05-30)

All features implemented and code-reviewed. Key changes:
- 6 command handlers: /situation, /target, /morale, /event, /phase, /casualties
- WargameState auto-initialized on wargame session start
- _generate_wargame_opening() shows tactical deployment prompt
- _build_wargame_sidebar() shows Turn/Phase/Doctrine/Casualties/Objectives
- _handle_phase_command() loads phases from TOML with fallback
- _trigger_ai_turn() generates automatic AI decisions on AI phases

Code review issues fixed:
- TOML error handling with try/except
- WargameState initialization cleanup
- Phase case standardization
- Safe threat icon lookup
