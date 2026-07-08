# UX Designer — Independent Analysis
*War Room session 2026-07-07. Lens: user experience only. All paths relative to `C:\Users\caleb\oracle\`.*

---

## 1. First-run experience

### Solo RPG (`Oracle.bat` → `oracle/gui/oracle_app.py`)
**Best first-run of the three.** A centered 500x520 startup wizard (`oracle_app.py:188-325`) greets the user in character ("Greetings, traveler..."), walks through Game Type / Setting / Mood / GM Personality / Chaos, and ends on a big BEGIN ADVENTURE button. Wargame-specific options reveal contextually (`:327-334`). The app then generates a rich opening scene with quest hook and ends with "**What do you do?**" (`:657-806`) — the user always knows the next move. Viewport 1200x800 with sane min size (`:163-169`).

Weaknesses: the five GM personalities are bare names with no one-line description ("Dark Narrator" vs "Mystical Seer" — a new user is guessing), and Chaos gets only "1 = Ordered / 9 = Chaotic" (`:281-284`) with no hint of what it *does* (more random events).

### Wargame (`Wargame.bat` → `oracle/gui/wargame_app.py`)
**No wizard.** The user lands in a 1600x900 three-panel layout (`:2771`) with empty army panels reading "No units" (`:992`) and roughly 20 visible controls. Two system chat lines provide the only orientation: "Welcome... Add units to both armies, then declare attacks or let the AI take turns" (`:3279-3286`). The game system silently defaults to Oldhammer 2E (`:2740-2743`); a user who wants Trench Crusade has to discover the Game System menu on their own. No min window size — 1600 px wide on a small laptop clips.

### Birthright (`Birthright.bat` → `oracle/gui/launcher.py` → `oracle/gui/app.py`)
Decent: tries autosave first, otherwise opens a Campaign Selection dialog with a preview pane (tagline, difficulty, description, recommended bloodlines — `campaign_select.py:193-224`). That is a good pattern. But the dialog appears via a frame callback 30 frames in (`app.py:76`), so the user first sees the empty dashboard ("No Campaign Active") flash before the modal arrives. `Birthright.bat` is also the only launcher that checks/installs dearpygui; `Oracle.bat` and `Wargame.bat` just crash to a `pause` prompt if it's missing.

---

## 2. Information hierarchy & layout

### Solo RPG
Clean two-zone layout: chat (fills) + 270px read-only sidebar (`:487-494`). Sidebar auto-updates Scene/Quest/NPCs/Threads — genuinely useful ambient state. Chaos appears in both header and sidebar and stays synced (`:1699-1703`). Input row with Send / Oracle / Dice / Menu is right where it should be. The vague "Menu" button (`:529`) hides the four content generators (New Quest, Encounter, Scene Change, Plot Twist — `:1939-1942`), which are arguably the app's best features.

### Wargame
Three fixed columns: forces (300px), battle log (flexible), AI/Phase Guide tabs (340px) (`:2810-2851`). Hierarchy is reasonable — log is central, armies at left, learning aids at right. The Phase Guide panel (`:2388-2728`) with steps/tips/common-mistakes loaded from TOML is a standout UX asset for a beginner-facing app. But the log gets only `height=-100` (`:340-344`) while six action buttons sit below it; on a short window the log shrinks first.

### Birthright
Three panels sized as *fixed pixels computed once* from config (dashboard `dashboard.py:48`, event log `event_log.py:48`, map `map_view.py:107-109`), inside a `no_resize` primary window (`app.py:116-122`). Resize the viewport and the layout does not reflow — dead space or clipping. Dashboard hierarchy itself is excellent: Regent / Turn / Domain / Oracle / Quick Actions / Campaign, with color-coded resources and an actions-remaining counter that goes yellow at 1, red at 0 (`dashboard.py:202-208`).

---

## 3. Core-loop friction (click counts)

| Action | Path | Steps | Verdict |
|---|---|---|---|
| Ask oracle (RPG) | type question ending in `?`, Enter | 1 | Excellent — best interaction in the suite (`oracle_app.py:930-933`) |
| Ask oracle via dialog | Oracle btn → type → pick likelihood → Ask | 4 | Fine; dialog adds likelihood control the typed path lacks |
| Roll dice (RPG) | type `/roll 2d6+3`, Enter — or Dice btn → quick-roll chip | 1-2 | Good; quick-roll buttons `:1894-1902` are smart |
| Log a scene change (RPG) | Menu → Change Scene | 2 | Fine, but buried behind unlabeled "Menu" |
| Declare attack (Wargame) | Declare Attack → attacker combo → weapon combo → target combo → type radio → 0-3 modifier checkboxes → Attack! | 6-9 | **Clunky.** Modal re-opens blank every attack; a 10-attack shooting phase = ~70 clicks. No "repeat last attack." |
| Add a unit (Wargame) | Add Unit → faction → unit → (optionally edit 9 stat ints + 3 sliders + wargear dialog + chaos dialog) → Add Unit | 4 min, 15+ typical | The TOML auto-fill (`:1283-1356`) saves it, but the form is a wall; sliders for exact integers (`:1151-1166`) are the wrong control |
| Take AI turn (Wargame) | AI Turn button | 1 | Good |
| Advance phase (Wargame) | Next Phase button | 1 | Good click-wise, but status panel doesn't update (see §4) |
| Run domain action (Birthright) | Quick Action btn → dialog → category tab → select action → pick target → Execute | 5-6 | Reasonable; details pane with cost/DC/affordability check (`domain_action.py:299-314`) is good UX |
| Resolve event (Birthright) | click a numbered choice button | 1 | Excellent — choices with consequence previews (`event_log.py:166-191`) |

**The single worst cross-cutting friction: no auto-scroll.** Neither chat log ever scrolls to the newest message. `oracle_app.py:1560-1586` and `wargame_app.py:390-433` append to the log but never call `set_y_scroll`; a grep of `oracle/gui` finds the only `set_y_scroll` in the codebase *commented out* in dead code (`views/chat_panel.py:125`). After the log fills one screen, every single action requires a manual scroll to see its result. This poisons the core loop of both chat apps.

---

## 4. Feedback & state visibility

**Solo RPG — mostly good.** Every input produces a visible GM/system message; invalid dice notation gets a readable system line (`:973-974`); chaos changes are announced (`:1052`); save/load confirm in-chat (`:2096, :2144`). Gaps: saving in wargame mode silently drops `wargame_state` — turn, phase, casualties are not in the save dict (`:2070-2090`), so a loaded battle has quietly lost its scoreboard.

**Wargame — inconsistent.**
- *Stale state:* Next Phase posts a chat line but never refreshes the Battle Status panel or Phase Guide — `BattleChatPanel._advance_phase` (`:735-744`) has no reference to them. The sidebar keeps saying "Turn 1 / Movement" while the game moves on. This is the app's worst state-visibility bug.
- *Silent success:* Save Roster closes the dialog with no confirmation — the code literally says `# Could add a success message here` (`:2201`).
- *Invisible errors:* roster save/load/delete failures go to `print()` (`:2203, :2293, :2320`) — invisible in a GUI session.
- *Leftover debug:* `DEBUG:` prints on every detachment load (`:2010-2070`) spam the console.
- *Good:* dice breakdowns with successes bracketed `[5]` (`:617-641`), battle save confirms in-chat (`:3056-3059`), load dialog shows "Selected: name" (`:3126, :3150`) — though the roster-load dialog lacks that same feedback.

**Birthright — the weakest feedback of the three, in an app whose visuals are the strongest.**
- Campaign > Save does nothing visible: `# Show brief notification` / `pass` (`app.py:464-468`).
- Advance Turn with unresolved events silently returns (`app.py:304-309`) — the #1 button on the dashboard sometimes just does nothing, with no explanation.
- Ask Oracle with no campaign: dialog closes, nothing happens (`app.py:406-415`).
- Domain Action's "Ask Oracle" button is a stub — `pass` (`domain_action.py:404-416`).
- Delete save button is a stub (`campaign_select.py:330-337`).
- Event-history filter buttons (All/Story/Random/Choices) do nothing (`event_log.py:303-306`).
Four visible, clickable controls that do nothing teach the user to distrust every button.

---

## 5. Discoverability

- **Solo RPG:** one input hint carries the entire feature set: "Questions ending in ? auto-trigger Oracle, /roll for dice" (`:519`). The six wargame-mode slash commands (`/situation /target /morale /event /phase /casualties`, `:909-927`) are documented **nowhere in the UI**. There is no `/help`: an unrecognized command like `/help` falls through to `_handle_action` (`:935-936`) and gets *narrated by the GM as if the player said it* — actively misleading.
- **Wargame:** buttons make actions visible (good), and the Phase Guide is real teaching UX. But nothing points a new user at it, and menus (Game System, Commander) are unadvertised.
- **Birthright:** the only app with a Help menu — but its Quick Reference **advertises keyboard shortcuts that do not exist** (Ctrl+S, Ctrl+N, R — `app.py:500-505`; no `handler_registry` or key handler exists anywhere in `oracle/gui`). Documentation that lies is worse than none.
- **Zero tooltips in the entire suite** (grep: no `add_tooltip` anywhere). Zero keyboard shortcuts. DearPyGui makes both cheap.

---

## 6. Consistency across the three apps

They feel like three unrelated tools by three different authors:

| Aspect | Solo RPG | Wargame | Birthright |
|---|---|---|---|
| Theme | DPG default dark | DPG default | Custom warm/bronze theme (`app.py:81-111`) |
| Menu bar | none (Menu *button*) | yes | yes |
| First run | wizard | cold drop-in | campaign dialog |
| Window | 1200x800, min-size | 1600x900, no min | 1600x900, no_resize layout |
| Saves | `./oracle_saves/quicksave.json` — relative to CWD (`oracle_app.py:2066,2092`) | `~/.oracle/rosters`, `~/.oracle/battles` (`wargame_app.py:2188,3028`) | `sessions/birthright_campaigns` (`config.py:14-15`) |
| Oracle likelihoods | "50/50" (`:1808`) | n/a | "Even" (`app.py:386`) |

Worse, there are **two competing wargame UIs**: the Solo RPG wizard's "Wargame" mode (8 game systems listed, `oracle_app.py:45-54`, chat + slash commands) and the dedicated `wargame_app.py` (4 systems, `:246-267`, button-driven). A user cannot tell which one is "the wargame." Naming compounds it: `launcher.py` docstring claims "unified Oracle GUI" but launches BirthrightApp, while `oracle_launcher.py` launches OracleApp.

Three .bat launchers is acceptable for a single-user desktop tool — the real problem isn't three doors, it's that the three rooms don't match, plus only one door (Birthright.bat) checks dependencies.

Dead code that hurts UX indirectly: `views/chat_panel.py` and `views/session_panel.py` (962 lines) are exported by `views/__init__.py:15-16` but used by nothing — exactly where a maintainer would "fix the chat panel" and see no change.

---

## 7. Visual design

- **Fonts/DPI:** No app loads a font (`oracle_app.py:179-182` is a `pass`). Everything renders in DPG's default ~13px bitmap font, which is small and fuzzy on a modern high-DPI Windows display, in windows 1200-1600px wide. This caps the perceived quality of the whole suite.
- **Theme:** Only Birthright is themed; the other two ship the stock ImGui blue-gray. Birthright's palette (warm dark bg, bronze accents, gold resources) already exists and matches all three fantasy/grimdark use cases — it just isn't shared.
- **Color language is actually good and mostly coherent** where it exists: GM tan / player blue / system gray in both chat apps (`oracle_app.py:57-68`, `wargame_app.py:393-401`), green/yellow/red status ramps for casualties, unit status, chaos, actions remaining. This is a solid foundation.
- **Hardcoded wrap widths:** chat text wraps at 600px (`oracle_app.py:1611-1616`), battle log at 500px (`wargame_app.py:427-431`), Birthright wraps manually at 60 *characters* in Python (`event_log.py:270-290`). Maximize any window and text hugs the left third. Bold rendering worsens it: `**bold**` segments are laid out in a `horizontal group` of separate texts (`oracle_app.py:1605-1611`), which cannot wrap at all — long bold lines overflow the panel.
- **Modal positions hardcoded** (`pos=[400,200]` etc. — `oracle_app.py:1793, 1884`; `wargame_app.py:467, 1114`) rather than centered on the current viewport.
- **Cosmetic bug:** the Chaos "Marks" tab renders a stray empty radio button per mark — placeholder `add_radio_button(items=[""])` left in (`wargame_app.py:1695-1698`).

---

## 8. Prioritized improvements

Ordered by impact-per-effort. S = under an hour, M = an afternoon, L = multi-day. All are view-layer only (golden rule safe).

1. **Auto-scroll logs to bottom on new message** — S. One line after each render: `dpg.set_y_scroll(log_tag, -1.0)`. Fixes the single most repeated friction in both chat apps.
2. **Make every button do something visible or remove it** — S. Birthright: save confirmation line, "Resolve pending events first" message on blocked Advance Turn, delete the stub Delete/Ask-Oracle/filter buttons (or wire them). Wargame: roster-save confirmation in chat, errors to chat not console.
3. **Fix stale Battle Status on Next Phase** — S. Give `BattleChatPanel` a refresh callback (`wargame_app.py:735-744`) that calls `_refresh_all()`.
4. **Add `/help` + command discoverability in Solo RPG** — S. A `/help` handler printing the command list, same list appended to the wargame-mode opening message; and stop routing unknown `/commands` to the GM narrator.
5. **Fix or delete the fictional keyboard shortcuts in Birthright help** — S. Preferably implement Ctrl+S via a `handler_registry` (it's ~6 lines) since Save currently has no feedback anyway.
6. **Load a real font at 16-18px in all three apps** — S. Single shared `_setup_fonts()` with a bundled TTF; biggest visual-quality win per line of code.
7. **Share Birthright's theme across all three apps** — M. Extract `_setup_theme()` (`app.py:81-111`) into `oracle/gui/theme.py`; call it from all three. Instantly "one product."
8. **Remove DEBUG prints and the stray radio placeholder** — S (`wargame_app.py:2010-2070, 1695-1698`).
9. **Unify save locations + named saves for Solo RPG** — M. Everything under `~/.oracle/` (or `sessions/`); Solo RPG gets save-name input instead of one silent quicksave slot; include `wargame_state` in the save payload.
10. **"Repeat Attack" button in wargame** — M. Cache last attacker/weapon/target/modifiers; one click re-rolls. Cuts the shooting-phase click count by ~80%.
11. **Wargame setup dialog on launch** — M. Small modal: game system, commander, optional "load test detachment for both sides" — reuses the wizard pattern users already know from Solo RPG, and gets a new user to a playable battle in 3 clicks.
12. **Responsive text wrap** — M. Use `wrap=0` (wrap to container) or recompute wrap on viewport resize; render bold lines as sequential wrapped text rather than horizontal groups.
13. **Wizard polish** — S. One-line descriptions under Personality combo; "higher chaos = more random events" under the slider.
14. **Decide the wargame story** — L (decision M, code L). Either the Solo RPG's wargame mode is the "narrative wargame" and wargame_app is the "crunchy wargame" — then *say so* in the wizard and window titles — or fold one into the other. Right now two half-overlapping wargame UIs is the suite's biggest conceptual confusion.
15. **Delete dead ChatPanel/SessionPanel views** — S. 962 lines of trap for future maintenance.

---

## Top 10 Recommendations

| # | What | Why | Where | Effort |
|---|------|-----|-------|--------|
| 1 | Auto-scroll chat/battle logs to newest message | Every action currently requires a manual scroll to see its result | `oracle_app.py:1560`, `wargame_app.py:390` | S |
| 2 | Visible feedback for save/blocked-turn/roster ops; kill or wire the 4 dead Birthright buttons | Silent buttons destroy trust in the whole UI | `app.py:304,464`, `domain_action.py:404`, `campaign_select.py:330`, `event_log.py:303`, `wargame_app.py:2201` | S |
| 3 | Refresh Battle Status + Phase Guide on Next Phase | Sidebar lies about turn/phase — core state invisible | `wargame_app.py:735-744` | S |
| 4 | `/help` command + slash-command list in opening message; unknown `/x` → error not GM narration | Six wargame commands are 100% undiscoverable | `oracle_app.py:900-936` | S |
| 5 | Load a 16-18px TTF font in all apps | Default 13px bitmap font caps perceived quality on high-DPI | all three `run()`/`_build_ui()` | S |
| 6 | Extract Birthright theme to `gui/theme.py`, apply everywhere | Three apps become one product visually | `app.py:81-111` | M |
| 7 | Implement Ctrl+S (and fix or delete the help text claiming shortcuts) | Help that lies is worse than no help | `app.py:500-505` | S |
| 8 | Unify saves under one root; named saves; include wargame_state | CWD-relative quicksave is fragile; battle progress silently lost | `oracle_app.py:2066-2092`, `wargame_app.py:2188,3028` | M |
| 9 | Wargame launch setup dialog (system/commander/test armies) | Cold empty-state start vs 3 clicks to a playable battle | `wargame_app.py:2768` | M |
| 10 | "Repeat Attack" in battle log actions | Cuts ~70 clicks per shooting phase to ~10 | `wargame_app.py:435-529` | M |

*Everything above is pixels-in-views work; no model or TOML changes required. Recommendations 1-5 and 7-8 together are roughly one session of work and would transform the perceived quality of the suite.*
