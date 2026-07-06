# QA Audit Report — C:\Users\caleb\oracle (READ-ONLY)

## 1. Test Suite Results

**Command:** `python -m pytest tests/ -q` (pytest-timeout not installed; `--timeout` rejected)

| Run | Result |
|-----|--------|
| 1 | 3 failed, 37 passed (0.45s) |
| 2 | 3 failed, 37 passed |
| 3 | 4 failed, 36 passed |
| 4 | 4 failed, 36 passed |

**Suite is flaky** — failure set changes between runs (unseeded `random` in GM logic; no `random.seed()` anywhere in tests/).

**Failures and root causes:**

- **`TestPatternMatcher::test_rest_camp`** — deterministic. PatternMatcher classifies a rest/camp input as intent `'craft'` instead of `'rest'`. Real bug in `oracle/gm/nlp/patterns.py`. **Severity: HIGH**
- **`TestGMOrchestrator::test_process_smart_*` / `TestSmartGMIntegration::test_mini_session`** — intermittent `AttributeError: 'SessionMemory' object has no attribute 'plot_threads'` at `oracle/gm/complication_generator.py:145`. `SessionMemory` defines `self.threads` (`oracle/gm/memory.py:118`), but **5 call sites reference the nonexistent `.plot_threads`**: `complication_generator.py:145,246,354` and `meaning.py:194,310`. This is a live production crash whenever complication generation or meaning-table context takes those code paths, not just a test problem. Flakiness is because complication type selection is random. **Severity: CRITICAL**

**Stray root-level files:**
- `test_display.py` — manual DearPyGui diagnostic script; builds a GUI at module top level. pytest collection trap (can launch/hang a GUI window). Untracked.
- `test_oracle_minimal.py` — minimal GUI app from past blank-screen debugging. Same hazard. Untracked.
- Neither is a real test. **Severity: MEDIUM**

## 2. Coverage Gaps

Entire test suite = **one file**: `tests/test_smart_gm.py` (40 tests). Covers only `oracle/gm/brain.py`, `oracle/gm/memory.py`, `oracle/gm/nlp/patterns.py`, `oracle/gm/nlp/resolver.py`, plus orchestrator smoke paths.

| Module | Lines | Tests |
|--------|------:|-------|
| oracle/importers.py | 2,536 | **none** |
| oracle/gm/orchestrator.py | 2,270 | partial (indirect) |
| oracle/roster.py | 1,647 | **none** |
| oracle/generators.py | 1,544 | **none** |
| oracle/gamesystems.py | 1,355 | **none** |
| oracle/wargame/ (engines + battle/coordinator) | ~3,700 | **none** |
| oracle/wargame/ai/ (commander, opponent, tactical, narrator) | ~2,600 | **none** |
| oracle/gm/complication_generator.py | 541 | none (crashes when hit indirectly) |
| oracle/gm/meaning.py, pacing.py, npc_memory.py, world_model.py, responder.py | ~2,400 | **none** |
| oracle/dice.py, fate.py, tables.py, journal.py, npc.py, mood.py | ~1,500 | **none** |
| All GUI | large | **none** |

~90%+ of game logic by line count has zero test coverage. **Severity: HIGH**

## 3. Entry-Point Smoke Tests

All six imports succeed: `oracle.gui.oracle_launcher`, `oracle.gui.launcher`, `oracle.gui.oracle_app`, `oracle.gui.wargame_app`, `oracle.gui.app`, `oracle.cli`, plus `oracle.main`. **Severity: OK**

## 4. TOML Data Audit

**Inventory:** exactly **330 TOML files** under `oracle/data/`, ~15 setting packs each with `complications/ encounters/ locations/ npcs/`, plus `core/` (26 files) and `wargames/` (5 systems).

**Parse failures: 2 of 330** — both doctor_who, same authoring mistake (bare table names with spaces):
- `oracle/data/doctor_who/complications/hopeful.toml:82` — `[timey-wimey salvation]` (needs `["timey-wimey salvation"]`)
- `oracle/data/doctor_who/complications/neutral.toml:105` — `[temporal complications]`

`oracle/tables.py:188` catches `TOMLDecodeError` and **silently returns None**, so these files' content is invisibly missing at runtime with no warning. **Severity: HIGH** (silent data loss)

**Schema inconsistency across wargame systems:**
- `rules.toml`: top keys `[rules]` only vs `rules+system` vs `rules+edition` depending on system.
- `wargear.toml`: metadata key is `metadata` in 3 systems but `wargear_info` in oldhammer_2e; category keys vary; old_world has no wargear.toml (uses `magic_items.toml`).
- `phases.toml`: trench_crusade lacks `name`/`description`/`special_rules_summary`; oldhammer uses `special_actions`.
- Loaders must special-case per system. **Severity: MEDIUM**

**Data-dir hygiene:** `test_detachments.toml` is scratch data in the shipping tree (untracked). `chaos_gifts.toml` and `oracle/data/fantasy/lore/` are real content **not committed** — one crash/reset and they're gone. **Severity: MEDIUM**

## 5. Repo Hygiene

- **Tracked junk:** none (437 tracked files; no `__pycache__`, `.egg-info`, `nul`, `sessions/`). `.beads/` partial tracking is by design. **OK**
- **`.gitignore` exists**, covers the important stuff. **LOW**
- **On-disk clutter:** zero-byte `nul` in root, `oracle.egg-info/`, `create_shortcut.vbs`, two stray test scripts. **LOW**
- **Uncommitted real work:** `oracle/data/fantasy/lore/`, `chaos_gifts.toml`, `.claude/agents/`, `production/`, modified `wargame_app.py` and `opponent.py`. At risk of loss. **MEDIUM**

## 6. pyproject.toml Sanity

- All three declared console scripts resolve. OK.
- **`dearpygui` only in the optional `[gui]` extra** but GUI is the primary product; plain `pip install .` yields broken `oracle-gui`/`birthright`. **MEDIUM**
- `requires-python = ">=3.10"` with conditional `tomli` backport — verify code actually try/except-imports `tomli`, else 3.10 support is broken.
- Description says "CLI-based" — stale. Cosmetic.
- `package-data` ships `data/**/*.toml` — good.

## Top Findings by Severity

1. **CRITICAL** — `.plot_threads` doesn't exist on `SessionMemory`; 5 call sites crash at runtime (`complication_generator.py:145,246,354`, `meaning.py:194,310`). Fix: use `.threads`.
2. **HIGH** — PatternMatcher misroutes "rest" intent to "craft".
3. **HIGH** — 2 broken doctor_who TOML files silently swallowed by loader.
4. **HIGH** — ~90% of game logic has zero tests.
5. **MEDIUM** — dearpygui not a core dependency; wargame TOML schema drift; uncommitted data; stray GUI-launching test scripts.
