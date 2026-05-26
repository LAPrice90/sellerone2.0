# Morning MOT Checklist

## Purpose
This file defines the standard morning checkover for SellerOne.

When the user asks for a `morning checklist` or `morning MOT`, Codex should use this file as the preset operating pattern.

The morning MOT must answer five things in plain English:
- Are A, B, E, H, and the F price-list manager running as normal?
- Did any system break, stall, or fail overnight?
- Is the data current enough for normal operation?
- Are there gaps between expectation and live truth?
- What is the correct fix path if anything is wrong?

The morning MOT is also the default place to review routine health noise.
Known unchanged WARNs and already-understood FAILs should be handled here, not repeated in unrelated chats.

This checklist is not only for finding problems. It must also tell Codex how to turn the findings into either:
- one large hometime-mode fix package, or
- separate narrow tickets.

## Trigger Phrases
Treat the following user requests as the same preset:
- `morning checklist`
- `morning MOT`
- `morning checkover`
- `check overnight status`
- `run the morning system check`

## Operational Modes
The morning MOT must support three distinct modes.

### 1. Diagnosis only
Use this when the user only wants status.

Codex should:
- inspect live state
- report blockers, gaps, and missed expectations
- stop at task recommendation

### 2. Task design
Use this when the user wants task packaging but not implementation yet.

Codex should:
- inspect live state
- classify blockers
- draft either a hometime package or individual tickets
- define the exact testing and proof standard for each ticket

### 3. Fix execution
Use this when the user wants Codex to actually repair the system.

Codex should:
- inspect live state
- sort findings into `fix now`, `monitor in MOT only`, `stale evidence only`, or `needs user decision`
- stop affected loops if needed
- implement clear root-cause fixes without routine checkpoint prompts
- test each fix
- prove success against the agreed clean-run target
- only then call it done

Fix execution is quiet by default.
That means:
- one opening summary
- then blocker-by-blocker fixing and testing without routine chat interruption
- then one milestone summary when a phase or the whole MOT package is complete
- only interrupt if a real decision, contradiction, or safety boundary appears

## Quiet MOT Rules
The morning MOT should reduce operator noise, not move it to a new prompt.

During a morning MOT:
- do not repeat every known WARN line one by one if they are already understood
- do not interrupt after each routine check
- do not stop between clear blockers just to ask whether to continue
- do not treat stale evidence as a fresh blocker without checking live truth first

Interrupt the user during a morning MOT only when:
- a blocker needs approval
- the next safe action would cross a repo boundary
- evidence is contradictory and root cause is no longer clear
- the recommended package size changes materially
- the fix package is complete and proof is ready to report

## Mandatory Rules
- Use live artifacts and latest completed run evidence first.
- Start the executable system-wide MOT from `run_morning_mot_system.bat`, not from a chat-only checklist.
- Check durable follow-ups from `project_control/DUE_CHECK_REGISTER.csv` before ending the MOT.
- Refresh or read `out/cycle_alerts/due_check_register_status.csv` so due checks are visible as MOT evidence.
- Always run the executable F price-list post-restart check after the overnight restart window and after the morning A evidence is available: `python scripts/tools/f_price_list_post_restart_mot.py`.
- If a due check is due or overdue, Codex must tell the user the result or classify it into `fix now`, `monitor in MOT only`, `stale evidence only`, or `needs user decision`.
- Do not run ad hoc `A` scripts unless the user explicitly asks, or explicitly asks for morning-MOT fix execution that includes proof.
- Do not change Google Sheets unless the user explicitly asks.
- Do not mask downstream outputs to make them look healthy.
- Fix root cause at the earliest broken stage.
- Keep one-off scripts out of daily loops.
- Separate stale checklist evidence from live runtime truth.
- If code changed after the latest health snapshot, mark it as pending verification, not verified.

## System Order
Check systems in dependency order:
1. `A`
2. `E`
3. `B`
4. `H`
5. `F price-list manager post-restart check`

Reason:
- `A` is the daily upstream data and health layer.
- `E` depends on fresh upstream data and informs operational confidence.
- `B` is the daytime operational loop.
- `H` depends on A/B/E freshness and is the most runtime-sensitive loop.
- `F` is checked as a post-restart operational add-on because price-list queue failures most often come from ownership, browser-login, or restart-drain state rather than A data generation.

## Executable MOT Schedule
The MOT has two scheduler-owned passes so stale owners are repaired before the operator day starts:

| Scheduled task | Local time | Command | Purpose |
|---|---:|---|---|
| `AMZ Morning MOT Post Restart` | 02:35 | `run_morning_mot_system.bat --phase post_restart --repair --proof-wait-seconds 30` | Catch and restart B/H/F owners after the controlled restart window. |
| `AMZ Morning MOT Post A` | 06:30 | `run_morning_mot_system.bat --phase post_a --repair --proof-wait-seconds 30` | Check A/E/B/H/F after the daily A run should have completed. |

The separate Codex automation `O net-fee restock MOT check` runs at 06:45 local through 2026-06-02, after the 06:30 post-A MOT pass. It must not be scheduled at 09:00 because that can miss overnight stale state until office time.

The runner writes:
- `out/cycle_alerts/morning_mot_latest.md`
- `out/cycle_alerts/morning_mot_system_check.csv`
- `out/cycle_alerts/morning_mot_system_check.json`
- `out/cycle_alerts/morning_mot_repair_actions.json`

Use `out/cycle_alerts/morning_mot_latest.md` as the single operator-facing MOT file. The CSV and JSON files remain machine-readable proof behind that one summary.

Repair boundary:
- B repair starts `AMZ Orders`.
- H repair starts `AMZ H Cycle`.
- F repair runs the F supervisor once.
- E repair starts `scripts/cycles/run_E_cycle.py` only after current-day A evidence exists.
- A repair is visible but guarded. The runner will not start A unless launched with `--allow-a-repair`.

Restart hardening:
- The controlled restart must not let stale H paperwork alone block the overnight reboot. If the only blockers are stale H markers such as `H_RUN_IN_PROGRESS_NOT_FINALIZED`, `H_LAUNCHER_HEARTBEAT_STALE`, `H_LAUNCHER_PID_STALE`, or `H_CYCLE_STALE_LOCK_PRESENT`, the restart controller may approve the reboot during the controlled restart window.
- `run_controlled_restart_controller.bat` enables the home-time forced reboot fallback by default. This is the final safety net if the normal drain/approval path still cannot reach approval while home-time mode is active.
- The reason is simple: live locks protect active work, but stale markers must not keep the PC running for days.

## Current Monday MOT Priority

As of the weekend check on 2026-05-02, the main Monday morning MOT task is:

- B cycle `token_shortages_by_sku=6`
- Evidence: `out/cycle_alerts/checklist_B.csv`
- Current classification: known issue, `fix now` during Monday MOT unless newer B evidence shows it has already cleared
- Safe proof rule: do not overlap the live B owner. If manual proof is needed, use B maintenance handoff and a boundary-safe `B_RUN_ONCE=1` proof cycle.

## Source Of Truth
Use these files first before proposing reruns.

| System | Primary run evidence | Health evidence | Runtime and ownership evidence |
|---|---|---|---|
| `A` | `out/manifests/A/<date>/*.json` | `out/cycle_alerts/checklist_A_split.csv`, `out/system_health_checklist.csv` | `out/systems/A/live/run_cycle.lock` if present, `out/locks/maintenance.*` when handoff is relevant |
| `E` | `out/manifests/E/<date>/*.json`, `out/systems/E/live/e_run_log.jsonl` | `out/cycle_alerts/checklist_E_split.csv`, `out/system_health_checklist.csv` | Usually manifest and log freshness are enough |
| `B` | `out/manifests/B/<date>/B_*.json`, `out/systems/B/live/B_cycle.log` | `out/cycle_alerts/checklist_B_split.csv`, `out/system_health_checklist.csv` | `out/systems/B/live/B_cycle.lock`, maintenance markers, live process state |
| `H` | `out/manifests/H/<date>/H_*.json`, `out/systems/H/live/H_cycle.log` | `out/cycle_alerts/checklist_H.csv`, `out/system_health_checklist.csv` | `out/systems/H/live/H_runtime_status.json`, `out/systems/H/live/H_run_in_progress.txt`, `out/systems/H/live/H_pricing_cycle.lock`, `out/H_pricing_cycle.lock`, launcher heartbeat |
| `F price-list manager` | `out/systems/F/price_list_manager/live/live_cycle_status.csv`, `out/systems/F/price_list_manager/live/live_cycle_events.csv` | `out/cycle_alerts/f_price_list_post_restart_mot.csv`, `out/systems/F/price_list_manager/live/live_cycle_health.csv`, due check `F_PRICE_LIST_POST_RESTART_MOT_DAILY` | `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt`, `out/systems/F/price_list_manager/live/live_cycle.lock`, `out/systems/F/price_list_manager/live/F_restart_drain.ready`, `out/systems/F/price_list_manager/live/f061_login_mode.requested`, `out/systems/F/price_list_manager/live/f061_child_status.txt`, `out/locks/restart_control/restart_controller.latest.json` |

## Morning MOT Procedure

### 1. Global Baseline
Start with a whole-system view before drilling into one loop.

Codex should collect:
- current local and UTC time
- latest `out/system_health_checklist.csv` modified time
- current FAIL and WARN counts from the global checklist
- any active health alert snooze from `out/locks/health_alert_snooze.json`
- live process ownership for `A`, `B`, `E`, and `H` if those runtimes are expected to be active
- latest controlled restart result from `out/locks/restart_control/restart_controller.latest.json`
- executable F price-list post-restart result from `out/cycle_alerts/f_price_list_post_restart_mot.csv`
- due operational checks from `project_control/DUE_CHECK_REGISTER.csv`
- latest generated due-check status from `out/cycle_alerts/due_check_register_status.csv`

Codex should classify the whole estate first:
- `normal` = no active hard blocker seen yet
- `degraded` = warnings or staleness exist, but core runtime still operates
- `blocked` = one or more hard blockers stop normal operation

Then Codex should classify each issue:
- `fix now` = root cause is clear, safe fix path exists, and proof can be run without a user decision
- `monitor in MOT only` = non-blocking, understood, and not worth interrupting the user about outside the MOT
- `stale evidence only` = checklist or aggregate is behind newer live truth
- `needs user decision` = approval, scope, or business choice is required

Due checks are not chat reminders. They must be handled from `project_control/DUE_CHECK_REGISTER.csv` and reflected in `out/cycle_alerts/due_check_register_status.csv`.
For each due check, Codex should either:
- mark the task complete with the artifact and success evidence
- leave it open with the next exact artifact and condition
- promote it to `fix now` or `needs user decision` if the evidence is bad

### 2. A Cycle Check
Morning expectation for `A`:
- the latest completed `A` manifest is from the current operational day
- the run is not partial unless there is a known accepted reason
- `A015` current-cycle health evidence exists
- no active `A` scoped FAIL

Questions Codex must answer:
- Did `A` complete today?
- Was the manifest complete or partial?
- Did `A015` write current-cycle evidence?
- Did `A` leave fresh enough upstream data for `E` and `H`?
- Was `B` maintenance handoff respected if relevant?

Minimum evidence:
- latest file under `out/manifests/A`
- `out/cycle_alerts/checklist_A_split.csv`
- `out/system_health_checklist.csv`

Hard-block examples:
- no current-day `A` completion
- latest `A` manifest is partial without accepted explanation
- `A015` missing current-cycle evidence
- active `A` FAIL

Soft-block examples:
- accepted WARN only
- stale aggregate checklist but newer live A manifest exists
- manual run gap explained by schedule

### 3. E Cycle Check
Morning expectation for `E`:
- the latest `E` run completed on expected daily cadence
- `E` outputs are fresh enough for planning and reporting
- no active `E` scoped FAIL

Questions Codex must answer:
- Did `E` run after the latest valid upstream data was ready?
- Is the latest `E` manifest current enough for the day?
- Is `out/systems/E/live/e_run_log.jsonl` current?
- Are `E` health checks clean enough to trust analytics?

Minimum evidence:
- latest file under `out/manifests/E`
- `out/systems/E/live/e_run_log.jsonl`
- `out/cycle_alerts/checklist_E_split.csv`

Hard-block examples:
- no expected daily `E` run
- missing required `E` manifest or log evidence
- active `E` FAIL

Soft-block examples:
- older `E` run but still within accepted daily cadence
- WARN-only analytics degradation that does not block operation

### 4. B Cycle Check
Morning expectation for `B`:
- `B` is either actively looping or intentionally paused
- latest `B` cycles continue on cadence with no duplicate owner
- token and order-side outputs are updating
- no dead-owner `B` lock is stranding the loop

Questions Codex must answer:
- Is `B` running right now if it should be?
- If not running, did it stop intentionally or break?
- Is the latest `B` manifest current and continuous?
- Are token outputs and live order-side outputs updating?
- Are maintenance markers stuck?

Minimum evidence:
- latest files under `out/manifests/B`
- `out/systems/B/live/B_cycle.log`
- `out/systems/B/live/B_cycle.lock`
- `out/cycle_alerts/checklist_B_split.csv`

Hard-block examples:
- `B` should be live but no healthy owner is running
- stale or dead-owner `B_cycle.lock`
- active `B` FAIL
- repeated crash/restart loop

Soft-block examples:
- nonfatal collector warnings
- brief pause at expected maintenance boundary
- checklist WARN with current live loop still healthy

### 5. H Cycle Check
Morning expectation for `H`:
- `H` background loop restarts normally when it is supposed to
- latest run finalizes truthfully
- snapshot, pilot, publish, and cleanup evidence agree
- no stale owner lock or stranded in-progress marker remains

Questions Codex must answer:
- Is `H` running right now if it is supposed to be live?
- Did it restart after upstream dependency completion when expected?
- Did the latest completed run finalize truthfully?
- Is `H_runtime_status.json` current?
- Are `H_run_in_progress.txt` and lock files clean?
- Did the latest run reach publish, become publish-reachable, or fail closed for a truthful reason?

Minimum evidence:
- latest files under `out/manifests/H`
- `out/systems/H/live/H_cycle.log`
- `out/systems/H/live/H_runtime_status.json`
- `out/systems/H/live/H_pricing_cycle.lock`
- `out/H_pricing_cycle.lock`
- `out/cycle_alerts/checklist_H.csv`

Hard-block examples:
- `H` should be live but no healthy owner is running
- dead-owner lock or stranded `H_run_in_progress.txt`
- latest run not terminalized truthfully
- active `H` FAIL
- repeated overnight parent/child restart failure

Soft-block examples:
- clean fail-closed outcome with full evidence
- non-blocking WARN with clear reason
- stale aggregate label while newer live truth shows health

Notes for H evidence:
- `out/cycle_alerts/checklist_H.csv` is the H flow-owned gate truth.
- `out/cycle_alerts/checklist_H_split.csv` and `out/health_status_H.csv` are observability-only and may be stale relative to live H runtime evidence.

### 6. F Price-List Post-Restart Check
Morning expectation for `F`:
- the price-list supervisor is fresh after the overnight restart
- if F has active pending rows, either the FPM130 manager is running or the supervisor has restarted it recently
- `F_restart_drain.ready` is absent unless a real maintenance request is currently active
- if `f061_login_mode.requested` is active, a normal script-owned F061 child is handling it or the MOT classifies it immediately
- no old restart-drain marker is silently blocking the price-list queue

Questions Codex must answer:
- Did the latest restart complete or skip?
- Did F resume after the restart window?
- Is the F supervisor state current and not `paused|reason=drain_ready` unless a matching maintenance request still exists?
- Is `F_restart_drain.ready` orphaned?
- If login mode is requested, did `live_cycle_events.csv` show `login_mode_child_started` after that request?
- Did this problem start after the restart or after A? Compare the restart finish time, the F stale/drain evidence time, and the latest A manifest/checklist time.

Minimum evidence:
- `out/cycle_alerts/f_price_list_post_restart_mot.csv`
- `out/locks/restart_control/restart_controller.latest.json`
- `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt`
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- `out/locks/maintenance.requested`
- `out/systems/F/price_list_manager/live/f061_visible_login.requested`
- `out/systems/F/price_list_manager/live/f061_login_mode.requested`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- latest `out/manifests/A/<date>/*.json`

Hard-block examples:
- `F_restart_drain.ready` exists, no maintenance request exists, and no F owner is running
- supervisor state is stale or stuck on `paused|reason=drain_ready`
- login mode is requested but no `login_mode_child_started` event appears after the request
- live active rows exist but neither FPM130 nor the supervisor is moving them

Soft-block examples:
- F is intentionally in visible login hold and the hold window has not expired
- A checklist is stale but newer F runtime truth shows the queue is moving
- a known login-backtrack row is parked and visible in due-check tracking

Classification rule:
- If F evidence became bad before the A manifest/checklist time, classify the cause as `post-restart or F-owner issue`, not `A caused it`.
- If F was healthy after restart but became bad immediately after A touched shared maintenance or handoff markers, classify it as `post-A handoff issue`.
- If A only reported the bad state later, classify A as `detector`, not `cause`.

### 7. Cross-System Gap Check
After the five system checks, Codex must compare them together.

Codex must explicitly look for:
- `A` completed, but `E` did not follow as expected
- `A` completed, but `H` never resumed or restarted
- `B` stopped while `H` stayed live on stale inputs
- `E` is stale relative to fresh `A`
- `H` is publishing from data older than expected upstream refresh
- `F` did not resume after the restart window
- `F` has an active login request but no script-owned login child
- a checklist says WARN or FAIL but live manifests/logs show the state has already moved on

Codex must label each mismatch as one of:
- `real blocker`
- `stale evidence only`
- `runtime healthy but needs verification`
- `shared dependency issue`

## Expectation Standard
The morning MOT must compare live truth to expectations, not just list files.

### Daily systems
Use this standard for `A` and `E`:
- expected to have completed on the current operational day
- manifests and health evidence must line up
- partial run counts as missed expectation unless explicitly accepted

### Loop systems
Use this standard for `B` and `H`:
- expected to be either actively looping or intentionally paused
- no dead-owner lock, duplicate owner, or stranded state
- latest completed run must be terminalized truthfully
- if background mode is intended, at least one restart boundary should be evidenced when relevant

## Morning MOT Output Format
When Codex answers a morning MOT request, the reply should use this shape:

1. `Executive summary`
- one short paragraph stating whether the estate is normal, degraded, or blocked

2. `Per-system status`
- `A`
- `E`
- `B`
- `H`
- `F price-list manager`

Each system line should answer:
- running normally or not
- latest evidence time
- expectations met or missed
- main blocker or gap if any

3. `Cross-system gaps`
- explain dependency breaks or stale-data relationships

4. `What matters now`
- identify the first true blocker
- separate real blocker from stale evidence
- show which items are `fix now` versus `monitor in MOT only`

5. `Recommended next action`
- no action
- one narrow inspection
- one narrow implementation
- one large hometime fix package
- quiet fix execution now

6. `Testing and proof plan`
- what must be tested before any blocker can be called fixed
- what evidence files or run IDs will prove success
- whether proof needs `3`, `5`, or `10` clean runs

## Fix Escalation Rules
If the morning MOT finds problems, Codex must decide how to package the work.

### Use individual tasks when:
- there is one clear blocker
- the blocker is narrow
- the fix can be proven with scoped testing
- unrelated systems do not need to be frozen together
- the user asked for diagnosis or task design only

### Use one large hometime-mode package when:
- multiple blockers interact
- loop ownership, scheduler, restart, or overnight stability is involved
- background systems need to be stopped and held while fixes are made
- success must be proven through repeated clean runs before restart

### Use quiet autofix inside the MOT when:
- the user asked for fix execution
- the blocker is clear and root-cause-confirmed
- the change stays within approved boundaries
- the proof path is already known
- no extra user decision is needed between steps

## Task Generator Rules
When the morning MOT finds real blockers, Codex must convert them into actionable work, not just diagnosis.

### For a single large hometime package, Codex must define:
- systems in scope
- loops to stop before editing
- exact blocker list in root-cause order
- testing sequence after each change
- clean-run proof target
- restart criteria for background mode

### For individual tasks, Codex must define for each blocker:
- `Inspection` goal and evidence sources
- `Implementation` scope and non-goals
- `Validation` proof run and expected outcome
- success condition for that blocker

### For quiet autofix, Codex must define internally before coding:
- blocker order in root-cause order
- exact files or systems in scope
- proof step after each blocker
- interruption threshold for user contact

## Clean Run Target Rules
If a fix package is needed, Codex must propose a clean-run target.

Use this default scale:
- `3 clean runs` = small isolated code fix with low runtime risk
- `5 clean runs` = medium runtime or handoff fix
- `10 clean runs` = overnight stability issue, background restart issue, ownership/finalization issue, or multi-system fix

If the user does not specify a target, Codex should recommend one based on severity:
- recommend `3` for a narrow data or logic defect
- recommend `5` for a loop or dependency handoff defect
- recommend `10` for a background, scheduler, ownership, or repeated overnight failure

## Mandatory Testing Rules
If the user asks for a fix, testing is not optional.

Codex must define and run the narrowest truthful test that proves the changed path.

Minimum rule set:
- no code change may be called fixed without a relevant test or live proof run
- if the blocker is runtime or ownership related, proof must use real runtime evidence
- if the blocker affects loop restart or overnight behavior, repeated clean runs are required
- if a next-cycle verifier is required instead of an ad hoc run, Codex must say that explicitly and must not call the issue verified early
- if a safe forced proof window exists, use it instead of waiting for the next scheduled cycle

### System-specific proof defaults
- `A` fix: next scheduled `A` evidence or an explicitly user-approved `A` run, or a morning-MOT fix-execution proof run, plus current-cycle `A015` evidence
- `E` fix: one successful `E` run with fresh manifest and split checklist
- `B` fix: one successful `B` cycle for narrow fixes, or repeated clean cycles for loop stability issues
- `H` fix: one successful controlled run for narrow fixes, plus repeated clean runs before background restart for stability issues
- `F` post-restart fix: supervisor one-shot or scheduler-owned proof showing fresh `fpm_live_supervisor_state.txt`, no orphan `F_restart_drain.ready`, and FPM130/F061 ownership restored when rows are pending
- cross-system handoff fix: proof must include both sides of the boundary, not just the upstream side

## Mandatory Proof Bundle
Every completed fix package must produce a proof bundle in the final report.

The proof bundle must include:
- exact run ID or run IDs used for proof
- relevant log lines
- relevant manifest, contract, or marker files
- health evidence time
- whether the target loop is running now
- whether the requested clean-run target was met

If any one of those is missing, the issue is not yet finished.

## Success Standard For A Fix Package
Codex must define success before starting implementation.

The success standard must include:
- exact blocker being fixed
- affected systems
- what will be tested
- required proof artifacts
- clean-run target
- whether background loops will stay disabled until proof is complete

Minimum success language:
- blocker removed at root cause
- no synthetic evidence
- fail-closed behavior preserved
- required artifacts and health evidence present
- clean-run target achieved
- only then restart background mode if background mode is in scope

## No Sign-Off Rules
Codex must not say `done`, `finished`, or `SIGN OUT` when any of the following is true:
- the user asked for a fix and the required testing has not happened
- the target runtime is still down
- the clean-run target has not been met
- the latest available health evidence predates the code change and no live proof run exists
- the final report does not include proof artifacts

If proof is incomplete, Codex must say one of:
- `implemented, pending verification`
- `partially fixed, more proof required`
- `blocked by missing runtime window`

## Hometime-Mode Execution Pattern
If the user chooses one large fix package, Codex should use this sequence:

1. Freeze affected loops safely
- stop only the runtimes that must be stopped
- respect B maintenance safety if A work is involved

2. Baseline the blocker
- capture live evidence before editing
- identify the first confirmed mismatch

3. Implement the smallest root-cause fix
- no downstream masking
- no unrelated refactor

4. Run scoped proof
- targeted test or controlled run for the changed path

5. Repeat until stable
- inspect
- change
- test
- re-check live artifacts

6. Prove clean runs
- run the agreed `3`, `5`, or `10` clean runs
- use real run evidence, not synthetic mocks, where runtime behavior is the issue

7. Re-enable background mode only after proof
- verify live ownership, loop restart, and cleanup

8. Perform final live recheck
- confirm the target loop is actually running now if it is meant to be live
- confirm there is no stale dead-owner lock
- confirm the latest proof run did not just pass in one-shot mode and then stop

## Individual Task Execution Pattern
If the user chooses separate tasks, Codex should package each blocker as:
- `Inspection` first when root cause is not confirmed
- `Implementation` once fix scope is narrow
- `Validation` once the change exists

Each task must include:
- goal
- exact scope
- non-goals
- required evidence
- done criteria

## Morning MOT Decision Prompt
In `Diagnosis only` or `Task design` mode, if blockers are found, Codex should end with a direct decision prompt in plain English:

- `I found <n> real blocker(s).`
- `Recommended mode: single hometime fix` or `Recommended mode: individual tasks`
- `Recommended clean-run target: 3 / 5 / 10`
- `If you want, I can now generate the exact fix task pack.`

In `Fix execution` mode, do not stop for this prompt.
Start the agreed quiet fix path unless a real decision point is hit.

## Preset User Requests
These are the standard ways the user can call this system.

### Morning status only
`Run the morning MOT and tell me what is running, what is stale, and whether expectations were met.`

### Morning status plus task design
`Run the morning MOT and draft the fix tasks.`

### One large hometime fix
`Run the morning MOT, then fix everything in hometime mode and prove 5 clean runs before restart.`

### Split task mode
`Run the morning MOT, then break the blockers into individual inspection and implementation tasks.`

### Full fix with proof
`Run the morning MOT, fix the blockers, test each fix, prove 5 clean runs, and do not sign off unless the loop is live again.`

### Quiet morning autofix
`Run the morning MOT in quiet fix mode. Sort the issues, fix the clear blockers, test them, prove them, and only interrupt me if you need a real decision.`

## Notes
- This checklist is a control document, not an auto-runner.
- It is meant to remove repeated prompt-writing and keep the morning review consistent.
- It should also keep routine health noise out of unrelated chats.
- If this file is extended later, keep it plain English and evidence-first.
