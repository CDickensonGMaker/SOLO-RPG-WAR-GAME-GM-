# DPG Engineer — Technical UI Analysis
*War Room UI/UX Audit, 2026-07-07. Lens: DearPyGui implementation reality.*

Environment verified: **dearpygui 2.3.1** on **Python 3.14.2** (pip show). Live surfaces:
`oracle/gui/oracle_app.py` (2,193 ln), `oracle/gui/wargame_app.py` (3,303 ln),
`oracle/gui/app.py` (545 ln, Birthright) + `views/`, `components/`.

---

## 0. Reality check: do the three apps still boot?

**Method:** static import, not headless launch (a headless `start_dearpygui()` would block).
Ran `python -c "import oracle.gui.oracle_app; import oracle.gui.wargame_app; import oracle.gui.app"`
from repo root — **all three import clean**. None of the modules build UI at import time
(Oracle/Birthright create context inside `run()`; WargameApp creates context in `__init__._build_ui`,
which only fires on instantiation in `main()`). Boot sequences are all legal DPG lifecycle order
(`create_context → build → create_viewport → setup → show → start → destroy`): `oracle_app.py:155-177`,
`wargame_app.py:2768-2771` + `3273-3289`, `app.py:58-79`. The `.bat` files point at real entry points
(`Oracle.bat → python -m oracle.gui.oracle_app`, `Wargame.bat → ...wargame_app`, `Birthright.bat →
...gui.launcher`). **No construction-time breaks found.** Caveat: this proves importability and
correct lifecycle order, not pixel-perfect behavior — someone still needs to click through once.

One boot-adjacent smell: `Birthright.bat` runs `pip install dearpygui>=1.9` on failure —
unquoted, `>=1.9` is a shell redirect in cmd, so it would actually run `pip install dearpygui`
and write a file named `=1.9`. Harmless today (dpg is installed), wrong if ever exercised.

---

## 1. Theming & fonts

**Fonts: zero custom fonts in the entire package.** `grep add_font|font_registry|bind_font|
set_global_font_scale` over `oracle/` returns nothing. `oracle_app.py:179-182 _setup_fonts()` is
literally `pass`. All three apps run DPG's built-in 13px ProggyClean bitmap font — small, thin,
and the single biggest readability cost for an app whose primary surface is *paragraphs of GM
narration*. No DPI handling anywhere (no `set_global_font_scale`, no viewport resize callback);
on a high-DPI laptop the text is tiny.

**Themes: 1 of 3 apps themed.**
- Birthright `app.py:81-111` registers a proper global theme (warm dark palette, rounding, padding) — the only one.
- Oracle `oracle_app.py` — **no `dpg.theme()` at all**; stock ImGui navy-blue look. Color identity exists only as per-item text colors from the `COLORS` dict (`oracle_app.py:58-68`).
- Wargame `wargame_app.py` — same, no theme; a *third* independent hardcoded palette scattered through `BattleChatPanel._render_message` (`wargame_app.py:393-425`) and every panel.

So the three apps look like three different products, and two of them look like debug tools.

**Cost of a proper pass: S.** One shared module `oracle/gui/style.py` exposing
`setup_fonts()` (load `C:\Windows\Fonts\segoeui.ttf` or a bundled TTF at 17-18px via
`dpg.font_registry` + `dpg.bind_font` — stdlib only, no new dependency) and `apply_theme()`
(lift the existing Birthright theme verbatim). Three call sites, ~80 lines total, transforms
perceived quality of all three apps at once. This is the best cost/impact ratio in the codebase.
Note the DPG gotcha: fonts must be registered after `create_context()` and are baked at one size —
pick 17px and stop; runtime font-size sliders are not worth it in DPG.

## 2. Layout technique

Generally the right idiom — nested `child_window`s with negative widths, not absolute `pos=`:
- Oracle: chat `width=-280` + sidebar `width=270` (`oracle_app.py:489-493`); chat log `height=-70`.
- Wargame: left 300 / center `-350` / right 340 (`wargame_app.py:2812-2841`).
- All three call `set_primary_window` correctly (`oracle_app.py:485`, `wargame_app.py:2853`, `app.py:188`).

Resize survives structurally, **but text does not reflow**: every chat line is
`add_text(..., wrap=600)` (`oracle_app.py:1611-1616`) or `wrap=500` (`wargame_app.py:427-431`).
On the Wargame's 1600px viewport the center pane is ~950px and text occupies half of it; shrink
the window and text clips instead. `wrap` is a pixel constant — the honest fixes are (a) accept a
computed wrap at build time, or (b) leave `wrap=0` inside a child_window sized by the layout
(DPG wraps at item width when wrap=0 only for `add_text` with a parent width — in practice a
per-message recompute on a `viewport_resize` callback is the workable route). Cost M, only worth
it after the font pass.

Two genuinely fixed-pixel offenders:
- Every modal in all three apps uses hardcoded `pos=[400,200]`-style constants (`oracle_app.py:1793`, `wargame_app.py:467, 1114`, dozens more). Birthright at least computes from `config.window` dims (`app.py:374`) — but from *config*, not the live viewport, so wrong after any resize. Cheap fix: one helper `centered_pos(w,h)` using `dpg.get_viewport_client_width()`. Cost S.
- Birthright panels size themselves from `config.window.width * proportion` at build time (`views/dashboard.py:48`) — a resize leaves stale panel widths. Cost S-M.

## 3. Widget choices — unused DPG capabilities

**Used well:** `drawlist` in `map_view.py` and `npc_graph.py` (lines 32-297 / 35-267) — the right
tool, genuinely good; `tab_bar` in wargame wargear/chaos dialogs and right sidebar
(`wargame_app.py:1539, 1683, 2843`); `collapsing_header` in PhaseGuidePanel (`wargame_app.py:2482-2510`).

**Unused where they'd clearly win:**
- **`add_table`: zero occurrences in the whole GUI.** The ForcePanel unit list (`wargame_app.py:1055-1087` — selectable + ad-hoc text columns), the force-org validation breakdown (`wargame_app.py:2106-2126`), saved roster/battle lists (`wargame_app.py:2247-2263, 3107-3123`), and the unit stat-line editor (`wargame_app.py:1176-1197` — nine `input_int`s in horizontal groups) are all tables pretending not to be. `mvTable` gives alignment, row striping, sorting, and resizable columns for free. Cost S per list, M for the stat editor.
- **`add_tooltip`: only in orphaned `components/dockable_panel.py` (121-208), which nothing imports.** A wargame app that shows `WS/BS/S/T/I/A/Ld/Sv` abbreviations and doctrine names is the canonical tooltip use case. Cost S.
- **Keyboard/handler registries: zero** (`grep key_press|handler_registry` → nothing). Worse, Birthright's help window *advertises* Ctrl+S / Ctrl+N / R shortcuts (`app.py:500-505`) that do not exist anywhere. Either implement (S — one `dpg.handler_registry` block) or delete the lie (trivial).
- **`focus_item`: zero.** After Send, the chat input keeps focus only by accident of `on_enter`; clicking Send loses it. `dpg.focus_item("chat_input")` at the end of `_on_send` — one line.
- **Auto-scroll:** the only `set_y_scroll` in the codebase is *commented out* in dead code (`views/chat_panel.py:125`). Neither live chat log ever scrolls to the newest message (`oracle_app.py:1560-1586`, `wargame_app.py:390-433`). Fix is two lines per app: after rendering a message, `dpg.set_y_scroll(log, -1.0)` (or `get_y_scroll_max` on the next frame via `set_frame_callback` — DPG computes max after layout, so the next-frame variant is the reliable one). **Highest-impact S fix in the audit.**

**Chat rendering approach** (`oracle_app.py:1588-1618 _render_text`): hand-rolled markdown-lite.
Two concrete bugs: (1) a line containing `**bold**` is emitted as one `group(horizontal=True)` of
text segments — a long bold line **cannot wrap** and overflows the panel clip; (2) bold is faked
as a color change (no bold font registered). Verdict: keep the approach (DPG has no rich-text
widget; this is the standard workaround) but render bold *lines* as separate wrapped
`add_text` with a bold font variant from the font pass, and only use horizontal groups for short
inline runs. Cost M. Do **not** promise real mixed-style inline wrapping text — DPG fundamentally
doesn't do it.

## 4. Responsiveness & callback hygiene

- **UI-thread blocking:** No worker threads exist anywhere in the GUI (`grep Thread` in `oracle/gui` → only the word "Threads" in a label, `oracle_app.py:573`). Today that's *acceptable* because the brain is local and synchronous: the heaviest callback work is TOML/JSON file I/O done inside dialog-open callbacks (`wargame_app.py:1105 load_factions_for_system`, `2212-2227` roster scans, `3072-3086` battle scans) — milliseconds at current data sizes. The CLAUDE.md rule isn't violated yet, but the first LLM/network feature will freeze the window; there is no marshalling scaffold to plug into. Flag as debt, not a bug.
- **`does_item_exist` discipline: good.** The delete-before-recreate pattern is applied consistently (~40 sites, e.g. `oracle_app.py:1784-1785`, `wargame_app.py:437-438`). Per-instance tag prefixes via `id(self)` in wargame panels (`wargame_app.py:318-320, 960-962`) are correct.
- **Item leaks: yes, the chat logs.** Both apps append groups of items per message and never trim (`oracle_app.py:1565`, `wargame_app.py:392`); `self.messages` also grows unbounded. A three-hour session = thousands of live text items. DPG tolerates a lot, but a cap (delete oldest group beyond ~300 messages) is 10 lines. Cost S.
- **Real state bugs found while auditing:**
  - `wargame_app.py:1695-1698` — a placeholder `add_radio_button(items=[""], tag=f"mark_...")` per Chaos mark ("Placeholder for proper radio") renders a stray dead radio dot above every mark checkbox. Delete it.
  - Wargear/Chaos checkbox state desyncs from the backing lists: reopening the dialog rebuilds all checkboxes unchecked while `_selected_wargear` persists (`wargame_app.py:1550-1554` vs `1592-1605`) — checking a previously-selected item then *removes* it (inverted toggle). Also "Clear All" tries to uncheck via `get_item_children("wargear_dialog", 1)` (`wargame_app.py:1613-1619`), which only sees direct children — the checkboxes live inside tab/child_window descendants, so nothing unchecks.
  - Leftover `print("DEBUG: ...")` in shipped callbacks (`wargame_app.py:2010-2070`).
  - `oracle_app.py:973` — `except ValueError as e:` binds `e` unused; cosmetic.
- **Callback args/user_data:** conventions followed; loop closures correctly use default-arg binding (`wargame_app.py:890, 1073`) or `user_data` (`oracle_app.py:1896-1902`). No "last button wins" bugs found.

## 5. Startup & structure: three apps, three .bat files

Current duplication is large and mechanical:
- **Two divergent copies of the same chat UI** (`OracleApp._render_message/_render_text` vs `BattleChatPanel._render_message`) plus a third orphaned one (`views/chat_panel.py` + `views/session_panel.py`, exported by `views/__init__.py:15-16`, imported by nothing).
- **Three color palettes**, one theme, zero shared style code.
- **Duplicate dialogs**: oracle-question dialog exists in `app.py:363-415` and `oracle_app.py:1782-1871`; dice dialogs in `oracle_app.py:1873-1920` and `wargame_app.py:852-932`, all with copy-pasted layout code and even colliding tag names (`"dice_dialog"`, `"oracle_dialog"` — safe only because the apps never share a process *today*).

**Single launcher feasibility — honest assessment:** a *launcher shell* (small DPG window with
three buttons that `subprocess.Popen`s the chosen app, or a mode-select screen that then builds
one app in the same process) is **S — an afternoon**. A *true in-process mode switcher* is **L and
a trap**: each app owns module-level global tags (`"main_window"`, `"chat_log"`, `"dice_dialog"`…),
its own theme assumptions, and its own viewport size; switching modes means full teardown
(`delete_item` everything or `destroy_context`/recreate — DPG supports one viewport per process,
so it's teardown-and-rebuild, not side-by-side). Recommendation: ship the S launcher (one
`Oracle.bat` replacing three), share `style.py`, and *stop there* until the tag namespaces are
unified. The prerequisite refactor is exactly the shared chat-panel extraction above.

## 6. Ranked list: quick wins vs money pits

| # | Item | Where | Cost | Impact |
|---|------|-------|------|--------|
| 1 | Auto-scroll chat logs to bottom on new message | `oracle_app.py:1560`, `wargame_app.py:392` | **S** (2-4 lines each) | Huge — core loop is unusable past one screenful |
| 2 | Shared `style.py`: real font (17px Segoe/bundled TTF) + lift Birthright theme to all 3 apps | new file + 3 call sites | **S** | Huge — readability + "one product" feel |
| 3 | Refocus chat input after Send; cap chat log at N messages | `oracle_app.py:888-898` | **S** | Medium |
| 4 | Center modals from live viewport size (one helper, ~30 call sites are mechanical) | all apps | **S** | Medium |
| 5 | Delete placeholder radio dots; fix wargear checkbox desync + Clear All; strip DEBUG prints | `wargame_app.py:1695, 1592-1619, 2010-2070` | **S** | Medium (dialog currently feels broken) |
| 6 | Tooltips on stat abbreviations, doctrines, phase names | wargame panels | **S** | Medium |
| 7 | Implement or delete Birthright's advertised shortcuts; add Enter-to-confirm on modals via `handler_registry` | `app.py:500-505` | **S** | Small-Medium |
| 8 | Single launcher .bat + DPG mode-select that spawns the chosen app as a subprocess | new ~60-line module | **S-M** | Medium |
| 9 | Convert unit lists / force-org / saved-roster lists to `add_table` | `wargame_app.py:1055, 2106, 2247` | **M** | Medium-high polish |
| 10 | Extract one shared ChatPanel used by both chat apps (kills 2 duplicates + wires in items 1/2/3 once); delete orphaned `views/chat_panel.py`, `session_panel.py`, `components/dockable_panel.py` or adopt them | `oracle/gui/views/` | **M** | High, enables everything later |
| 11 | Text reflow on resize (recompute wrap on `viewport_resize`) | both chat apps | **M** | Medium |
| 12 | Worker-thread scaffold for future slow ops (queue + frame-callback drain) | shared | **M** | Zero today, mandatory before any LLM feature |
| 13 | True in-process mode switcher (one viewport, three modes) | all | **L** | Low until tags/theme unified — **defer** |

**Things DPG fundamentally does badly — do not promise:** rich text (inline bold/italic within
wrapped paragraphs), runtime font resizing, multi-viewport/detachable windows, native file dialogs
(DPG's is ugly but present — current save dialogs sensibly use fixed dirs instead), smooth
scrolling/animations, and web-style CSS layout. The markdown-lite compromise is correct; invest in
theme/font/spacing, not in fighting the retained-mode ImGui model.

---
*Bottom line: the codebase already uses the right DPG skeleton (child_windows, negative widths,
tag hygiene, drawlists where they matter). What's missing is one shared style module and five
S-sized fixes — nearly all perceived jank traces to default font, no theme on 2/3 apps, no
auto-scroll, and one visibly buggy wargear dialog. All three apps import clean as of today.*
