# Oracle Agent Team — install & use

This is a five-agent Claude Code team built for your Oracle app, plus a `CLAUDE.md` that keeps
every session on the rails. You don't need to write any Python to set this up — just copy files
into the right folders.

## What you got
```
your-oracle-project/
├─ CLAUDE.md                      ← auto-loaded rules for every session (the always-on bumper)
└─ .claude/
   └─ agents/
      ├─ oracle-architect.md      ← plans & guards the architecture (use FIRST)
      ├─ gamemaster-designer.md   ← solo RPG / wargame / Birthright rules expert
      ├─ dpg-engineer.md          ← writes the Python + DearPyGui code
      ├─ code-reviewer.md         ← reviews every change (bumper)
      └─ qa-tester.md             ← writes & runs tests (bumper)
```

## Install (one time)
1. Put `CLAUDE.md` in the **root of your Oracle project** (same folder you open Claude Code in).
2. Create a `.claude/agents/` folder there and drop the five `.md` agent files inside.
3. **Restart Claude Code** in that folder. Agent files are only read at startup, so a new or
   edited agent won't appear until you restart.
4. Type `/agents` to confirm all five show up. (`/agents` is also how you create or edit agents
   interactively later.)

These are **project-level** agents — they only exist when you run Claude Code inside this
project, and they travel with the repo if you ever use git. If you want the
`gamemaster-designer` available in *every* project, copy that one file to `~/.claude/agents/`
instead.

## How to use it day to day
Claude will auto-pick an agent when a task matches its description, but you'll get the best
results by **driving the workflow yourself**, especially while you're learning. A normal loop:

1. **Start with a plan.** "Use the oracle-architect to plan adding an exceptional-yes result to
   the oracle." → you get a short written plan and a list of small steps, with risks called out.
2. **Build a rule.** "Have the gamemaster-designer implement step 1." → mechanics go into a
   model + TOML, deterministic and testable.
3. **Wire the UI.** "Have the dpg-engineer add the panel button for it." → the DearPyGui code.
4. **Review.** "Have the code-reviewer check that change." → findings by severity, with fixes.
5. **Test.** "Have the qa-tester cover the new oracle logic." → pytest tests that prove it works.

You can name an agent explicitly (best while learning) or just describe the task and let Claude
delegate. If a review comes back with blockers, send them back to the builder: "have the
dpg-engineer fix the 🔴 items."

## The bumpers, in plain terms
Three things keep the program from running away from you:
- **CLAUDE.md** — silently reminds every session of the golden rule (logic in models, pixels in
  views, rules in TOML) and "smallest change that works."
- **oracle-architect** — refuses to let a small request balloon into a 10-file rewrite; makes a
  plan you approve before code happens.
- **code-reviewer + qa-tester** — catch the bugs you can't see yet and prove changes didn't break
  what already worked.

## Tweaks you might make later
- **Cost vs. power:** `oracle-architect` and `gamemaster-designer` are set to `opus` (strong
  reasoning for planning and rules); the others use `sonnet`. To spend fewer tokens, change a
  `model:` line to `sonnet` or `inherit` (use whatever the session is on).
- **Tighter or looser tools:** each agent's `tools:` line controls what it can do. The reviewer
  is intentionally read-only. Edit these in `/agents` or directly in the file (restart after).
- **Add a 6th agent** only if you feel a real gap. More agents = more to manage; five is a
  deliberate, beginner-friendly size.

Start small: open Claude Code in the project, run `/agents` to confirm the team loaded, then ask
the architect to plan the next thing you want to build.
