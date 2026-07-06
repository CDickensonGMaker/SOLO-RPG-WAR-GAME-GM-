# Oracle Architecture Audit — oracle-architect

Scope: 91 `.py` files, ~47k LOC. Golden rule = *logic in models, pixels in views, numbers in TOML*. Evidence is `file:line`.

## Headline

The **model/logic layer is actually clean** — zero DearPyGui imports outside `oracle/gui/`. The rot is elsewhere: **~9,000 lines of orphaned/duplicate wargame code**, three parallel wargame UIs, three parallel roster/enum definitions, and a GUI that reimplements the CLI's command parser with game rules baked into view methods.

---

## 1. Layering violations

### 1a. Model layer is DPG-clean (good — no action)
All 24 files containing `dpg.` live under `oracle/gui/`. `oracle/gm/`, `oracle/wargame/`, root modules (`fate.py`, `dice.py`, `roster.py`, `generators.py`, `gamesystems.py`, `importers.py`, `tables.py`, `mood.py`), and `oracle/gui/models/` are all free of DearPyGui. The golden rule's model→view direction is respected.

### 1b. Game rules hardcoded in view/app files — **MAJOR**
- `oracle/gui/wargame_app.py:173` `FORCE_ORG_2E = {...}` — force-organization min/max slot limits (a ruleset number) hardcoded at module level in a view file. Belongs in TOML.
- `oracle/gui/wargame_app.py:246` `GAME_SYSTEMS = {...}` with embedded rule text (`"WWI horror skirmish - 2d6 vs 7 system"`, line 264).
- `oracle/gui/wargame_app.py:269` `COMMANDER_ARCHETYPES = [...]`.
- `oracle/gui/wargame_app.py:182` `validate_force_org()` and `:219` `validate_unit_size()` — **rules validation logic living in a view module**.
- `oracle/gui/wargame_app.py` chaos-mutation dice rolling inside panel methods (`_roll_mutation` :1873, `_roll_multiple_mutations` :1863) — game logic in a UI class.

### 1c. Game logic inside the live GUI (`oracle_app.py`) — **MAJOR**
`OracleApp` (the app Oracle.bat actually runs) embeds rules in view methods:
- `oracle/gui/oracle_app.py:1059` `_detect_likelihood()` — oracle odds logic.
- `oracle/gui/oracle_app.py:1344-1554` `_generate_random_event()` — ~210 lines of event-generation rules/prose in the view.
- `:1142` `_handle_morale_command`, `:1176` `_handle_phase_command`, `:1240` `_trigger_ai_turn`, `:1300` `_handle_casualties_command` — wargame rules driven from GUI command handlers.
- Module-level `GAME_SYSTEMS`, `SETTINGS`, `MOODS`, `PERSONALITIES_LIST` string lists (`:40-50`) hardcoded rather than sourced from TOML/model.

### 1d. Borderline (minor)
`oracle/gui/views/wargame/unit_detail.py:168` `stat_order = ["M","WS","BS","S","T","W","I","A","Ld","Sv"]` — a Warhammer stat-line ordering. Presentation-ish, but it's system-specific knowledge in a view.

Models themselves (`roster_model.py`, `wargame_data.py`) mostly load from TOML and use only structural maps (`slot_mapping`, `type_to_slot`) — acceptable.

---

## 2. Entry-point sprawl

The task's mapping is **wrong on one point**. Actual wiring:

| Trigger | Runs | Class | Status |
|---|---|---|---|
| `Oracle.bat` | `python -m oracle.gui.oracle_app` | `OracleApp` | **LIVE**. Note: bypasses `oracle_launcher.py` entirely (skips its dependency check). |
| `Birthright.bat` | `python -m oracle.gui.launcher` → `oracle.gui.app` | `BirthrightApp` | LIVE |
| pyproject `oracle` | `oracle.main:main` → `cli.run_cli` | `OracleCLI` | LIVE (terminal) |
| pyproject `oracle-gui` | `oracle.gui.oracle_launcher:main` | `OracleApp` | redundant wrapper; only the console-script uses it, `.bat` doesn't |
| pyproject `birthright` | `oracle.gui.launcher:main` | `BirthrightApp` | LIVE |
| `oracle/gui/wargame_app.py` `__main__` :3298 | `WargameApp` | — | **DEAD**: no .bat, no console script, not exported by `gui/__init__.py` |

Findings:
- `oracle/gui/oracle_launcher.py` (36 lines) and `oracle/gui/launcher.py` (51 lines) are near-identical thin dependency-check wrappers. `oracle_launcher` is dead-ended: Oracle.bat calls `oracle_app` directly, so the only caller is the rarely-used `oracle-gui` console script. **Minor** — consolidate to one launcher.
- `WargameApp` in `wargame_app.py` has **no live entry point** — 3,303 lines reachable only by manually running the module. **Critical dead weight.**

---

## 3. Duplication & dead code — **CRITICAL**

### 3a. `oracle/gui_oracle/` — empty dead shell
`oracle/gui_oracle/views/` contains **0 files** (confirmed `find … -type f` = 0). Pure cruft directory; delete.

### 3b. Three parallel wargame UIs
1. **Live**: `oracle_app.py` inline wargame (`_build_wargame_sidebar` :587, `_generate_wargame_opening` :808, `_refresh_wargame_sidebar` :1705) using `get_wargame_data` + `WargameAI`.
2. **Orphan A**: `wargame_app.py` `WargameApp` + `BattleChatPanel`/`ForcePanel`/`BattleStatePanel`/`PhaseGuidePanel` (3,303 lines) — not imported anywhere.
3. **Orphan B**: `oracle/gui/views/wargame/` package (10 panels: `GameSelectorPanel`, `ArmyBuilderPanel`, `UnitDetailPanel`, `ForceDisplayPanel`, `CasualtyTracker`, `TurnTrackerPanel`, `TacticalAIPanel`, `RulesBrowserPanel`, `battle_events`, `equipment_dialog`) + `views/wargame_panel.py`. These import **only each other** — no external consumer (`oracle_app.py` imports none of them; `wargame_app.py` imports none of them). Entire subtree is dead.

### 3c. Two parallel roster models
- `oracle/roster.py` (1,647 lines): `Roster`, `RosterUnit`, `RosterManager`, `SlotType`, `UnitStatus`. Used by the wargame engine layer (`wargame/engine/*`, `wargame/ai/opponent.py`, `wargame/battle/coordinator.py`) — legitimately live.
- `oracle/gui/models/roster_model.py`: a **second** roster model, consumed **only** by the orphaned `gui/views/wargame/*` panels (§3b). Dead alongside them.

### 3d. Duplicate enum / class definitions
- `Doctrine` defined **3×**: `cli.py:50`, `gui/views/wargame_panel.py:21`, `wargame/ai/tactical.py:33`.
- `Scale` defined **3×**: `cli.py:59`, `mood.py:98`, `gui/views/wargame_panel.py:31`.
- `Mode` defined **2×**: `cli.py:44`, `mood.py:14`.
- `DiceRoller` defined **2×**: `dice.py:45`, `wargame/engine/base.py:249`.
There is no single source of truth for these core domain enums.

### 3e. CLI vs GUI command duplication
`cli.py` implements ~40 `_cmd_*` handlers (roll, ask, chaos, morale, event, doctrine, aggression, etc.). `oracle_app.py` re-implements the same game actions as `_handle_*_command` methods (`:938`–`:1344`). Two independent parsers/dispatchers over the same game verbs. Also, `cli.py:879 _import_pdf` and `:993 _import_bsdata` embed import-orchestration that overlaps `importers.py`'s public `auto_import`/`import_bsdata` functions.

---

## 4. Module structure

Root-level domain modules (`fate.py`, `dice.py`, `mood.py`, `npc.py`, `journal.py`, `roster.py`, `generators.py`, `gamesystems.py`, `tables.py`, `importers.py`, `birthright_character.py`, `windows.py`) as a flat logic layer is **reasonable** and correctly DPG-free. Real structural problems:

- **`gui/models/` duplicates root models.** `roster_model.py` vs root `roster.py`; `wargame_data.py`/`campaign.py`/`game_state.py` are a second model layer. The project has two "model" homes (`oracle/*` and `oracle/gui/models/`) with overlapping responsibilities and no rule for which to use — the root ones feed the engine/CLI, the gui/models ones feed (mostly dead) panels.
- **`gamesystems.py` is a shared hub** imported by both live models and dead panels — fine, but it ties the orphaned cluster in, masking that the cluster is dead.
- Enum homelessness (§3d) — `Doctrine`/`Scale`/`Mode`/`Aggression` should live once in a `wargame`/domain module and be imported everywhere.
- **Naming collision risk**: `importers.py:67` defines `class ImportError` shadowing the builtin.

---

## 5. God files — responsibilities & seams

**`oracle/gui/wargame_app.py` (3,303) — DEAD, do not refactor, delete.** For the record it jams: module-level rules constants + TOML loaders (`load_factions/wargear/chaos_gifts/detachments` :73–165), rules validation (:182, :219), and 5 fat panel classes including `ForcePanel` with ~30 methods spanning add-unit dialogs, wargear randomizer, chaos-mutation dice roller, roster save/load/validate. If it were live, seams = loaders→module, validation→model, each panel→own file. It's not live; recover any unique TOML-loader logic then remove.

**`oracle/importers.py` (2,536) — split by importer.** Four unrelated subsystems in one file: `BSDataImporter` (BattleScribe XML, :232–1010, ~780 lines), `NewRecruitImporter` (:1012), `TOMLImporter` (:1238), and an entire **PDF subsystem** (`PDFTable`/`PDFPage`/`PDFContent`/`PDFImporter`, :1437–end, ~1,000 lines). Natural seam: `importers/{bsdata,newrecruit,toml,pdf}.py` + shared `ImportedUnit`. PDF importing shares nothing with roster importing. Also rename the shadowing `ImportError`.

**`oracle/gm/orchestrator.py` (2,270) — dispatch + content generator fused.** `GMOrchestrator` has ~25 `_handle_<verb>` intent methods (:429–1372: talk, search, oracle, travel, investigate, fight, rest, use, observe, describe, social, follow, flee, defend, craft, trade, pray…) **plus** ~30 `_generate_*`/`_get_*_content` narrative-prose methods (:533–2183). Seams: (1) replace the giant if/elif intent switch with a handler registry/dispatch table; (2) extract all `_generate_*` prose into a `NarrativeGenerator`, and move the hardcoded template strings to TOML (much of it is literal flavor text).

**`oracle/gui/oracle_app.py` (2,193) — view + parser + rules + persistence.** `OracleApp` mixes: UI layout (`_build_*` :188–587), an embedded command parser/NLU (`_process_input` :900, `_handle_*_command` :1102–1344), **game rules** (`_detect_likelihood` :1059, `_generate_random_event` :1344 ~210 lines, morale/phase/AI-turn), rendering, and session save/load (:2061–2098). Seams: pull command parsing into a shared brain/dispatcher (reuse cli.py's), move rules methods to models, split wargame sidebar into its own controller.

**`oracle/cli.py` (1,709) — command hub with embedded rules + duplicate enums.** `OracleCLI` = ~40 `_cmd_*` handlers. Redefines `Mode`/`Doctrine`/`Scale` locally (:44–59). Embeds import orchestration (`_import_pdf` :879, `_import_bsdata` :993). Seams: import enums from domain modules; delegate imports to `importers.py`; extract a shared command dispatcher so the CLI and `oracle_app.py` stop maintaining two copies of every game verb.

---

## Prioritized top fixes

1. **CRITICAL — Delete dead code.** Remove `oracle/gui_oracle/` (empty), `oracle/gui/wargame_app.py` (3.3k, no entry point), `oracle/gui/views/wargame/` + `views/wargame_panel.py` (orphaned panel library), and `oracle/gui/models/roster_model.py` (only the dead panels use it). First salvage any unique TOML-loader/validation logic worth keeping. Removes ~7–9k LOC and eliminates two of the three wargame UIs.
2. **CRITICAL — Pick one wargame UI.** After #1, `oracle_app.py`'s inline wargame is the survivor. Decide whether the deleted panel library had features worth porting *before* deleting; otherwise the live inline path stands.
3. **MAJOR — De-duplicate core enums.** Single home for `Doctrine`, `Scale`, `Mode`, `Aggression`, `DiceRoller`; delete the copies in `cli.py`, `mood.py`, `wargame_panel.py`, `dice.py` vs `engine/base.py`.
4. **MAJOR — Extract rules out of the live GUI.** Move `_detect_likelihood`, `_generate_random_event`, morale/phase/casualty logic out of `oracle_app.py` into models/brain; move random-event and generated prose to TOML.
5. **MAJOR — Unify command dispatch.** `oracle_app.py` and `cli.py` should share one command/brain dispatcher instead of two parallel `_handle_*_command`/`_cmd_*` sets; route both through `orchestrator`/`brain`.
6. **MINOR — Consolidate launchers.** Merge `oracle_launcher.py` and `launcher.py`; make `Oracle.bat` go through the launcher (for the dependency check) instead of calling `oracle_app` directly.
7. **MINOR — Split `importers.py`** into per-format modules (esp. carve out the ~1k-line PDF subsystem) and rename the builtin-shadowing `ImportError`.
