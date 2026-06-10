# SO21 First Overnight Run Efficiency Plan

Created: 2026-06-09
Owner: Rep and Operations
Mode: management plan, no implementation

## Plain-English Purpose

The first overnight SellerOne 2.1 run proved that the new control desk can create work, survive the 02:00 PC restart, produce reports, and use Workers and Reviewers.

It also showed that the system is not yet smooth enough. The main issue is not that Workers cannot work. The main issue is that work movement is not visible enough, proof closure is too slow, and worker/reviewer threads can look like extra managers.

This plan tunes the control layer so SellerOne can run today and tomorrow without Luke needing to watch every handoff.

## What Worked

- Operations kept work in the control layer and did not change business runtime.
- The 02:00 PC restart recovery check passed.
- Morning improvement reporting was produced and reviewed.
- Data lifecycle, retention, duplicate-data, cleanup-design, maintenance, and script-health planning were created.
- Task Scheduler new-style review passed after repair.
- Amazon LWA credential status check returned HTTP/status code 200.
- No protected price, Sheet, database, Amazon/security, purchase, receiving, send-to-Amazon, scheduler-edit, runtime-stop, deletion, or cleanup-apply action was performed.

## What Slowed Us Down

### 1. Proof Closure Was Too Slow

Several jobs reached worker-output or reviewer-output, but the queue did not always close the loop quickly.

Example:

- `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW` passed retest, but the readable queue still needed status movement.
- `SO21-CREDENTIAL-TOKEN-STATUS-CHECK` passed with HTTP/status code 200, but the reviewer returned a format-only issue.

Business impact:

- Luke sees "waiting proof" and "no builder working", which feels like nothing is moving.

Required change:

- Operations must treat proof closure as a first-class job.
- Every pass must either close a waiting-proof item, send it back for a narrow repair, start the next approved item, or record a blocker.

### 2. The Board Does Not Show Real Movement Clearly Enough

The generated packet index updates many rows at once. That shows the board refreshed, but it does not prove the job itself moved.

Business impact:

- It is hard to tell whether a job is active, stale, blocked, waiting reviewer, or simply refreshed.

Required change:

- Add a Queue Movement Board that shows:
  - job reference
  - current stage
  - last real movement time
  - last real movement type
  - assigned role
  - worker/reviewer thread label
  - age in stage
  - next expected action
  - blocker reason if idle

### 3. Worker And Reviewer Threads Look Like Extra Managers

The operating model is still correct:

- Rep Chat talks to Luke.
- Operations is the single Shift Manager.
- Worker threads execute one packet.
- Reviewer threads verify one packet.

The issue is visibility and naming. Some Worker and Reviewer threads are titled in a way that makes them look like more management chats.

Business impact:

- Luke sees many threads and loses confidence that the structure is clean.

Required change:

- Add thread hygiene rules:
  - only two manager chats are allowed: Rep and Operations
  - every Worker thread title starts with `Worker - <job_ref>`
  - every Reviewer thread title starts with `Reviewer - <job_ref>`
  - completed Worker/Reviewer threads should be archived or left clearly completed
  - Workers and Reviewers must start from task packets, not Rep-chat history

### 4. Reviewer Strictness Needs A Business-Severity Split

Reviewers should still be strict on safety. But format-only issues should not make a successful business result look failed.

Example:

- Amazon LWA check passed with status code 200.
- Reviewer found no exposed secret.
- The only issue was an extra safe line in the report.

Business impact:

- A safe pass can look like a failure.

Required change:

- Add review grades:
  - `pass`
  - `pass_minor_format_repair`
  - `returned_material_gap`
  - `blocked_needs_luke`
  - `failed_safety`
- Only material gaps, safety issues, and Luke decisions should stop the line.

## Today And Tomorrow Operating Plan

### Workstream A - Cleanup To Blueprint

Goal:

- Finish making the new control desk the real source of truth.

Today:

- Close `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW` as proved in the queue.
- Start `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN`.
- Keep `SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST` ready, but do not delete anything.

Success measure:

- No old manager folder, old work log, or old plan folder is treated as live control.
- Cleanup candidates are dry-run only and approval-gated.

### Workstream B - Maintenance Mode Operator Control

Goal:

- Turn maintenance mode from a safety design into a usable operator process.

Today:

- Define the safe operator controls for status, pause request, restart request, and proof check.
- Keep Business Runtime protected unless Luke approves a named target.
- Use Control Desk Automation as the first safe test area.

Tomorrow:

- Create the first script/tool packet only after the operator design is reviewed.

Success measure:

- Operations can tell what is running, what can be paused, what must not be touched, and what proof is needed after restart.

### Workstream C - Professional-Level App Analysis

Goal:

- Turn the improvement findings into a customer-style proposal with evidence, graphs, risks, and business value.

Today:

- Use the morning improvement report, storage reports, scheduler review, and maintenance plan as the evidence base.
- Start with storage, reliability, proof visibility, and worker efficiency.

Tomorrow:

- Produce the first proposal-style report for Luke showing expected benefit, effort, risk, and recommended order.

Success measure:

- Luke can choose the next build priorities from a business proposal, not scattered technical notes.

## New Control Improvements To Create

### 1. Queue Movement Board

Job reference:

- `SO21-QUEUE-MOVEMENT-BOARD`

Purpose:

- Show whether each job is actually moving.

Output:

- `CONTROL/SO21_QUEUE_MOVEMENT_BOARD.md`

### 2. Thread Role Hygiene Register

Job reference:

- `SO21-THREAD-ROLE-HYGIENE`

Purpose:

- Separate the two managers from one-job Worker and Reviewer threads.

Output:

- `CONTROL/SO21_THREAD_ROLE_HYGIENE.md`

### 3. Proof Closure Rules

Job reference:

- `SO21-PROOF-CLOSURE-RULES`

Purpose:

- Stop safe business passes being made to look blocked by minor formatting issues.

Output:

- `CONTROL/SO21_PROOF_CLOSURE_RULES.md`

## Frequency Change Already Applied

The Operations Shift Manager heartbeat was changed from every 30 minutes to every 15 minutes on 2026-06-09.

New rule:

- every pass must close proof, start next work, record a blocker, or request a real Luke decision

## Protected Boundary

This plan does not approve:

- business runtime changes
- Windows Task Scheduler edits
- process kills
- worker restarts
- Amazon login/security changes
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon actions
- deletion, movement, compression, purge, archive apply, or cleanup apply

## Definition Of Working Properly

SellerOne 2.1 is working properly when:

- Rep Chat stays clean and Luke-facing
- Operations is the only Shift Manager
- Workers and Reviewers are one-job threads
- every active job has a visible owner, stage, timestamp, and next action
- waiting-proof items are reviewed quickly
- minor format issues do not hide real pass/fail status
- business runtime remains separate from control-desk stabilisation
- Luke is only interrupted for real decisions

## Recommended Next Move

continue with `SO21-QUEUE-MOVEMENT-BOARD`, then `SO21-THREAD-ROLE-HYGIENE`, then `SO21-PROOF-CLOSURE-RULES`
