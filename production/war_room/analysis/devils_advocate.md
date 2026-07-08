# Devil's Advocate — UI/UX Audit
*War Room session 2026-07-07. Lens: what every proposal costs, and whether the premise holds.*

Everything below was verified against the working tree today: `git status`/`log`, `bd list`,
pytest run, import checks, and reads of `oracle/gui/oracle_app.py`, `wargame_app.py`, `app.py`,
`launcher.py`, the launchers, and the two sibling analyses.

---

## Challenge 0 — The premise itself

The Summoner said, in one breath: *"I haven't tested it since the large fix yesterday, but I'm
sure it can still be improved."* Those two clauses are in tension. "Improve the UX" of an app
you have not launched since a P0-bugfix + 5,500-LOC deletion + RNG refactor is polishing a car
you haven't turned the key on. The council should not pretend the query is only about polish;
the first deliverable is *confidence the thing runs*, and the second is a short list of polish.

---

## Challenge 1 — Untested foundation

**Claim.** A UX pass on top of an unverified base is premature, and the tree is in a state
where a careless move breaks the build *today*.

**Evidence.**
- Yesterday landed three non-trivial commits: `49de377` (P0 fixes), `e6327f7` (−5.5k LOC
  deletion), `b89e610` (RNG made injectable). Zero launches since.
- The uncommitted WIP is interlocked: `oracle/wargame/engine/oldhammer.py` (modified, tracked)
  now does `from oracle.tomlio import load_toml` — but `oracle/tomlio.py` is **untracked**.
  A `git stash`, a clean checkout on another machine, or committing oldhammer.py without
  tomlio.py produces an ImportError in a live rules engine. This foot-gun is armed right now.
- `tests/test_wargame_engines.py` is also untracked — 627 lines, **43 passing tests** covering
  the engines. The single most valuable artifact created this week is not in version control.
- Precedent that the map lies: yesterday's decree declared `wargame_app.py` "no live entry
  point — delete it" (P1 item 5). In fact `Wargame.bat` launches exactly that module
  (`python -m oracle.gui.wargame_app`). Had the deletion followed the decree literally, the
  wargame would not start today. The council has already been wrong once about what is live.
- What I could verify without launching: 83 tests pass (0.31s), and all three GUI modules
  import cleanly. That is necessary, not sufficient — there are **zero GUI tests**, and DPG
  failures (missing tags, references to panels deleted in `e6327f7`) only appear at runtime.

**Accepted mitigation.** Before any UX work: (a) one commit bundling tomlio.py + oldhammer.py
+ test_wargame_engines.py; (b) a 15-minute manual smoke test — launch all three .bats, run one
full loop in each (RPG: wizard → opening → "?" question → /roll; Wargame: add a unit per side
→ Declare Attack → AI Turn → Next Phase; Birthright: load campaign → domain action → advance
turn). Write down what breaks. That list, not intuition, orders the UX work.

---

## Challenge 2 — Opportunity cost: where is the real bottleneck to *playing*?

**Claim.** The bottleneck to the owner actually playing is not visual polish; it is (a) the
unverified base, and (b) holes in the play loop that no theme fixes.

**Evidence.**
- 7 open Beads. oracle-cgg (engine tests, P1) turns out to be *half done and uncommitted* —
  so the cheapest high-value act this session is a `git add`, not a design debate.
- gamemaster-designer found the wargame **cannot end**: `check_victory()`, `end_turn()`,
  `get_battle_summary()` are never called by `wargame_app.py` (only `start_battle` at :2974).
  A font at 18px on a battle that can't conclude is lipstick on a stalemate.
- oracle-dgz (pull rules out of `oracle_app.py`) and oracle-cpn (combat pipeline extraction)
  touch the very files a UX pass would edit. Polish-first means editing lines that a scheduled
  refactor will move next week — double churn, double review, on a codebase with no GUI tests.

**Accepted mitigation.** Sequence: commit WIP → smoke test → the S-tier UX fixes that touch
*rendering call sites only* (auto-scroll, feedback lines, phase refresh) → then dgz/cpn →
then any UX work that restructures panels. And put "call check_victory/end_turn" on the list
ahead of any theming: it is the one item that changes whether a session of the wargame is a
game at all.

---

## Challenge 3 — Scope creep: which fixes stay small, which metastasize

**Claim.** Roughly a third of the plausible UX menu is genuinely small; the rest has rewrite
gravity, and `wargame_app.py` is the gravitational center.

**Evidence and sorting.** From the ux-designer's own list:
- **Genuinely small (S, additive, view-only):** auto-scroll (`set_y_scroll` after render —
  the only existing call in the repo is *commented out in a dead file*,
  `views/chat_panel.py:125`); refresh callback on Next Phase (`wargame_app.py:735-744`);
  `/help` + stop narrating unknown slash commands (`oracle_app.py:900-936`); visible
  save/blocked-turn feedback; delete the lying Ctrl+S help text; one bundled TTF; delete DEBUG
  prints. These are safe *because they add lines rather than move them*.
- **Metastasis risk:**
  - *Unify save locations / named saves* — touches persistence in three apps, orphans existing
    `./oracle_saves/quicksave.json` files, and is model-adjacent, not pixels. Smells small,
    isn't.
  - *Responsive text wrap* — fights DPG's layout model; the bold-text-in-horizontal-group hack
    (`oracle_app.py:1605-1611`) means "make text wrap properly" becomes "rewrite the message
    renderer." Rabbit hole.
  - *Wargame setup wizard / repeat-attack* — new modal flows inside a 3,303-line single file
    with 20 `except` blocks, ~8 of them silent `pass` (`wargame_app.py:345, 1618-1619, 2227,
    2488, 2501, 2510, 3086...`), zero test coverage at the GUI layer, and two scheduled
    refactors aimed at its dependencies. Additive callbacks are tolerable; anything that
    *restructures* its panels before oracle-cpn/dgz land is building on a file the council
    already wants to reshape.
  - *"Decide the wargame story"* (two competing wargame UIs: `oracle_app.py` wargame mode with
    8 systems at :45-54 vs `wargame_app.py` with 4 at :246) — the fold-one-into-the-other
    option is a multi-week rewrite wearing a UX costume. This is precisely the "big surprise
    rewrite" CLAUDE.md prohibits. The one-session version is: change two window titles and add
    one wizard line ("Narrative wargame — for the full tactical app use Wargame.bat").
  - *Any "unified launcher/shell" proposal* — a new fourth app. Reject on sight.
- One more trap: `views/chat_panel.py` + `views/session_panel.py` (962 lines) are dead but
  still exported by `views/__init__.py`. A UX fix applied there compiles, imports, and does
  nothing. Delete them *before* the polish pass, or someone will fix the wrong chat panel.

**Accepted mitigation.** The decree should explicitly split its list into "additive, S,
pre-refactor-safe" and "deferred until dgz/cpn," and cap this session's UX scope at the first
bucket. Any item requiring a new module or touching save formats needs its own plan per
CLAUDE.md rule 1.

---

## Challenge 4 — The audience of one

**Claim.** Standard-issue discoverability work is mostly worthless here — with one twist that
cuts the other way.

**Evidence.**
- Worthless or near-worthless for one user: tooltip passes (zero tooltips today, and that is
  fine), onboarding refinements to a wizard the owner has seen fifty times, cross-app visual
  consistency as an end in itself ("feels like one product" is a shipping concern; nobody
  else is receiving this product), keyboard-shortcut suites.
- **The twist:** this owner is a beginner who built via AI — he did not write most of this
  and demonstrably does not know what is in it. The brain has 20+ NL intents, Mythic meaning
  tables, a pacing engine, NPC memory (gamemaster-designer §2) — none surfaced, none known.
  Six wargame slash commands are documented nowhere (`oracle_app.py:909-927`). For a normal
  solo tool, discoverability is waste; here `/help` and a command list in the opening message
  are genuinely load-bearing, because the user's manual for his own app does not exist in his
  head. But the fix is *one command and one printed list*, not a discoverability program.
- Still pays at n=1: **core-loop friction** (no auto-scroll means every action needs a manual
  scroll to see its result — confirmed: zero live `set_y_scroll` calls in `oracle/gui/`),
  **readability** (no font loaded anywhere; `_setup_fonts` is `pass` at `oracle_app.py:182`),
  and above all **error visibility**. Roster save/load failures go to `print()`
  (`wargame_app.py:2203, 2293, 2320`); four Birthright buttons do nothing. A beginner cannot
  debug what he cannot see — for this specific user, silent failure is the difference between
  "I'll fix it" and "it's haunted, I'll stop playing."

**Accepted mitigation.** Filter every proposed item through: "does this remove friction or
reveal errors *for Caleb, mid-session*?" If it only serves a hypothetical new user, cut it.

---

## Challenge 5 — The DearPyGui ceiling

**Claim.** There is a real risk the owner's mental image of "better UI" is something DPG
cannot deliver, and nobody on the council will say so.

**Evidence.** DPG is an immediate-mode GUI: no rich text, no reflowing text (hence the
hardcoded wrap widths at 600px/500px/60 chars and the unwrappable bold-segment hack), no
native widgets, awkward DPI story, bitmap-default font. The reachable ceiling is "clean,
readable imgui tool" — think a good debug console or EVE-style utility, not Foundry VTT or
Obsidian. A TTF at 17px, one shared theme, and auto-scroll get ~80% of the achievable gain;
the remaining 20% costs 10x and the last 20% is unreachable without changing toolkits — which
would be the largest surprise rewrite conceivable and must not sneak in as "maybe we should
look at Qt/web."

**Accepted mitigation.** The decree names the ceiling out loud, defines success as "friction
removed in the three core loops," not "looks modern," and records a standing decision:
no toolkit migration will be entertained without a dedicated session and the owner asking
for it explicitly.

---

## Challenge 6 — Edge cases the optimists will miss

- **DPI / small screens.** No font, no `set_global_font_scale`, wargame viewport 1600×900
  with *no minimum size* — on a 1366×768 laptop or at 125–150% Windows scaling it clips or
  blurs. Modal positions hardcoded (`pos=[400,200]`) can land badly on odd viewport sizes.
  Any font fix must be tested at 100% and 150% scaling before it is called done.
- **Long sessions.** `self.messages` grows unboundedly and every message permanently adds DPG
  widgets; nothing is ever pruned. The chaos death-spiral (random event at chaos/18 per
  action → 50% at chaos 9) accelerates log growth exactly when sessions run long. Note the
  irony: the council's #1 fix, auto-scroll, makes long sessions *more* likely. Cheap guard: a
  message cap (drop oldest widgets past ~300) or at least a "New Session" that actually clears.
- **TOML errors mid-session.** The new `tomlio.load_toml` warns and returns None — to a
  console. Oldhammer then *silently falls back to hardcoded charts* (`oldhammer.py:70-75` in
  the WIP diff). The project pillar is "rules live in TOML"; a typo in a chart file now means
  the game quietly plays with different rules than the file says, and the owner sees no
  change and doesn't know why. Fallback needs to announce itself in the GUI, not stderr.
- **Windows launcher quirks.** All three .bats call bare `python` (PATH-dependent, no venv);
  only `Birthright.bat` checks for dearpygui — the other two crash to a `pause`. If anyone
  "cleans up" the .bats to use `pythonw` or a shortcut, the console vanishes and with it the
  only place `print()`-errors and TOML warnings currently appear — the console window is,
  today, the app's de-facto error log. Keep it until errors surface in-GUI. Also: saves are
  CWD-relative for Solo RPG (`./oracle_saves`), so launching any way other than the .bat
  scatters save files.

---

## Named Sacrifices (Law 2)

For the five recommendations the council is most likely to issue:

1. **Quick-wins bundle (auto-scroll, feedback lines, phase-refresh, /help, font).**
   Sacrifices: a session of work on a base verified only by import checks; every "one-liner"
   in `wargame_app.py` must be click-tested by hand because there is no GUI safety net; and
   it consumes the session that could have closed oracle-cgg for good. Cheapest bundle, but
   not free — the verification burden is the price.
2. **Shared theme / "one product" visuals.** Sacrifices: hours of pure aesthetics for an
   audience of one; touches the startup path of all three apps including the only one whose
   theme already works (Birthright); zero effect on any play loop. Defensible only after the
   S-tier friction fixes, never before.
3. **Unified saves + named save slots.** Sacrifices: orphans every existing quicksave;
   converts a "pixels" session into persistence-logic surgery across three apps; highest
   regression risk of anything wearing the "polish" label. Needs its own plan, not a line
   item.
4. **Wargame setup wizard + repeat-attack.** Sacrifices: new structure inside the 3,303-line
   monolith ahead of the scheduled cpn/dgz refactors — double churn guaranteed; wizard value
   is concentrated in the first ten seconds of a launch the owner does daily. Repeat-attack
   is the better half; the wizard can wait for the refactor.
5. **Consolidating the two wargame UIs.** Sacrifices: weeks. This is the prohibited surprise
   rewrite in its most tempting disguise. The affordable version is two window titles and one
   sentence in the wizard; anything beyond that trades the whole month's momentum for
   conceptual tidiness no second user exists to appreciate.

And the sacrifice of my own position, named: insisting on smoke-test-first costs the feel-good
momentum of shipping visible polish today, and risks the session ending with "we found three
new bugs" instead of "it looks better." That is the correct trade. A pretty app that hasn't
been started since its biggest surgery is a bet, not a product.

*— Devil's Advocate*
