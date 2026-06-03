# CLAUDE.md — Oracle project rules

This file is loaded automatically into every Claude Code session in this project. It is the
main "bumper." Keep it short and true; update it when the project changes.

## What Oracle is
A Python **desktop app built with DearPyGui** — a solo tabletop gaming assistant with three
modes:
- **Solo RPG** — Mythic-style GM emulator: yes/no oracle weighted by odds + chaos factor,
  dice, random events, scene/thread/NPC tracking.
- **Wargame** — tactical AI opponent: army building, unit rosters, turn/phase tracking, threat
  assessment, doctrine-based AI, rules reference.
- **Birthright Campaign** — domain-level AD&D play: regency, bloodline, holdings, domain turns.

Game system data loads from **TOML files**, one per ruleset (Oldhammer, Trench Crusade, OPR
Grimdark Future, …).

## The golden rule (do not break this)
**Logic lives in models. Pixels live in views/panels. Rules and numbers live in TOML.**
- Models (WargameDataModel, BattleRosterModel, …): pure data + game logic, **no DearPyGui calls.**
- Views/Panels (ChatPanel, SessionPanel, TacticalAIPanel, …): **DearPyGui only, no game rules.**
- The GM "brain" connects input → models → response. Panels talk to models through the brain.
- System-specific numbers/tables → TOML, never hard-coded into shared logic.

## How we work here (the owner is a beginner programmer building via AI)
1. **Plan before code.** For anything beyond a one-file tweak, the `oracle-architect` writes a
   short plan first. No big surprise rewrites.
2. **Smallest change that works.** No new dependency, abstraction, or config layer without a
   concrete present reason — and say the tradeoff out loud.
3. **One small, testable step at a time.** Build → review → test, not a giant batch.
4. **Always review and test new logic.** `code-reviewer` after code; `qa-tester` after rules.
5. **Explain changes in plain English** — what changed and what to click to see it.

## Technical conventions
- Read TOML with `tomllib`; wrap loads so a bad file gives a readable error, not a stack trace.
- Every DearPyGui item gets an explicit unique `tag=`. Check `does_item_exist` before recreating.
- Callbacks pass state via `user_data`, never closures over loop variables.
- Never block the UI thread — long work (brain, parsing, network) runs in a worker thread.
- Type hints on function signatures; small functions; clear names a beginner can re-read later.
- Random/dice functions take an injectable RNG or seed so they're testable.
- Tests use `pytest` and live in `tests/`.

## Copyright
Published rules (Mythic / Word Mill, Warhammer / Games Workshop, Birthright / WotC, Trench
Crusade) are IP. Implement mechanics as **original code**; do not paste copyrighted rule text or
verbatim stat tables into the repo. The owner supplies legally-owned numbers via TOML. OPR rules
are freely licensed and fine to use directly.

## The agent team (see .claude/agents/)
- **oracle-architect** — plans, guards architecture, blocks scope creep. Use first.
- **gamemaster-designer** — solo RPG / wargame / Birthright rules + TOML. The domain expert.
- **dpg-engineer** — writes the Python + DearPyGui code.
- **code-reviewer** — reviews every change for bugs and layering violations.
- **qa-tester** — writes/runs deterministic tests for game logic.


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
