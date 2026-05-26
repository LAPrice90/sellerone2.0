# SellerOne Endgame Command Center

Created: 2026-05-26
Scope: planning only, no script edits, no cycle runs.

## Purpose

This folder is the plain-English control room for finishing SellerOne.

The existing repo already has many good plans, but they are spread across `project_control/`, `plans/active/`, `out/`, and older handoff notes. This folder does not replace those files. It turns them into one working checklist so each Goal Pursue session can finish one clear job at a time.

Think of this as the building-site clipboard:

- the roadmap says what the building should become
- the guidebooks say how the plumbing and electrics work
- these checklist files say what trade turns up next and what "finished" means

## How To Use This Folder

1. Start with `MASTER_ENDGAME_CHECKLIST.md`.
2. Pick one cycle file only.
3. Ask Codex or Goal Pursue to research that file and update the checklist before coding.
4. Only after the checklist is clear, approve an implementation phase.
5. After every implementation phase, require proof from the artifact named in the task.

Suggested prompt:

```text
Use plans/active/sellerone-endgame-command-center-2026-05-26/<FILE>.md as the active checklist. Research only first. Do not change code until the phase and proof path are clear.
```

## Built-In Checklist Answer

Codex has a temporary chat checklist, but chat memory is not enough for this project.

The durable checklist for this repo should be these local files:

- `MASTER_ENDGAME_CHECKLIST.md` - the overall order of work
- `O_RESTOCKING_TODO.md` - existing SKU restocking and buying path
- `F_PRICE_LIST_SCANNER_TODO.md` - supplier price lists, scanner, new product review, listing handoff
- `H_REPRICER_TODO.md` - repricer and market-proof stability
- `A_CYCLE_TODO.md` - daily data and health gate
- `B_CYCLE_TODO.md` - orders, tokens, COGS, sales truth
- `E_ANALYTICS_TODO.md` - ROI, velocity, restock maths support
- `GOVERNANCE_EXTERNAL_TODO.md` - due checks, storage, scheduler, external integrations

## Rule

Do not use this folder to hide bad data. If a task exposes a broken source, fix or escalate the source first.

