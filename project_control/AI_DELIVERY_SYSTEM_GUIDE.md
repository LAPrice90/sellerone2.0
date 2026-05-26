# AI Delivery System Guide

## Purpose

This guide turns your current AI-assisted way of working into one repeatable system.

The goal is simple:
- turn an idea into a safe plan
- turn the plan into controlled execution
- keep proof and history inside the repo
- stop important knowledge living only in chat threads

This guide does not replace `AGENTS.md`.
`AGENTS.md` remains the main instruction file for Codex behavior in this repo.

## The Core Problem To Fix

Right now the weak point is not idea generation.
It is the handoff between:
- brainstorm
- research
- planning
- execution
- archive

That is why work can feel "80 percent right" but still drift.

Typical failure pattern:
1. good thinking happens in chat
2. plan lives mostly in chat
3. execution starts in a new window
4. the executor solves one task at a time
5. missing context causes stale data, wrong joins, or unsafe assumptions

The fix is:
- store the plan in repo files
- store batch instructions in repo files
- store proof in repo files
- make Codex read those files every time

## The Repo System

Use this structure:

```text
AGENTS.md
CODEX.md
.codex/config.toml

project_control/
  AI_DELIVERY_SYSTEM_GUIDE.md

plans/
  README.md
  active/
    <plan_slug>/
      PROJECT_BRIEF.md
      INCIDENT_BRIEF.md
      PLAN.md
      PLAN_STATUS.md
      EXECUTION_BATCH_001.md
      DEBUG_BATCH_001.md
      EXECUTION_BATCH_001_REPLY.md
      DATA_CONTRACTS.md
      RUNBOOK.md
  archive/
    <year>/
      <plan_slug>/

scripts/
  one_off/
    P001_create_plan_workspace.py
```

## The Working Flow

Follow this order every time:

1. Idea
- Write the business problem in plain language.
- State what hurts today.
- State what "better" looks like.

2. Research
- Use ChatGPT Deep Research only when you need outside facts, patterns, or comparisons.
- Save the useful output in `reference/` or inside the plan folder as research notes.
- Do not treat research as the build plan.

3. Choose the lane
- Create one plan folder in `plans/active/`.
- Then decide:
  - build lane for new work
  - debug lane for existing faults

4. Build lane start
- Write `PROJECT_BRIEF.md`.
- This should explain the business problem in normal language.
- Then write `PLAN.md`.

5. Debug lane start
- Write `INCIDENT_BRIEF.md`.
- State the exact symptom, owner, contract, actual state, and likely blast radius.
- Then write `DEBUG_BATCH_001.md`.

6. Blueprint
- Write `PLAN.md`.
- Lock scope, files, outputs, data owners, freshness rules, and proof rules.
- If the work changes architecture or ownership, record that decision in `project_control/DECISIONS.md` in a separate approved ticket.

7. Execution batches
- Break the blueprint into numbered batches.
- Each batch should be small enough for Codex to finish and verify in one bounded pass.
- Every batch must say:
  - what files may change
  - what must not change
  - what tests must pass
  - what proof must exist

8. Execution
- Start Codex in VS Code inside the repo folder.
- Tell it to read:
  - `AGENTS.md`
  - `CODEX.md`
  - the active plan folder
  - the current batch
- Then tell it to execute only that batch.

9. Proof
- The reply for the batch goes into `EXECUTION_BATCH_###_REPLY.md`.
- Proof must be factual:
  - tests run
  - row counts
  - coverage numbers
  - health rows
  - output paths

10. Archive
- When the plan is complete, move the whole folder from `plans/active/` to `plans/archive/<year>/`.
- Keep the runbook with it.
- Do not rely on memory or chat history later.

## The Flow Chart

```text
request
  -> classify as build or debug
  -> research if needed
  -> brief
  -> batch
  -> codex execution
  -> proof
  -> next batch or archive
```

## Tool Roles

### ChatGPT website

Use it for:
- brainstorming
- Deep Research
- finding missing factors
- pressure-testing assumptions
- turning rough thoughts into cleaner notes

Do not use it as the only home for the plan.

### Codex in VS Code

Use it for:
- reading the repo
- following repo instructions
- editing files
- running tests
- showing proof
- keeping work tied to actual repo artifacts

## Recommended Role Split

Use this split consistently:

- Architect:
  - GPT
  - planning, design, risk review, gap finding
- Builder:
  - Codex
  - code changes, tests, batch execution, proof capture
- Inspector:
  - GPT
  - review of logic, assumptions, and hidden risks

This matters because the system becomes unstable when thinking and execution are mixed carelessly.

## Recommended Settings By Phase

Treat these as working guidance, not permanent hardcoded config:

- Planning:
  - GPT
  - high reasoning
- Research:
  - Deep Research
  - high effort
- Execution:
  - Codex
  - medium to high reasoning
- Batch execution:
  - Codex
  - high reasoning, strict scope
- Review:
  - GPT
  - high reasoning
- Small fixes:
  - Codex
  - medium reasoning

### Current agent setup

You already have an agent setup in this repo.
Do not replace it with a separate system.
Align the new process to it:

- `AGENTS.md` stays the top behavior authority
- `CODEX.md` becomes a short session handoff file
- `.codex/config.toml` points Codex at `CODEX.md` as an allowed fallback instruction file
- plan folders become the durable memory for each ticket

## Two Lanes, One System

Use one operating system with two lanes.

### Build lane

Use for:
- new features
- new outputs
- new extensions

Main files:
- `PROJECT_BRIEF.md`
- `PLAN.md`
- `EXECUTION_BATCH_###.md`

### Debug lane

Use for:
- broken existing behavior
- stale data
- wrong joins
- missing updates
- integration faults

Main files:
- `INCIDENT_BRIEF.md`
- `DEBUG_BATCH_###.md`

Debug mindset:
- an error is not just a task
- it is a violation of expected behavior
- identify the owner and contract first
- compare expected state vs actual state
- fix the earliest broken stage

## The Plan Folder Rules

Each new plan folder should contain:

### `PROJECT_BRIEF.md`
- plain-language problem
- business goal
- constraints
- definition of success

### `INCIDENT_BRIEF.md`
- exact symptom
- when it was first noticed
- owner system
- expected contract
- actual state
- suspected blast radius

### `PLAN.md`
- current state
- target state
- file ownership
- data contracts
- health and freshness checks
- risk list
- batch list

### `PLAN_STATUS.md`
- one simple checklist:
  - not started
  - in progress
  - blocked
  - done

This file is for quick orientation when you reopen the project later.

### `EXECUTION_BATCH_###.md`
- exact work order for Codex

### `DEBUG_BATCH_###.md`
- exact debug work order for Codex

### `EXECUTION_BATCH_###_REPLY.md`
- factual proof of what happened

### `DATA_CONTRACTS.md`
- what each dataset is
- who owns it
- where it lives
- how fresh it must be
- what breaks if it goes stale

### `RUNBOOK.md`
- how to run
- how to validate
- where to look when something breaks

## Anti-Drift Rules

These are the rules that stop "looks right" work from poisoning the system.

1. One owner per output
- Every dataset must have one producing script.
- Consumers read it.
- Consumers do not quietly replace it.

2. Freshness must be written down
- If a dataset matters, record:
  - source
  - output path
  - freshness warning point
  - freshness fail point

3. Every plan must name integration points
- APIs
- sheets
- CSV outputs
- local DB tables
- live loops

4. Every batch must state blast radius
- what can be affected
- what cannot be touched

5. Every change needs proof
- code changed is not the same as fixed

## How To Prompt Codex

Use short, direct handoffs.

Good start pattern:

```text
Read AGENTS.md, CODEX.md, and plans/active/<plan_slug>/PLAN.md.
Then read EXECUTION_BATCH_001.md.
Summarise the batch scope, files allowed to change, tests required, and proof required.
Do not code until that summary is complete.
```

Good execution pattern:

```text
Execute only EXECUTION_BATCH_001.md.
Do not widen scope.
Run the listed tests.
Write the proof into EXECUTION_BATCH_001_REPLY.md.
```

Good debug pattern:

```text
Read AGENTS.md, CODEX.md, INCIDENT_BRIEF.md, and DEBUG_BATCH_001.md.
Classify the failure, identify the owner and expected contract, and compare actual state vs expected state before changing code.
Fix the root cause in the owning stage, then run the listed proof steps and write the result into EXECUTION_BATCH_001_REPLY.md.
```

Good repair pattern:

```text
Read the batch reply and the failing output.
Find the root cause.
Fix the earliest broken stage, not the final output.
```

## Settings Guide

Your rule about models is correct:
- do not hardcode a model name in business scripts
- do not build your workflow around one model staying best forever

Use this split:

### Repo behavior settings
- live in `.codex/config.toml`
- example use:
  - allow fallback file names like `CODEX.md`
  - store repo-specific Codex behavior

### Business script settings
- live in config files or environment variables
- example use:
  - API keys
  - endpoints
  - model names when a script truly needs one
  - timeout values
  - retry limits

### Planning rule
- In user guides, say "best available approved model" instead of pinning one forever.
- Change model choice in config, not by rewriting process docs.

## A Safe Standard For New Builds Or Extensions

Before adding a new build or extension, answer these questions in `PLAN.md`:

1. What business problem does this solve?
2. What existing system does it touch?
3. What files are the source of truth?
4. What output will it create?
5. Who owns that output?
6. How will stale data be detected?
7. What health check will be added?
8. What batch proves it works?
9. How is rollback done?
10. Where will the finished plan be archived?

If any answer is missing, planning is incomplete.

## Recommended Ticket Shape

For larger work, use this pattern:

1. Planning ticket
- research
- brief
- blueprint
- contracts
- batch breakdown

2. Implementation tickets
- one batch per ticket where possible

3. Validation ticket
- confirm live evidence after the next scheduler-owned cycle if needed

This matches the repo rule that planning and implementation should be separated when proof is not yet complete.

## Archive Rules

Archive a plan only when:
- all planned batches are complete or intentionally closed
- the runbook exists
- the final status is clear
- open risks are written down

Archive steps:
1. move folder from `plans/active/<plan_slug>/` to `plans/archive/<year>/<plan_slug>/`
2. keep all batch files and reply files
3. leave no "important memory" only in chat

## The Main Habit Change

The system becomes reliable when you stop asking AI to remember the project for you.

The repo should remember:
- what the project is
- why it exists
- what is in scope
- what was changed
- what proof exists
- how to restart the work later

That is the whole design goal of this workflow.
