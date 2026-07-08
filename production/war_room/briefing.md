# War Room Briefing — UI/UX Audit
*Session: 2026-07-07. Summoner: Caleb.*

## The Query
"What do we have and what could we do to make it better? I'm thinking more of the
UI/UX experience overall. I haven't tested it since the large fix yesterday, but
I'm sure it can still be improved."

## Constraints (Pillars)
- Golden rule: logic in models, pixels in views, rules in TOML.
- Owner is a beginner programmer building via AI — smallest change that works,
  plain-English explanations, no surprise rewrites.
- DearPyGui is the UI toolkit. Three modes: Solo RPG, Wargame, Birthright.
- Prior session (2026-07-06, archived) fixed P0 bugs and deleted ~9k dead LOC.
  83 tests pass; imports clean as of this morning.

## Known state going in
- Live GUIs: `oracle/gui/oracle_app.py` (2,193 ln), `oracle/gui/wargame_app.py`
  (3,303 ln), `oracle/gui/app.py` (545 ln, Birthright) + `views/`, `dialogs/`.
- Launchers: Oracle.bat, Wargame.bat, Birthright.bat (three separate entry points).
- Open Beads: oracle-cgg (engine tests), oracle-2rz (GUI hygiene), oracle-a0h,
  oracle-ewy, oracle-b5f, oracle-dgz.
- Uncommitted WIP: tomlio.py, tests/test_wargame_engines.py, oldhammer.py edits.

## Architects summoned
ux-designer, gamemaster-designer (play-experience lens), dpg-engineer,
devils-advocate. Arbiter synthesizes.
