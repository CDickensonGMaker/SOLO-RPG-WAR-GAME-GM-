# War Room Decree — UI/UX Overhaul
*Session 2026-07-07. Query: "What do we have, and how do we make the UI/UX better?"*
*Council: ux-designer, gamemaster-designer, dpg-engineer, devils-advocate. Debate in `discussion.md`, analyses in `analysis/`.*

## The Verdict

**What you have:** three functional apps with a healthy logic core and a genuinely good
skeleton (correct resizable layout, real drawlist map/NPC graph, a solid Birthright
dashboard pattern) — wearing debug-tool clothes. The suite's problems are not deep:
no auto-scroll, no feedback on actions, dead buttons, default 13px font, three apps
that don't know they're one product, and a wargame battle that literally cannot end.
Verified this morning: all imports clean, 83 tests pass. Nobody has clicked a button
since the big fix — that is step zero.

**The shape of the fix:** ~80% of the felt improvement is small, additive, view-layer
work. No rewrite is needed or permitted.

## The Decree

### Phase 0 — Protect and verify (before any pixel moves)
1. **Commit the stranded WIP** — `tomlio.py` + `tests/test_wargame_engines.py` (627
   lines, green) + modified `oldhammer.py`. A tracked file already imports an untracked
   one; a stash or partial commit breaks a live rules engine. *(done this session)*
2. **15-minute smoke test**: launch all three .bats, perform one core action in each
   (ask the oracle a question; advance a wargame phase; run one domain action).
   The Summoner's hands, this time — the point is seeing it, not just green tests.

### Phase 1 — Trust and flow (one sitting, all S, view-layer only)
3. **Auto-scroll both chat logs** + refocus the input after Send. (2–4 lines per app;
   the needed `set_y_scroll` call already exists, commented out, in dead code.)
4. **Close the battle loop**: wire `end_turn` / `check_victory` / `narrate_victory`,
   and make Next Phase refresh the Battle Status + Phase Guide panels. A battle must
   be able to END with a narrated result.
5. **Feedback everywhere, no dead controls**: Birthright Save confirms, Advance Turn
   says *why* it's blocked, stub buttons ("AI Makes Decision", save-Delete, history
   filters, inert Aggression combo) are removed or wired, phantom shortcuts deleted
   from help text. Every click produces a visible consequence.
6. **`/help`** listing all commands in both chat apps; unknown `/commands` route to
   help instead of being narrated by the GM as player speech.
7. **Oracle gating**: only yes/no-shaped questions hit the oracle (the brain's gate at
   `brain.py:549` already knows how); "What do I see?" goes to meaning/scene tools.
   Add a Meaning Table button — the tables are finished and unexposed.

### Phase 2 — One product (S/M)
8. **Shared `oracle/gui/style.py`**: one theme (grow Birthright's) + one bundled
   16–18px TTF font, applied to all three apps. Consistent window titles.
9. **Single launcher**: one Oracle.bat → tiny mode-picker window that spawns the chosen
   app as a subprocess. The true in-process merge is **deferred** (tag collisions make
   it large) until "share later" becomes "share now".
10. **Dialog hygiene**: `centered_pos()` helper for the ~30 hardcoded `pos=[400,200]`
    modals; fix the wargear/Chaos dialog (stray radio dots, checkbox desync, broken
    Clear All, DEBUG prints — fold into existing bead oracle-2rz).
11. **Prune chat logs** past ~500 entries (auto-scroll makes long sessions likelier;
    both logs currently grow forever).

### Phase 3 — Play depth (M; this is where it becomes a *game*, per the Summoner's goal)
12. **Complete the Mythic loop**: End Scene button (chaos up/down per scene outcome —
    `fate.chaos_down` exists, never wired), cap the random-event spiral at high chaos.
13. **Tappable threads and NPCs**: click a thread to advance/resolve, click an NPC to
    talk — salvage the buttons from the orphaned SessionPanel, then delete the dead
    panel files.
14. **Session continuity**: Load/Continue on the startup wizard (currently forces a new
    adventure first), named saves, journal export via the unused `render_journal()`.
15. **Unify save locations** under `~/.oracle/` (currently split across CWD-relative
    `./oracle_saves`, `~/.oracle/`, and `sessions/`).

## Named Sacrifices (Law 2)
- **Deferring the true unified app**: three processes remain under one launcher skin.
  Accepted to avoid a prohibited surprise rewrite of colliding tag namespaces.
- **Skipping tooltips/onboarding**: future sharers get a rougher first run. Revisit
  when sharing is real.
- **Keeping the .bat console visible**: it is currently the only error log. Ugly stays
  until an in-app status bar exists.
- **Deleting the orphaned panels after salvage**: any half-built features in them die;
  git history remembers.
- **DPG ceiling accepted**: no rich inline text, no animations, no runtime font resize.
  Target is "clean imgui game tool", not Foundry VTT.

## The Record
Beads epic **UI/UX Overhaul** created; phases entered as linked issues (see `bd ready`).
Phase 0 item 1 committed this session. The Summoner decides where to begin;
recommended: smoke test tonight, then Phase 1 in a single sitting.
