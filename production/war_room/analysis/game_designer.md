# Gamemaster-Designer Analysis — UI/UX Audit (Play Experience Lens)
*War Room session 2026-07-07. Architect: gamemaster-designer.*

Question I answered: does the interface serve the actual experience of playing a solo RPG
session, fighting a wargame battle, or running a domain turn? Not code quality — the fiction
and the game flow.

Verdict in one line: **the chat-centered instinct is right in all three apps, but the Mythic
loop is broken at both ends (no scene ritual, chaos only ratchets up), the wargame turn
doesn't close (no victory, stale sidebar), and the single biggest friction is mundane — the
log never scrolls to the new GM message.**

---

## 1. The Solo RPG Loop (oracle_app.py)

The Mythic loop is: scene → ask oracle → interpret → log → threads/NPCs evolve → **scene ends,
chaos shifts** → next scene. The app implements the middle and amputates both ends.

**What's right:**
- Chat IS the center and should be (`oracle_app.py:489-527`). One input box, "?" auto-oracles,
  `/roll` for dice, GM answers in character. That is the correct shape for solo play.
- The sidebar shows scene / chaos / quest / NPCs / threads at a glance
  (`oracle_app.py:538-577`) — the right at-the-table info.
- The opening generation (`_generate_opening`, `oracle_app.py:657-806`) is genuinely good
  play: location, sensory details, NPCs with disposition hints, a quest hook with stakes, and
  it ends with "**What do you do?**" — a GM's question, not a status dump.

**What breaks the loop:**

1. **No end-of-scene ritual — chaos never goes down.** `fate.py:75` has `chaos_down()`; the
   brain even understands the text command "decrease chaos" (`brain.py:570-572`). But no
   button, no prompt, nothing in the UI ever lowers chaos except manually dragging the slider.
   Meanwhile `chaos_up()` fires on every random event and every plot twist
   (`oracle_app.py:1050-1052`, `2051-2053`). Mythic's core dial — "were you in control this
   scene?" — does not exist. Result: chaos ratchets toward 9 over a session.

2. **The chaos death-spiral is mechanical, not just thematic.** Every plain action rolls a
   random event at `chaos/18` probability (`oracle_app.py:1086-1088`). At chaos 9 that's 50%:
   half of all player actions get interrupted by an ENCOUNTER/COMPLICATION block. Combined
   with (1), a long session degenerates into event spam that buries the fiction the player is
   trying to have. The bookkeeping doesn't interrupt the fiction — the *event engine* does.

3. **Every "?" is treated as yes/no** (`oracle_app.py:930-933`). "What do I see?" or "Who is
   she?" gets "Rolling... 43 ... **NO**" — a nonsense answer that snaps immersion instantly.
   The brain already has the fix: `process_input` gates oracle on yes/no starter words
   ("is/are/does/will..." — `brain.py:547-554`), but `_process_input` in the app bypasses it.

4. **Threads and NPCs are read-only scenery.** Sidebar shows top 4 threads and 5 NPCs
   (`oracle_app.py:1664-1697`) but you cannot add, advance, or resolve a thread, and you
   cannot click an NPC to talk to them or see their history. The brain supports all of it:
   `add_thread/advance_thread/resolve_thread` (`brain.py:461-494`), `npc_speaks`,
   `adjust_npc_disposition`, `log_npc_promise/lie/conversation`, `get_npc_relationship`
   (`brain.py:424-532`). Ironically, an **orphaned** view (`views/session_panel.py:92-121`,
   exported in `views/__init__.py` but used by no app) already has "Change Scene", "Add
   Thread", and "Add NPC" buttons.

## 2. Capability Gaps — What the Brain Can Do That the UI Hides

| Brain/model capability | Where it lives | UI status |
|---|---|---|
| 20+ NL intents: search, travel, pray, rest, assess, recall, sense, recall_lore, query_state | `orchestrator.py:110-149` | Reachable via `process_smart`, but **zero discoverability** — the only hint is the input placeholder (`oracle_app.py:519`). No /help, no verb list. |
| Meaning tables (Mythic meaning words + elaboration) | `gm/meaning.py:109,214,333` (`roll_meaning`, `format_for_display`) | Never reachable from any GUI. This is *the* Mythic tool for open questions. |
| Pacing engine: tension, scene phase, suggest_next_beat, scene bangs | `gm/pacing.py:237,303,401` | Never surfaced. `get_pacing_status` (`brain.py:496`) uncalled by UI. |
| Session journal: scenes, notes, `render_journal()` readable export | `journal.py:448` | Unused by any GUI (only a coincidental string match at `oracle_app.py:1529`). |
| NPC memory: promises, lies, conversation logs, relationship summary | `brain.py:502-532` | Invisible. |
| Wargame: `end_turn()`, `check_victory()`, `get_battle_summary()`, `narrate_victory/defeat` | `coordinator.py:141,320,535`; `commander.py:723,738` | **Never called** by `wargame_app.py` (grep: only `start_battle` at :2974). A battle literally cannot end. |
| Commander's opening address — `start_battle()` returns narration | `coordinator.py:294` | Return value discarded (`wargame_app.py:2974`). |
| `player_declares_charge` | `coordinator.py:402` | No UI path; attack dialog offers only Shooting/Melee (`wargame_app.py:499-505`). |

Dead controls that pretend capability (worse than missing):
- "AI Makes Decision" button prints "*Commander X assesses the battlefield...*" and decides
  nothing (`wargame_app.py:2957-2966`).
- Aggression combo callback is `pass` — "stored for future use" (`wargame_app.py:2931-2934`).
- Birthright Help lists Ctrl+S / Ctrl+N / R shortcuts (`app.py:500-505`) that are never
  registered anywhere. A solo player *will* try them.

## 3. Immersion — GM Voice vs Debug Output

- **The wargame narrator is the best writing in the project** — dramatic openers, commander
  voice lines quoted in-character (`narrator.py:136-191`) — and the battle log does show it
  with a distinct narrative color (`wargame_app.py:419-427`). Good.
- But it's sandwiched between debug-shaped lines: `"{unit}: SHOOT"` / `"  Target: X"`
  (`wargame_app.py:710-719`) and stat blocks `"Hits: 2, Wounds: 1, Saves Failed: 1"`. The
  dice breakdown is exactly what a solo wargamer wants — keep it — but the AI's *intent*
  should read as an order ("Ironclaw wheels his Chosen toward your flank") before the math.
- ASCII banners (`"=" * 45`, `oracle_app.py:848-854`, `1277-1279`) read as terminal output,
  not a war room.
- The markdown-lite renderer breaks its own formatting: any line containing `**bold**` is
  rebuilt as a horizontal group of separate text items (`oracle_app.py:1603-1611`), so long
  bold-bearing lines **cannot wrap** and run off the panel; all wraps are hardcoded to 600px
  regardless of window width (`oracle_app.py:1611-1616`). The GM's most emphasized sentences
  are the ones most likely to clip.
- Oracle answers land well (**YES, BUT...** + interpretation, `oracle_app.py:1027-1040`).
  The roll metadata line before the answer is the right order — mechanics whispered, answer
  loud.

## 4. Table Needs During Play

- **Chaos**: visible in header and sidebar (good, `oracle_app.py:505-506`). Missing in the
  Birthright event view unless you look at the dashboard (acceptable).
- **Dice**: reachable but modal. Both dice dialogs (`oracle_app.py:1873`, `wargame_app.py:852`)
  interrupt flow; quick-roll buttons exist only *inside* the modal. A solo player rolls
  constantly — quick-roll buttons belong on the main surface. No reroll-last button anywhere.
- **Threads/NPCs**: visible but capped (4/5) and inert (§1.4).
- **Rules reference**: PhaseGuidePanel is a genuinely good play aid — steps, key rules,
  common mistakes from TOML (`wargame_app.py:2388-2728`) — but it's a tab *behind* AI
  Controls (`wargame_app.py:2843-2851`) and only syncs to the actual battle phase when
  something calls `refresh()`, which phase advance does not (see §6).
- **Chat log scrolling — the #1 mid-session friction**: neither app ever calls
  `set_y_scroll` (grep of both files: zero matches). New GM messages append below the fold;
  after every single exchange the player must manually scroll down. This punishes the core
  loop hundreds of times per session.

## 5. Session Continuity

- **Resuming is backwards.** Launch → wizard forces you to configure and BEGIN a *new*
  adventure → app generates a fresh opening (new quest, location, NPCs) → only then does a
  Load button exist in the sidebar (`oracle_app.py:583-585`) → loading throws away what was
  just generated. There is no "Continue last session" on the wizard
  (`oracle_app.py:188-325`), even though `oracle_saves/quicksave.json` is trivially checkable.
- **One save slot**, silently overwritten (`oracle_app.py:2092-2096`). One misplaced click on
  Save after starting a throwaway session destroys the real campaign. No name, no timestamp,
  no confirmation.
- **Reviewing last session**: History dialog truncates every entry to 100 chars
  (`oracle_app.py:2171-2174`) — useless for "where were we?" The unused
  `journal.render_journal()` (`journal.py:448`) already produces the readable recap this
  needs.
- **Birthright does this best**: autosave on exit (`app.py:532-535`), auto-load of autosave on
  startup (`app.py:207-216`), campaign select dialog otherwise. Copy that pattern.
- Wargame save/load exists with named files (`wargame_app.py:2982+`) — adequate.

## 6. Wargame Turn Flow

A battle round should be: phase banner → my actions → AI phase → morale → turn ends → status
updates → repeat until victory. What actually happens:

1. **"Next Phase" updates only the chat** (`wargame_app.py:735-744`). `BattleStatePanel`
   (turn/phase, `:2370-2381`) and `PhaseGuidePanel.refresh()` (`:2709`) are refreshed only by
   `_refresh_all`, which runs on new battle / load / system change (`:2975,3215,3262`). So
   the always-visible "Turn: 1, Phase: Movement" sidebar is *wrong for the entire battle*,
   and the learning aid never follows the game. The player must track turn/phase in their
   head — the one job this panel had.
2. **The battle never ends.** No UI path calls `end_turn()` or `check_victory()`
   (`coordinator.py:320,141`); `narrate_victory/defeat` (`commander.py:723,738`) are
   unreachable. The commander can taunt but never concede or gloat at the end. There is no
   climax — the session just stops.
3. **No commander presence at the start** — `start_battle()`'s returned intro is dropped
   (`wargame_app.py:2974`), so the opponent has no face until the first shot.
4. What *does* flow well: Declare Attack → dice breakdown → narrative → voice line
   (`wargame_app.py:604-665`) is a satisfying resolution beat. AI Turn shows threat
   assessment and per-unit activations. The bones of a good round are here; the round just
   has no beginning (intro), no clock (stale sidebar), and no end (victory).
5. Note: `BattleChatPanel` defines `self._input_tag` (`wargame_app.py:320`) but never builds
   an input box — the "chat" is buttons only. Fine for now, but it means the commander
   dialogue capabilities (`react_to_player_action`, `opponent.py:644`) have no channel.

Birthright turn flow is the healthiest of the three: dashboard shows turn/season/actions
remaining with color-coded urgency (`dashboard.py:200-208`), events arrive as choice buttons
with severity dots and consequence previews (`event_log.py:135-201`). Two frictions:
"Advance Turn" **silently does nothing** when events are pending (`app.py:304-309`) — it must
say "Resolve pending events first" — and standalone oracle results appear in a modal popup
(`event_log.py:326-370`) then vanish, never entering the event history.

## 7. Missing Play Aids That Would Matter Most

1. End Scene ritual (see R2).
2. Meaning-table button for open questions (`gm/meaning.py` is finished and idle).
3. Auto-scroll (R1).
4. On-surface quick dice + reroll-last.
5. Command/verb cheat sheet (the six wargame slash-commands at `oracle_app.py:911-927` are
   documented nowhere a player will look).
6. Victory/defeat handling in wargame (R4).
7. Journal export ("what happened last session" in prose).

---

## Prioritized Recommendations

Ordered by play-experience impact per unit of effort. All respect the golden rule (these are
view-layer changes wiring *existing* model capabilities) and "smallest change that works."

| # | What | Why | Effort |
|---|------|-----|--------|
| R1 | **Auto-scroll chat/battle logs to bottom on new message** (both `oracle_app._render_message` and `BattleChatPanel._render_message`; `dpg.set_y_scroll(log, -1.0)` after append) | Removes the single most frequent friction in every session of all modes | **S** |
| R2 | **"End Scene" button in the solo sidebar**: ask "Were you in control?" → `chaos_up`/`chaos_down`, show open threads for optional resolve, log a scene-break line in the chat | Restores the missing half of the Mythic loop; fixes the chaos ratchet; gives sessions rhythm | **M** |
| R3 | **Gate auto-oracle on yes/no phrasing** (reuse `brain.py:549-551` starter list in `_process_input`); route non-yes/no "?" to `process_smart`, and offer a "Meaning" button that calls `roll_meaning()` + `format_for_display()` | Kills the most immersion-breaking failure (nonsense YES/NO to open questions) and finally surfaces the meaning tables | **S** |
| R4 | **Close the wargame round**: `_advance_phase` also refreshes `_state_panel` + `_phase_guide`; on turn wrap call `coordinator.end_turn()` and `check_victory()`; on outcome, print `narrate_victory/defeat`; print `start_battle()`'s intro on New Battle | Turn/phase clock becomes trustworthy, battles get an opening face and an actual ending | **S** |
| R5 | **"Continue last session" on the startup wizard** (if `oracle_saves/quicksave.json` exists, offer it *before* generating a new opening); add timestamp to save confirmation | Fixes the backwards resume flow that currently regenerates then discards content | **S** |
| R6 | **Make threads/NPCs tappable**: port Add/Resolve Thread and Add NPC from the orphaned `views/session_panel.py`; click NPC → small menu (Talk / Relationship) calling `npc_speaks` / `get_npc_relationship` | Converts the sidebar from scenery into the Mythic threads/characters lists; brain support already 100% built | **M** |
| R7 | **Remove or wire dead controls**: "AI Makes Decision" stub, inert Aggression combo, phantom Birthright shortcuts, silent Advance Turn block (show reason), silent save (show confirmation) | Dead controls teach the player not to trust the interface | **S** |
| R8 | **Fix bold-line wrapping** in `_render_text` (don't put wrapped text inside horizontal groups; compute wrap from panel width or drop inline-bold for line-level emphasis color) | The GM's emphasized lines are currently the ones that clip off-screen | **S–M** |
| R9 | **Journal export + fuller history**: "Export Journal" button calling `journal.render_journal()` (or a formatter over `memory`) to a timestamped .md; unclamp History dialog | Session-to-session continuity in prose, not 100-char stubs | **M** |
| R10 | **Tame the random-event spiral**: cap `event_chance` (e.g. max 25%) or roll events only on oracle asks (Mythic-correct) rather than every action | Keeps late-session fiction playable even at high chaos; numbers should live in TOML per golden rule | **S** |

Deliberately deferred (named tradeoffs): free-text commander chat in wargame (L — flavor, not
flow); charge declaration UI (M — rules surface, needs gamemaster-designer spec first); pacing
engine surfacing (M — brain-side value unproven in play yet); Birthright oracle results into
event history (S but Birthright is the least-broken app).

**What is sacrificed**: R2 and R6 add sidebar chrome to a deliberately minimal UI — the cost
is a busier panel; keep them to one button and small popups. R10 changes felt difficulty for
anyone used to the current event rate. R3 means some questions no longer auto-roll — players
must end yes/no questions with yes/no phrasing, which is Mythic-correct but a habit change.
