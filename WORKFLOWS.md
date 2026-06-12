# How I Use Coding Agents Day-to-Day

## Tool stack

- **Claude Code** (primary) — long-context agent for anything requiring multi-file reasoning, report generation, or structured output. Lives in the terminal; I keep it open the same way I keep a browser open.
- **Cursor** — for fast in-editor edits where I want inline suggestions and can approve hunks directly. Use it for surgical changes; avoid it for anything requiring broader codebase context.
- **GitHub Copilot** — autocomplete in hot paths. I treat it as a fast typist, not a thinker.
- **Custom CLAUDE.md skills** — project-specific slash commands I define per repo. This take-home is a good example: `/audit [URL]` encodes the full Crawl-Reason-Write lifecycle so the agent doesn't need re-briefing each run.

## Delegation patterns

**I let agents drive:**
- First drafts of anything structured (reports, specs, schema definitions, test cases)
- Multi-step research pipelines where I'd otherwise tab-switch 10+ times
- Boilerplate generation and file scaffolding
- Refactors with a clear mechanical rule ("rename all snake_case to camelCase in this module")
- Generating eval rubrics and scoring logic

**I always take the wheel:**
- Final review before any file is committed or any output is sent externally
- Any decision involving prod infrastructure, secrets, or shared state
- Ambiguous requirements — I write the spec myself before handing off
- Anything where a wrong answer is worse than a slow answer (security, compliance, money movement)

## Custom skills and slash commands I've built

- `/audit [URL]` — this project's Crawl-Reason-Write pipeline (see CLAUDE.md)
- `/review [PR]` — pulls diff, runs through a rubric of security, performance, and correctness, outputs a structured review comment
- `/spec [feature]` — generates a two-section spec: user story + technical constraints, then waits for my edits before any implementation
- `/migrate [old] [new]` — handles API version migrations with a before/after diff preview before touching files

## What I've learned about agent delegation

The best way to delegate to an agent isn't to give it a task — it's to give it a **contract**: the input format, the output format, and the quality bar. An agent given "write a CRO audit" produces something generic. An agent given a target report, a schema for 10 experiments across 5 pillars, and a no-hallucinations bar produces something shippable. The investment in the harness (CLAUDE.md) pays back on every run.

The failure mode I watch for is **confident slop** — output that looks right and is wrong in a non-obvious way. I treat every agent output as a first draft that I own. The agent writes it faster than I could; I review it faster than I could write it from scratch. That division of labor is the actual productivity unlock.
