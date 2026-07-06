# War Room Decree — Oracle Audit
*Session: 2026-07-06. Query: "I made a solo RPG and wargaming program; I think it's a giant mess. How do we improve it?"*
*Council: oracle-architect, code-reviewer, qa-tester. Full analyses in `analysis/`.*

## The Verdict

**Oracle is not a giant mess. It is a good logic core buried under ~9,000 lines of dead code, wearing a sloppy GUI, with one real crash bug.**

Where the three auditors agree:
- The golden rule (*logic in models, pixels in views, rules in TOML*) is **respected where it matters** — zero DearPyGui imports outside `oracle/gui/`, logic modules 88–96% type-hinted, callbacks correctly use `user_data`.
- The rot is concentrated: dead wargame UIs, GUI-layer quality, RNG discipline, and duplication.

## The Decree — in priority order

### P0 — Fix what is broken today (small, do first)
1. **`.plot_threads` crash (CRITICAL).** `SessionMemory` has `.threads`, but 5 call sites use `.plot_threads` → runtime `AttributeError` during complication generation and meaning-table context. `complication_generator.py:145,246,354`, `meaning.py:194,310`. Also why the test suite is flaky.
2. **PatternMatcher misroutes "rest" → "craft"** (`oracle/gm/nlp/patterns.py`, deterministic test failure).
3. **2 broken doctor_who TOMLs** (`complications/hopeful.toml:82`, `neutral.toml:105` — table names with spaces need quotes) **and** make `tables.py:188` log/surface parse errors instead of silently returning None.
4. **Commit the at-risk work**: `chaos_gifts.toml`, `oracle/data/fantasy/lore/`, `production/`, modified files. Delete `nul`, move/delete the two stray root test scripts (pytest collection trap that launches a GUI).

### P1 — Delete the dead weight (~9k LOC, biggest "mess" reduction)
5. After a salvage check for unique features/loaders: delete `oracle/gui_oracle/` (empty), `oracle/gui/wargame_app.py` (3,303 lines, no live entry point), `oracle/gui/views/wargame/` + `views/wargame_panel.py` (orphaned 10-panel library), `oracle/gui/models/roster_model.py` (only the dead panels use it). The live wargame UI is the one inline in `oracle_app.py`.
   *Tradeoff (Devil's Advocate): the dead panel library (ArmyBuilder, RulesBrowser, CasualtyTracker…) may contain features better than the live inline sidebar. Salvage-check before deleting; git keeps the history regardless.*

### P2 — Structural fixes (do in this order; each unblocks the next)
6. **Seedable RNG.** Replace `secrets.SystemRandom()` in `wargame/engine/base.py:265` and `wargame/ai/opponent.py:134` with injectable `random.Random`; consolidate the two `DiceRoller` classes (`dice.py` vs `engine/base.py`) into the seedable one. *This is the single biggest testability blocker.*
7. **Extract the shared combat pipeline.** `resolve_shooting`/`resolve_melee` are ~1,000 lines duplicated across 4 engines with a verbatim casualty loop. Template method on `base.py` + `_apply_wounds_to_models()` helper.
8. **Write engine tests** (now possible with seeded RNG). Wargame engines, roster, generators currently have zero coverage; ~90% of game logic is untested.
9. **De-duplicate domain enums**: `Doctrine` (3×), `Scale` (3×), `Mode` (2×) — one home, imported everywhere.
10. **Pull rules out of the live GUI**: `_detect_likelihood`, `_generate_random_event` (205 lines), morale/phase/casualty handlers out of `oracle_app.py` into models; unify command dispatch so `cli.py` and `oracle_app.py` share one handler set instead of two parallel copies of every game verb.
11. **`load_toml(path)` helper** for all 21 load sites (fixes the one unwrapped load in `oldhammer.py:78`).

### P3 — Polish (when touching those files anyway)
12. Split `importers.py` (2,536 lines) into `importers/{bsdata,newrecruit,toml,pdf}.py`; rename builtin-shadowing `class ImportError`.
13. Split `gm/orchestrator.py`: handler registry for the ~25 intent methods; extract `_generate_*` prose to a NarrativeGenerator with flavor text in TOML.
14. GUI hygiene: remove 7 DEBUG prints, fix the ~10 silent excepts, raise type hints from 6–9% toward parity with logic modules.
15. `pyproject.toml`: make `dearpygui` a core dependency (GUI is the product); consolidate the two near-identical launchers; consider worker threads for orchestrator calls if input ever feels laggy (*deferred: current orchestrator is pure Python and fast; threading adds complexity for no felt benefit yet*).

## Named Sacrifices (Law 2)
- Deleting the dead panels sacrifices any half-built features in them — mitigated by salvage check + git history.
- Extracting the combat pipeline risks changing subtle per-system behavior — mitigated by writing seeded characterization tests (P2 #8) against current behavior *before* refactoring.
- Skipping threading (P3) accepts brief UI stalls on the heaviest inputs in exchange for simplicity.

## The Summoner decides where to begin. Recommended: P0 items 1–4 in one sitting (an afternoon), then P1 as a single deletion commit.
