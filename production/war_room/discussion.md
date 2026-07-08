# The Debate — UI/UX Audit (2026-07-07)
*Full independent analyses in `analysis/`. This records where the Council agrees and clashes.*

## Summoner's answers (bound into the record)
- All three modes matter; **solo-DM + wargaming companion is the main goal**; Birthright
  is "a video game RPG where the interactions are text" he wants playable solo.
- Audience: **me now, share later.**
- Wants all four: look & feel, less friction, feedback & clarity, one unified app.
- Play style: as much in-app as possible, hybrid with physical table stuff.

## Unanimous (4/4 architects)
1. **Auto-scroll is the single biggest friction.** Neither chat log scrolls on new
   output; the only `set_y_scroll` in the codebase is commented out in dead code
   (`views/chat_panel.py:125`). Every single GM reply requires a manual scroll.
2. **Dead and silent controls erode trust.** Birthright Save gives no feedback
   (`app.py:464`), Advance Turn silently refuses (`app.py:304`), "AI Makes Decision"
   is a stub, Aggression combo is inert, help advertises Ctrl+S/Ctrl+N/R shortcuts
   that don't exist (`app.py:500-505`).
3. **A wargame battle cannot end.** `end_turn`/`check_victory`/`narrate_victory` are
   never called; Next Phase never refreshes the Battle Status sidebar
   (`wargame_app.py:735` vs `:3262`). This is a *function* gap wearing a UX costume.
4. **Theme/font pass is cheap and worth it.** 13px default bitmap font everywhere;
   only Birthright is themed (`app.py:81-111`). One shared `style.py` (~80 lines)
   makes three apps feel like one product.

## Clashes and resolutions

**Polish vs. verify (Devil's Advocate vs. everyone).**
DA: zero launches since the P0 fix + 5.5k-line deletion + RNG refactor; yesterday's
decree even ordered `wargame_app.py` deleted as dead when Wargame.bat launches exactly
that file — the map has lied before. Also a live foot-gun: tracked `oldhammer.py` now
imports *untracked* `tomlio.py`, and the 627-line engine test file is uncommitted.
dpg-engineer: static boot check passes on all three apps.
**Resolution:** DA wins. Step zero is one commit (WIP files) + a 15-minute click-through
of all three .bats. Only then polish.

**One unified app (Summoner's wish vs. dpg-engineer's costing).**
dpg-engineer: a true in-process mode switcher is L — colliding global tags
("main_window", "dice_dialog") across three apps. A launcher shell that picks a mode
and spawns the app is S. DA: the true merge is the prohibited surprise rewrite.
**Resolution:** Two-step. Now: shared theme/fonts + a single mode-picker launcher +
consistent window titles → *feels* unified. Later, if sharing becomes real: actual merge,
planned by oracle-architect as its own epic.

**Onboarding vs. audience-of-one (UX designer vs. DA).**
DA: tooltips and first-run wizards are waste for the author of the tool. But `/help` is
load-bearing *because* this owner builds via AI and genuinely doesn't know his own
feature set — six wargame slash commands are currently undiscoverable, and unknown
commands get narrated by the GM as player speech (`oracle_app.py:935`).
**Resolution:** Skip tooltips/onboarding for now. Ship `/help`, route unknown commands
to it, and keep error visibility ahead of prettiness (roster errors currently go to
`print()`; the .bat console is the app's only error log — do not "clean it up" away
until a status bar exists).

**Fiction vs. bookkeeping (gamemaster-designer's addition).**
The Mythic loop is amputated: chaos only rises (`fate.chaos_down` never wired), there is
no End Scene ritual, and random-event chance scales to ~50% per action at chaos 9 —
event spam buries the fiction. Any "?" hits the yes/no oracle, so "What do I see?"
answers "NO", while the brain's meaning tables (`gm/meaning.py`) sit unexposed.
No one contested this; it enters the decree as the play-depth phase.

**Salvage before deletion (recurring law).**
Orphaned `views/chat_panel.py` + `session_panel.py` duplicate the live chat UI and
already contain the thread/NPC buttons and the auto-scroll line we want. Salvage the
patterns into the live apps, then delete the dead files so polish never lands in dead code.
