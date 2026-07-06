# Oracle Code Quality Audit — code-reviewer

Scope: 91 `.py` files, ~47.5k LOC. Sampled all files flagged plus the 4 wargame engines. Raw findings below with file:line evidence.

## Headline metrics

| Metric | Result |
|---|---|
| `import threading` / real concurrency | **0 occurrences in entire codebase** |
| Unwrapped `tomllib.load` | 1 of 21 (`oldhammer.py:78`) |
| Bare `except:` | 1 (`wargame_app.py:1618`) |
| `except …: pass` swallow sites | ~10 |
| Mutable default args (`=[]`/`={}`) | **0 (clean)** |
| Closure-over-loop-var bugs | **0 (convention followed correctly)** |
| Module-level singletons | 11 + 6 lazy `global` |
| Direct `random.*` (non-injectable) call sites | ~19 files, orchestrator alone 45 |
| TODO/FIXME/HACK in code | 1 (`session_panel.py`) |
| DEBUG print leftovers | 7 (`wargame_app.py`) |

---

## 1. Bug patterns

**Blocking the UI thread — CONVENTION FULLY VIOLATED (High).**
There is **zero threading anywhere** (`import threading`, `Thread(target=`, `concurrent.futures`, `asyncio` all return nothing under `oracle/`). Every TOML load, brain/NLP call, and combat resolution runs synchronously on the DearPyGui callback thread. The CLAUDE.md rule "long work (brain, parsing, network) runs in a worker thread" is not implemented at all. `oracle/gm/orchestrator.py` (2270 lines of NLP/logic) is invoked directly from GUI callbacks.

**Bare `except:` (Med).** `oracle/gui/wargame_app.py:1618` — `except: pass` inside the checkbox-clearing loop swallows everything including `KeyboardInterrupt`/`SystemExit`.

**Silent `except Exception: pass` (Med).** Errors discarded with no logging:
- `oracle/gamesystems.py:850-851`
- `oracle/gm/world_model.py:154-155`
- `oracle/gm/nlp/content_router.py:399-400` (and `:379` `continue`)
- `oracle/gui/oracle_app.py:1201-1202`
- `oracle/gui/models/wargame_data.py:229-230` (observer errors — at least commented)
- `oracle/gm/__init__.py:58,65,80` — three `except ImportError: pass` hiding subsystem load failures ("shouldn't happen").

**Mutable defaults / loop-closures — CLEAN.** No `def f(x=[])` anywhere. DPG callbacks correctly bind via default args (`lambda s,a,c=n:`, `u=unit`, `i=item`) or `user_data=` (e.g. `wargame_app.py:1984-1986`, `2252-2255`). This convention is genuinely followed — note it as a strength.

**`does_item_exist` guards — partial (Low/Med).** `wargame_app.py`: 291 `add_*`, 46 `delete_item`, only 29 `does_item_exist`; `oracle_app.py`: 155 add / 28 delete / 20 guard. Guards exist but don't cover every recreate/delete path.

---

## 2. Convention compliance

**Type hints — bimodal.** Logic modules excellent, GUI abysmal:

| File | return-hint coverage |
|---|---|
| `gamesystems.py` | 96% |
| `orchestrator.py` | 95% |
| `roster.py` / `commander.py` | 94-95% |
| engines (base/opr/oldhammer/old_world/tc) | 93-94% |
| `importers.py` | 93% |
| `generators.py` | 88% |
| **`gui/wargame_app.py`** | **9%** |
| **`gui/oracle_app.py`** | **6%** |

**Function length — worst offenders (>80 lines):**
- `oracle/gui/oracle_app.py:1344` `_generate_random_event` — **205 lines**
- `oracle/gui/wargame_app.py:1094` `_show_add_unit_dialog` — 168
- `oracle/gui/wargame_app.py:1637` `_show_chaos_rewards_dialog` — 163
- `oracle/gui/oracle_app.py:657` `_generate_opening` — 150
- `oracle/importers.py:1602` `save_tables` — 150
- `oracle/wargame/engine/oldhammer.py:320` `resolve_shooting` — 166
- `oracle/wargame/engine/trench_crusade.py:273` `resolve_shooting` — 146
- `oracle/gui/oracle_app.py:188` `_build_startup_wizard` — 138
- `oracle/wargame/engine/opr.py:207` `resolve_shooting` — 130
- Plus ~20 more. GUI dialog builders and engine combat methods dominate.

**Unwrapped TOML (Low).** Only `oracle/wargame/engine/oldhammer.py:78` loads `tomllib.load(f)` with no try/except — a malformed `oldhammer_charts.toml` throws a raw stack trace. The other 20 load sites are wrapped (`tables.py:187`, `meaning.py:91`, `pacing.py:113`, etc.). Good compliance overall; one gap.

---

## 3. Copy-paste duplication (High)

**Combat resolution across 4 engines — CONFIRMED and quantified.** `resolve_shooting`/`resolve_melee` are reimplemented per engine with near-identical scaffolding:

| Engine | resolve_shooting | resolve_melee |
|---|---|---|
| `opr.py:207 / :342` | 130 | ~124 |
| `oldhammer.py:320 / :491` | 166 | 92 |
| `old_world.py:214 / :333` | 114 | 109 |
| `trench_crusade.py:273 / :424` | 146 | ~56 |

That's **~1,000+ lines** of parallel combat code. All share the identical skeleton: build `AttackResult` → parse weapon shots (with `isinstance(shots,str)` handling) → `roll_check` to hit → count hits → saves → **verbatim casualty loop**:
```python
while remaining >= current:
    remaining -= current; kills += 1; current = target_wounds
```
appears character-for-character in `opr.py:328-333`, `old_world.py:320-324`, and the others. Extract a `_apply_wounds_to_models()` and a template-method combat pipeline on `base.py`.

**Two divergent `DiceRoller` classes.** `oracle/dice.py:45` (seedable) and `oracle/wargame/engine/base.py:249` (SystemRandom) — duplicated, incompatible dice logic.

**TOML-loader boilerplate** (open-rb / `tomllib.load` / try) hand-repeated ~21 times; no shared `load_toml(path)` helper despite the convention calling for one.

---

## 4. Global state / singletons (Med)

Module-level mutable singletons instantiated at import:
`dice.py:174 _roller`, `fate.py:149 _oracle`, `gamesystems.py:1165 _manager`, `journal.py:516 _manager`, `mood.py:490 _manager`, `npc.py:479 _generator`, `roster.py:1453 _manager`, `tables.py:345-346 _loader/_roller`, `wargame/ai/tactical.py:567 _ai`, `wargame/engine/base.py:554 _default_roller`.
Plus lazy mutable globals via `global`: `generators.py` (5×: `_default_quest_gen`…), `gm/nlp/patterns.py:811`, `gui/models/roster_model.py:704 _battle_model`, `gui/models/wargame_data.py:665 _wargame_data`, `gui/views/wargame/battle_events.py:364 _event_system`.

God objects: `gm/orchestrator.py` (2270 L, 72 methods) and `gui/wargame_app.py` (3303 L, 95 methods) are passed/reached everywhere.

---

## 5. RNG testability — SPLIT (High)

**Good:** `dice.py:60 DiceRoller(rng=…)` and all `generators.py` classes (`:653, :772, :932` accept `rng: Optional[random.Random]`, default `random.Random()`, thread it through as `self.rng`). Fully seedable.

**Bad — large swaths call `random.*` directly, non-seedable:**
- `gm/orchestrator.py` — **45** direct calls
- `gm/responder.py` — 19; `gm/world_model.py` — 16; `birthright_character.py` — 19 (`:151,211,230,462-467`…)
- `wargame/ai/commander.py` — 15; `gm/personality.py` — 8; `gm/nlp/voice.py` — 7; `cli.py` — 9
- GUI: `oracle_app.py` 12, `wargame_panel.py` 9, `wargame_app.py` 9

**Worst:** the wargame combat `DiceRoller` (`base.py:265`) and `wargame/ai/opponent.py:134` use **`secrets.SystemRandom()`** — cryptographic RNG that **cannot be seeded**. Combat resolution and AI decisions are therefore impossible to test deterministically, directly contradicting "dice functions take an injectable RNG/seed." This is the single biggest testability blocker.

---

## 6. Print / debug leftovers (Low)

- **Stray DEBUG prints in shipping GUI:** `wargame_app.py:2010, 2016, 2019, 2022, 2025, 2066, 2070` (`print(f"DEBUG: …")`).
- Error-handling via `print()` in GUI instead of logging/dialog: `wargame_app.py:97,126,145,165,2203,2293,2320,2427`.
- `cli.py` prints (25) are legitimate CLI output.
- TODO/FIXME/HACK: only 1 in code (`gui/views/session_panel.py`). Not a concern.

---

## Prioritized Top-10 quality fixes

1. **Introduce worker threads for brain/NLP/parsing calls** (convention violation, whole app). Currently 0 threading; orchestrator runs on the UI callback thread → freezes on every input.
2. **Make wargame RNG seedable** — replace `secrets.SystemRandom()` in `base.py:265` & `opponent.py:134` with an injectable `random.Random`; unblocks all combat/AI testing.
3. **Extract shared combat pipeline** from the 4 duplicated `resolve_shooting`/`resolve_melee` (~1000 LOC) into `base.py` template methods + a `_apply_wounds` helper.
4. **Thread injectable `rng` through `orchestrator.py` (45 sites), responder, world_model, commander, birthright_character** instead of module `random.*`.
5. **Add a single `load_toml(path)` helper** and route all 21 load sites through it; fixes the unwrapped `oldhammer.py:78` and kills the boilerplate.
6. **Break up the 200/168/163/150-line functions** (`oracle_app._generate_random_event:1344`, `wargame_app._show_add_unit_dialog:1094`, `_show_chaos_rewards_dialog:1637`, `importers.save_tables:1602`).
7. **Raise GUI type-hint coverage** from 6-9% (`wargame_app.py`, `oracle_app.py`) toward the 90%+ the logic modules already hit.
8. **Remove the 7 DEBUG prints** (`wargame_app.py:2010-2070`) and convert error `print()`s to logging.
9. **Fix silent excepts** — bare `except:` at `wargame_app.py:1618` and the `except Exception: pass` sites (`gamesystems.py:850`, `world_model.py:154`, `content_router.py:399`, `oracle_app.py:1201`); log instead of swallow.
10. **Consolidate the two `DiceRoller` classes** (`dice.py` vs `base.py`) into one seedable implementation and reduce the 11 import-time singletons where feasible.

**Net read:** Not "a giant mess" uniformly. The *logic layer* (engines, generators, orchestrator, importers, roster) is well-typed, injects RNG where the author remembered to, and correctly follows the `user_data`/no-loop-closure rule. The rot is concentrated in: (a) the **GUI layer** (near-zero type hints, giant dialog functions, DEBUG prints, silent excepts), (b) **missing threading entirely**, (c) the **4-way combat-engine duplication**, and (d) **inconsistent RNG discipline** — seedable in dice/generators, non-seedable (`secrets`) exactly where combat testing matters most.
