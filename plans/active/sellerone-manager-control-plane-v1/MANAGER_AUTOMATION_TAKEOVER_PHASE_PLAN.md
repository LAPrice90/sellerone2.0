# SellerOne Manager Automation Takeover Phase Plan

## Purpose
This plan defines how SellerOne moves from chat-managed technical work to a manager-controlled maintenance system.

Plain English:
- The UI is where Luke views business data and makes business decisions.
- The manager is the control desk for maintenance, proof, repairs, and future extensions.
- Worker chats or automations do the technical work only from manager-approved packets.
- Luke should only be interrupted for protected actions or real business judgement.

## Current Baseline - 2026-05-31
- Main manager front door exists.
- Combined MOT exists for A, B, E, H, F, and O.
- `sellerone_manager/current_state.json` is the front door.
- Current overall state is warning-level, not failure-level.
- Active MOT fails: `0`.
- Luke decisions needed: `0`.
- A is calm.
- F is calm.
- O is calm as a mid-build manager view.
- B has warning-level proof gaps.
- E has warning-level ROI coverage gaps.
- H has warning-level readiness/storage/old-health context, but no active H MOT failure.
- Next approved Codex task:
  - `MGR_B_repair_b_refund_fee_shipping_roi_api_proof`

## Takeover Definition
Manager automation takeover is complete when the manager can do all of these without Luke supervising technical detail:

- Run independent MOT checks for every core flow.
- Keep one combined truth board.
- Classify every issue as proved, warning, not_started, not_verified, active approved task, parked, or real Luke decision.
- Create manager-approved packets with exact boundaries.
- Let Codex or worker chats claim safe packets without asking Luke again.
- Retest repairs through MOT or the named proof path.
- Mark work proved only from evidence.
- Keep protected actions blocked until Luke decides.
- Keep routine noise out of chat.
- Keep durable records so a new thread does not need the story explained again.

## Protected Actions
These always stop for Luke unless a separate approved proof packet explicitly allows the action and names the restore proof:

- price changes
- queue edits
- Google Sheets writes
- publishing
- local DB alignment or data correction
- output deletion
- worker restart
- live worker run without an approved proof window
- scheduler ownership change without restore proof
- business judgement
- scope widening beyond the approved packet

## Phase 1 - Control Desk Stability

### Aim
Make the manager front door reliable and simple.

### Work
- Keep `current_state.json` as the single front door.
- Keep `mot_rollup_latest.md` as the combined evidence board.
- Keep `approved_task_packets.csv` as the worker handoff list.
- Keep packet identity simple:
  - explicit `Approved Check`
  - allowed files
  - forbidden actions
  - proof path
  - rollback path
  - stop condition
- Avoid turning every warning into a big repair package.

### Expected End State
- The manager can answer:
  - what is calm
  - what is warning-only
  - what is an active Codex task
  - what is parked
  - what needs Luke
- New chats do not need Luke to explain manager-vs-worker roles again.

### Proof
- `python -m sellerone_manager.app --what-next`
- `python -m sellerone_manager.app --refresh-approved-tasks`
- `python -m pytest tests\manager -q`

### Done When
- `what-next` shows one clear next safe task when one exists.
- No duplicate packet identity mistakes.
- No raw warnings are treated as Luke work.

## Phase 2 - B Money Truth Proof

### Aim
Make B refund, fee, shipping, and ROI evidence safe for downstream E and O logic.

### Work
- Claim:
  - `MGR_B_repair_b_refund_fee_shipping_roi_api_proof`
- Add or confirm manager/MOT labels for:
  - refund API proof
  - fee API proof
  - shipping API proof
  - ROI confidence
- Keep Sellerboard as outside comparison only.
- Keep unknown money evidence labelled as `not_yet_proven`.

### Expected End State
- B still has no active FAIL.
- B can say which money facts are:
  - `api_proved`
  - `sellerboard_bridge_only`
  - `not_yet_proven`
- E and O can later avoid treating bridge-only values as clean ROI.

### Not Allowed
- No B run or restart.
- No data correction.
- No DB alignment.
- No Sheets.
- No output deletion.
- No Sellerboard values as final ROI truth.

### Proof
- `python -m sellerone_manager.app --hourly-mot --mot-flow B`
- focused B manager tests under `tests/manager/`

### Done When
- B warning is either cleared by API proof or remains warning-labelled with exact missing proof.
- Manager packet is marked `fixed_needs_retest` or `proved` only from evidence.

## Phase 3 - E Confidence And ROI Consumption Safety

### Aim
Make E safe to use while ROI proof is incomplete.

### Work
- Ensure E separates:
  - velocity-only evidence
  - clean ROI evidence
  - provisional truth
  - missing profit proof
  - reorder-ready rows
- Confirm E does not treat B bridge-only values as clean ROI.
- Keep E warning if ROI coverage is incomplete.

### Expected End State
- E can be trusted from the outside.
- E can say:
  - which SKUs have clean profit proof
  - which SKUs only have velocity
  - which SKUs are not business-ready for restocking

### Not Allowed
- No fake ROI fill.
- No hidden downstream masking.
- No business reorder decision.

### Proof
- `python -m sellerone_manager.app --hourly-mot --mot-flow E`
- E confidence output tests.
- E coverage summary exists and is current after an E-owned proof run.

### Done When
- E MOT warning is either cleared by proof or remains a clear confidence warning.
- O can later read E safely without guessing.

## Phase 4 - H High-Risk Control

### Aim
Keep H controlled before giving it broad autonomy.

### Work
- Keep H independent MOT current.
- Keep scheduler/finalizer/publish truth separate.
- Keep old health rows as clues only.
- Package H issues by root cause, not by every noisy symptom.
- Continue only from approved H packets.

### Expected End State
- H has no active MOT failure.
- H warnings are understood and parked or labelled.
- H repair work never starts from raw repricer chaos.

### Not Allowed
- No price changes.
- No publishing by Codex.
- No queue edits.
- No scheduler pause/resume without controller proof.
- No broad H autonomy.

### Proof
- `python -m sellerone_manager.app --hourly-mot --mot-flow H`
- terminal state proof
- publish status proof
- scheduler ownership proof if a controlled pause is used

### Done When
- H can be watched by the manager without chat panic.
- Any future H repair begins from a bounded packet.

## Phase 5 - F Scanner And Source-Proof Registration

### Aim
Keep F quiet when it is running and useful when it is stuck.

### Work
- Keep F source proof checks current:
  - email source proof
  - URL source proof
  - source intake chain
  - queue recommendation explanation
- Keep F scanner state classified as:
  - running
  - stale
  - stuck
  - login required
  - blocked
  - parked
- Do not expose raw scanner chaos to Luke.

### Expected End State
- F either runs normally or creates one clean manager task.
- F login issues follow the F061 script-owned browser path.
- F queue state is never edited from the manager.

### Not Allowed
- No F061 queue edit.
- No scanner run from manager unless an approved proof window exists.
- No separate login-browser workaround unless Luke asks.

### Proof
- `python -m sellerone_manager.app --hourly-mot --mot-flow F`
- F manager snapshot reports.

### Done When
- F warnings are either cleared, parked, or converted to one bounded source-proof task.

## Phase 6 - O Mid-Build Manager Coverage

### Aim
Make O visible without pretending it is finished.

### Work
- Keep O labelled by build stage:
  - foundation
  - bridge
  - proof-only
  - not_started
  - not_verified
  - unsafe blocker
- Separate UI/data-viewing work from manager maintenance work.
- Ensure O never makes business decisions automatically.

### Expected End State
- O can be monitored as a build project.
- Missing future features are not treated as live failures.
- O readiness is honest.

### Not Allowed
- No purchase commitment.
- No receiving decision.
- No send-to-Amazon action.
- No business judgement.

### Proof
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`
- O expectation reconciliation.
- O proof files checked for freshness and stage.

### Done When
- O manager can clearly say what is built, what is bridge-only, and what is not started.

## Phase 7 - Retest And Lifecycle Automation

### Aim
Make the repair loop work without Luke tracking task IDs.

### Work
- Standardise task states:
  - `approved`
  - `in_progress`
  - `fixed_needs_retest`
  - `retest_failed`
  - `proved`
  - `parked`
  - `blocked_needs_luke`
- Make MOT retest queues reliable.
- Make stale packet rows close or park cleanly.
- Ensure packets do not stay active after the MOT worklist clears.

### Expected End State
- A worker can claim a task, fix inside the boundary, request retest, and leave proof.
- The manager can mark proved only from MOT/proof evidence.

### Not Allowed
- No worker marking itself complete without independent proof.
- No hand-editing MOT outputs.
- No chat-only follow-up memory.

### Proof
- manager packet lifecycle tests
- retest queue tests
- `python -m sellerone_manager.app --refresh-approved-tasks`
- `python -m sellerone_manager.app --claim-approved-task`

### Done When
- The manager can run the loop:
  - issue found
  - packet approved
  - task claimed
  - safe fix done
  - retest run
  - proved or reopened

## Phase 8 - Scheduled Manager Automation

### Aim
Let the manager keep itself current while Luke is away.

### Work
- Keep hourly MOT running for all supported flows.
- Keep manager refresh scheduled.
- Keep due checks durable.
- Keep worker automation optional and packet-bound.
- Add watchdog checks for:
  - MOT command result
  - manager current state freshness
  - approved task packet freshness
  - automation failures

### Expected End State
- The control desk keeps current without Luke opening every chat.
- Routine checks do not interrupt Luke.
- New blockers become packets or decisions.

### Not Allowed
- No autonomous protected actions.
- No hidden business decisions.
- No worker cycles as a workaround for missing proof.

### Proof
- Windows task or Codex automation exits with result `0`.
- `mot_history.jsonl` updates on schedule.
- `current_state.json` updates after MOT.

### Done When
- Manager board remains fresh across a full day without Luke babysitting it.

## Phase 9 - Worker Automation Bridge

### Aim
Let Codex workers do safe technical work automatically from approved packets.

### Work
- Worker starts by reading:
  - `WORKER_CHAT.md`
  - approved packet
  - current manager state
- Worker claims the next approved packet.
- Worker stays inside allowed files.
- Worker updates state through the manager commands.
- Worker stops only at protected boundaries.

### Expected End State
- Luke does not manage technical task IDs.
- Worker chats do not freestyle repairs.
- Safe code/proof work continues without repeated approval.

### Not Allowed
- No sub-agent or worker work outside approved packet scope.
- No live flow run unless the packet already approves the proof window.

### Proof
- A worker can complete at least one packet end-to-end:
  - claim
  - edit or proof
  - tests
  - MOT retest
  - manager state update

### Done When
- The manager, not Luke, chooses the next safe technical task.

## Phase 10 - Quiet Operator Contract

### Aim
Make the manager feel like a human control desk, not another technical chat.

### Work
- Keep replies short.
- Lead with whether a decision is needed.
- Hide routine raw logs and paths.
- Explain only the business maintenance meaning unless Luke asks for detail.
- Keep repeated warnings in MOT, not in every chat.

### Expected End State
- Luke sees:
  - what matters
  - what Codex owns
  - what would interrupt him
- Luke does not see:
  - raw test logs
  - repeated unchanged warnings
  - task ID clutter
  - random repair branches

### Proof
- Manager front-door text stays plain English.
- Current state only asks Luke when `luke_action_required=true`.

### Done When
- Luke can open the main manager thread and understand the business maintenance state in under one minute.

## Phase 11 - Final Takeover Acceptance

### Aim
Declare manager automation takeover complete.

### Required Evidence
- A/B/E/H/F/O are all in the combined MOT.
- Active fail count is `0`, or every fail has an active approved packet or real Luke decision.
- Every warning is either:
  - accepted watch item
  - not_verified
  - parked
  - planned improvement
  - waiting for a proof window
- No cycle says complete without proof.
- Current state is fresh.
- Hourly MOT is fresh.
- Approved task packets are fresh.
- Retest queue is fresh.
- Worker instructions are durable.
- Manager instructions are durable.

### Final Automation Expectations
- Manager checks every flow on schedule.
- Manager creates safe packets.
- Workers claim safe packets.
- MOT retests repairs.
- Manager marks proved or blocked.
- Luke is interrupted only for protected actions or business judgement.

### Final Proof Commands
- `python -m pytest tests\manager -q`
- `python -m sellerone_manager.app --hourly-mot --mot-flow all`
- `python -m sellerone_manager.app --refresh-approved-tasks`
- `python -m sellerone_manager.app --what-next`

### Takeover Complete When
- `current_state.json` gives one truthful answer across A/B/E/H/F/O.
- `mot_rollup_latest.md` has no hidden failures.
- `approved_task_packets.csv` has only active safe work, proved work, parked work, or blocked Luke decisions.
- Luke has no routine technical checklist to manage.

## Current Execution Position - 2026-05-31T12:30Z
- Phase 2 is proved: B money-proof labels are explicit and B remains warning-labelled where API proof is incomplete.
- Phase 3 is proved: E now reads B money-proof labels as an outside safety dependency and stays warning-labelled when B money is bridge-only or not yet proven.
- Phase 4 is controlled: H has no active MOT failure, but broad H autonomy stays blocked and high-risk lanes stay parked.
- Phase 5 is parked: F scanner proof is OK, and stale source-proof work is parked under a bounded F package.
- Phase 6 is controlled: O is labelled as mid-build and not treated as a finished live cycle.
- Phase 7-10 are under final acceptance proof: lifecycle, scheduled manager automation, worker bridge rules, and quiet operator contract are being verified.

## Immediate Next Phase
Continue with Phase 11 final takeover acceptance:
- run the final manager tests
- run combined MOT for all flows
- refresh approved task packets
- read the manager front door
- accept only if every item is proved, warning-labelled, parked, or a real Luke decision
