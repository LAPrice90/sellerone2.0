# Architecture

## Architectural Intent

The system is organized as flow-owned scripts that produce and consume operational artifacts under repo-controlled paths. Governance work in this repo is currently focused on making source ownership explicit and reducing duplicate truth layers.

## Confirmed Structural Constraints

- Flow-owned scripts are expected to gate on flow-scoped checks rather than unrelated global blockers.
- One-off scripts and daily loops are separate operating lanes and should not be mixed.
- Manual business inputs are a protected layer and should not be overwritten by blank or guessed data.
- Health, logs, and recovery artifacts are part of the architecture because the system depends on them for safe operation.

## Data Architecture Snapshot

- Some logical datasets exist in both legacy mirror paths under `out/` and canonical live paths under `out/systems/<owner>/live/`.
- `scripts/core/out_paths.py` provides compat path resolution for datasets that are being migrated from direct legacy reads to canonical live reads.
- `project_control/DATA_LINEAGE_REPORT.md` maps source readers and writers.
- `project_control/SOURCE_AUTHORITY_REPORT.md` classifies likely canonical, mirror, preview, cache, and deprecated-risk layers.
- `project_control/CANONICAL_ENFORCEMENT_PLAN.md` defines phased cleanup work for source enforcement.

## Known Canonical Direction

- B token live datasets are intended to be read through compat resolution with the canonical live location under `out/systems/B/live/`.
- H live compat-mapped datasets are being migrated toward canonical reads under `out/systems/H/live/`.
- Legacy `out/...` locations for compat-mapped datasets should be treated as mirrors or fallback paths where the compat model still allows them.

## Control-Layer Architecture

- `AGENTS.md` is the active agent-behavior authority.
- `WORK_LOG.md` is the append-only approved history and audit ledger.
- `project_control/` is the intended permanent project governance lane for purpose, architecture, decisions, state, queue, and guardrails.
- Investigative reports in `project_control/` act as supporting authority for later rewiring and ownership decisions.

## A Cycle Orchestration Model

- `scripts/cycles/run_A_all.py` is the A-cycle orchestrator.
- The current configured A run order is 13 sequential steps:
- `A001_run_listings_to_sheet.py`
- `process_stock_receipts_sheet.py`
- `A002_run_catalog_items_to_sheet.py`
- `A003_run_inventory_to_sheet.py`
- `A004_run_fees_to_sheet.py`
- `A010_apply_researching_delta.py`
- `A005_run_inventory_adjustments_report.py`
- `A016_refresh_phase1_daily_intel.py`
- `dedupe_product_db.py`
- `sync_product_db_to_main_sheet.py`
- `run_E_cycle.py`
- `A020_run_daily_finance.py`
- `A015_build_system_health_check.py`
- The orchestrator creates an in-memory manifest at cycle start, walks `RUN_ORDER` in-process, and appends one manifest step only after each child script returns or a skip/failure branch is taken.
- The current A orchestrator writes the manifest once in the `finally` block after the loop exits. It does not flush progress after each step.
- The current design assumes that full traversal happened if the process reached finalization. That assumption is unsafe because the finalizer does not verify how many configured steps were actually traversed.

## A Manifest Truth Model Today

- Step completion is currently inferred from the orchestrator control path, not from a separate execution ledger.
- For ordinary child scripts, `run_A_all.py` calls `subprocess.run(...)` and then appends a manifest step with:
- `rc=<child return code>`
- `outputs=<static list from STEP_ARTIFACTS>`
- `notes=elapsed=...`
- A step with `rc=0` currently means only that the child process returned zero to the parent.
- The manifest does not currently distinguish:
- step launched
- child process exited
- required outputs verified
- expected step skipped by policy
- traversal incomplete because the orchestrator itself stopped early
- The final manifest-level `health_summary` is added by `scripts/core/run_manifest.py::finalize_manifest(...)`, which only counts statuses in the checklist file passed to it. It does not verify that the checklist was produced by the current A run.

## Expected Outputs Declaration Vs Verification Today

- `run_A_all.py` declares expected outputs through the static `STEP_ARTIFACTS` dictionary.
- Those output paths are copied into the manifest as descriptive metadata.
- The current A orchestrator does not verify that those files exist, were rewritten during the current run, belong to the current run, or are internally valid before recording a step as successful.
- Because of that gap, the manifest can report `rc=0` for a step while the declared output is missing, stale, or left over from an older run.
- A015 is the only place where freshness is checked at all, and that check is narrow:
- for global health it compares the checklist file mtime before and after running A015
- for split health it compares `out/cycle_alerts/checklist_A_split.csv` mtime before and after running A015
- outside A015, most A outputs are declaration-only and not verification-backed.

## Health Artifact Freshness Today

- `run_A_all.py` uses `_run_a015_with_freshness(...)` to decide whether the checklist file was freshly written during the A015 call.
- Freshness is currently file-mtime-based only. There is no manifest-to-checklist run-id link, no cycle-start lower bound, and no proof that the checklist reflects the same A run that is being finalized.
- `scripts/core/run_manifest.py::finalize_manifest(...)` then reads `out/system_health_checklist.csv` and copies aggregate counts into the A manifest even if that file predates the current A run.
- `scripts/flows/A/A015_build_system_health_check.py` currently treats the latest A manifest as usable if it exists, is readable, is not older than 36 hours, and contains the `process_stock_receipts_sheet.py` step.
- A015 does not currently require that all configured A steps appear in the manifest, and it does not currently reject a manifest that finalized after only a subset of `RUN_ORDER`.

## March 10 Failure Surface

- The March 10, 2026 morning A manifest `out/manifests/A/2026-03-10/20260310T060002Z.json` finalized after only 3 recorded steps even though the configured run order contains 13 steps.
- That manifest still carried `health_summary.fail_count=0` and `health_summary.warn_count=0` by reading `out/system_health_checklist.csv`, even though that checklist file was stale from March 4, 2026 rather than created by the March 10 run.
- This demonstrates two independent integrity gaps:
- traversal completeness is not enforced
- final health evidence is not bound to the current cycle

## Failure Modes In The Current Design

- Early finalization after only a subset of steps can happen if the orchestrator stops before `RUN_ORDER` is fully traversed but still reaches the `finally` block. Plausible causes include:
- unexpected exception or external termination after a completed child step
- an added or accidental `break` path
- future edits that mutate control flow without also updating manifest invariants
- any process-level interruption where Python still executes `finally`
- Because manifest writing happens in `finally` and has no traversal audit, partial progress can be serialized as if it were a normal completed run.
- `rc=0` with missing outputs can happen because success reporting is tied to child return code alone. Static output declarations are written into the manifest without existence or freshness checks.
- Stale health artifacts can be reused as current evidence because:
- manifest finalization always reads `out/system_health_checklist.csv`
- the finalizer does not require that A015 ran in the same cycle
- the finalizer does not require checklist mtime >= cycle start
- the finalizer does not require a run-id marker inside the checklist output
- A015 itself currently accepts a latest manifest that only proves the receipts step was present, not that the A run fully completed.

## Safe Fix Design

- Add explicit cycle-traversal accounting to the A orchestrator:
- record `configured_step_count`
- record `launched_step_count`
- record `completed_step_count`
- record `verified_step_count`
- record `final_state` such as `completed`, `failed`, `degraded`, `interrupted`, `partial`
- Treat the manifest as an execution record, not a summary guess:
- `step launched` means the parent started the child process
- `step completed` means the child process returned and the parent captured the return code
- `expected outputs verified` means required outputs passed post-step verification
- Finalization must compare actual traversed count to configured count. If the list was not fully traversed, the cycle must not finalize as successful.
- Replace declaration-only output handling with per-step verification rules:
- each step declares required outputs and optional outputs
- required outputs must exist after the child returns
- required outputs must be fresh relative to the step start time or carry another approved same-run proof
- optional outputs may be missing without flipping the step to failed
- A child step returning `rc=0` but missing required outputs should be recorded as:
- child_result=`rc=0`
- verification_result=`failed_missing_outputs`
- step_status=`failed`
- The cycle should then stop immediately for required-output failures on blocking steps because downstream A steps would otherwise consume missing or stale data.
- Guardrail or explicitly non-blocking cases must be modeled separately as policy-driven skips or warnings, not as ordinary success.
- Bind health evidence to the current A cycle:
- A015 outputs must be considered current only if they are written after the A015 step start and after the cycle start
- the manifest finalizer must not copy health counts from a checklist file unless the A015 step both completed and verified
- if A015 did not run in the cycle, or if its checklist is stale, the manifest health section must be marked stale or unverified rather than healthy
- Update A015 manifest interpretation:
- reject partial A manifests as current-cycle success evidence
- require the A manifest to declare traversal status and configured-vs-actual counts
- use that state when deciding whether the A cycle completed cleanly, partially, or not at all

## A Daily Intel Eligibility And Freshness Contract

- `scripts/flows/A/A015_build_system_health_check.py` and `scripts/flows/A/A016_refresh_phase1_daily_intel.py` must use one shared required-SKU derivation rule for daily-intel eligibility.
- Required daily-intel SKU scope is defined as:
- SKU is in `out/phase1_sku_scope.csv`
- SKU is non-parked (`parked_flag != 1`, with parked overrides still respected)
- SKU has stock quantity greater than zero from the canonical stock-source precedence
- Canonical stock-source precedence for required-SKU derivation is:
- latest `out/inventory_snapshot_*.csv`
- `out/inventory_summaries.csv`
- `out/parking/stock_snapshot_latest.csv`
- A015 must evaluate a freshness prerequisite before daily-intel coverage and compliance checks.
- Freshness prerequisite means A015 must confirm that daily-intel evidence is current for the same operational window as the evaluated scope.
- If freshness is not satisfied, A015 must emit a dedicated prerequisite-style failure and must not report a false missing-SKU coverage failure for that state.
- Dedicated prerequisite failure must remain fail-closed and visible in health outputs.
- This contract is an eligibility and diagnostics integrity change only.
- This contract does not alter repricing strategy, pricing logic, floor/ceiling policy, or business decision rules.
- Genuine daily-intel failures remain genuine failures and must still surface as FAIL.

## A Daily Intel Operational Sequencing

- Operational baseline for trusted A health requires a full A traversal through `A016_refresh_phase1_daily_intel.py` and then `A015_build_system_health_check.py`.
- Partial A runs can leave mixed-freshness artifacts between scope, daily-intel output, and health outputs.
- Health interpretation for daily-intel coverage/compliance must respect freshness prerequisites before interpreting coverage deltas as true missing-SKU failures.

## Issue-Class Behavior Policy

- Configured step list not fully traversed:
- classify as `fail`
- final cycle state `partial` or `interrupted`
- do not report cycle success
- do not treat prior health checklist as current-cycle evidence
- Child returns non-zero on a blocking step:
- classify as `fail`
- stop the cycle immediately
- preserve manifest with exact last launched/completed step
- Child returns zero but required outputs are missing or stale:
- classify as `fail`
- stop the cycle immediately
- record that the child succeeded but verification failed
- Child returns non-zero on an explicitly approved non-blocking policy step:
- classify as `degraded` or `warn` only if the policy is documented in code and control docs
- continue only when the downstream pipeline does not depend on that output
- Health/checklist file exists but is older than the current cycle or older than the A015 step:
- classify as `fail` for gating purposes
- keep the stale artifact visible for debugging, but do not reuse it as current proof

## Implementation-Ready Plan

- Likely code files:
- `scripts/cycles/run_A_all.py`
- `scripts/core/run_manifest.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- possibly shared manifest helpers if step-output verification is reused by other cycles later
- Recommended implementation order:
- extend manifest schema to represent traversal counts, step state, verification state, and final cycle state
- update `run_A_all.py` to record launched/completed/verified separately and to hard-fail partial traversal
- add required-output verification helpers and per-step policy definitions
- bind A manifest health summary to current-run A015 evidence only
- update A015 to treat partial manifests and stale checklist evidence as invalid current-cycle proof
- Validation approach:
- controlled test where all 13 steps are traversed and required outputs verify
- forced child failure on a blocking step
- forced `rc=0` with a removed required output
- forced early orchestrator interruption after step 3 to confirm manifest finalizes as partial/failed, not successful
- stale checklist replay test using a pre-existing March 4 style artifact to confirm it is rejected as current-cycle evidence
- Rollback and safety:
- keep the first implementation A-only
- preserve existing output paths and step order
- add new manifest fields in an additive way so old readers do not crash immediately
- do not change Sheets or local DB behavior as part of the integrity fix

## Operational Runbook Boundary

- Flow-specific runbooks and incident plans remain subordinate references, not top-level architecture authority.
- `cycle_recovery_plan_v1.md` and `scripts/cycles/H_PHASE1_INLINE_MODE_RUNBOOK.md` should be read as scoped operational guidance unless their rules are promoted into maintained control files.

## H Cycle Operating Model

- `run_H_cycle.bat` is the operational H launcher and the only approved production entrypoint for starting the H service.
- `scripts/cycles/run_H_pricing_cycle_guarded.py` is the required guard wrapper for production starts. It is responsible for preserving heartbeat, phase, fault, crash, and exit-status evidence around the real H child process.
- `scripts/cycles/run_H_pricing_cycle.py` contains the actual H pricing loop, staged publish flow, and per-cycle sleep/cadence behavior.
- Production H operation is a continuous service model:
- the launcher starts the guarded child
- the child completes one pricing cycle
- the launcher relaunches after child exit unless H is explicitly put into one-shot or controlled maintenance mode
- Task Scheduler is a bootstrap or recovery trigger for H, not the normal per-cycle cadence engine.
- One-shot H execution is a maintenance and diagnostic mode only. It must be requested explicitly and must not be the silent production default.
- Controlled mode remains a maintenance safety control that forces one-shot behavior for manual guarded runs.

## H Cycle Protection Model

- H production starts must retain the current protection stack:
- active process detection before launch
- live lock ownership and stale-lock archival
- in-progress marker cleanup logic
- finalizer and publish marker validation after child exit
- guarded heartbeat and exit-status evidence
- These protections are part of the operational architecture because they prevent duplicate runs, detect partial exits, and preserve crash evidence outside the child process.

## Controlled Overnight Restart Architecture

- Controlled overnight restart is an architecture-level lifecycle feature, not a one-off script patch.
- Purpose:
- replace unsafe hard shutdown behavior with a drain-first, fail-closed restart model
- preserve run ownership truth, lock truth, and finalization truth across restart boundaries
- keep startup recovery on the normal boot/task path rather than adding parallel startup logic

### Restart Window Model

- Restart orchestration should target a quiet overnight local-time window around 02:00 to 03:00.
- Restart is requested during that window, not forced at an exact blind cutoff timestamp.
- If approval conditions are not met during the window, reboot is skipped for that window and recorded as skipped.

## H Stability Control Architecture (Planning Baseline, PROMPT 022)

### Single Runtime Ownership Model

- Exactly one active restart authority is allowed for H at any time.
- Primary active owner for normal operation: `run_H_cycle.bat` launcher loop.
- Windows Scheduler is bootstrap ownership only:
- allowed to start launcher when service is not running
- not allowed to act as per-cycle restart authority
- `controlled_restart_gate.py` and `controlled_restart_controller.py` are escalation-only control layers:
- they can request controlled drain and produce approval evidence
- they do not own normal relaunch cadence
- `home_time_monitor.py` is observer plus escalation signal only:
- it records anomalies and proposes safe interventions
- it does not directly recycle normal H runtime loops

### Ownership Transfer Rules

- Transfer from launcher owner to controlled restart owner is allowed only during an explicit controlled-restart window and only after drain markers prove boundary-safe state.
- Transfer back to launcher owner is required immediately after restart window closes, approved restart completes, or restart is skipped.
- If ownership is ambiguous, system must fail closed and hold state rather than allow two authorities to act.

### Windows-Tolerance Architecture Rules

- Anti-churn relaunch model:
- do not relaunch immediately after short failed exits
- enforce cooldown windows that increase with repeated short failures
- Stale lock and heartbeat checks must use tolerance windows large enough to absorb short Windows scheduler/session delays.
- SIGBREAK or session-interruption signals must be classified as interruption events first, not immediate hard-fault loops.
- Parent and child mismatch must enter a reconcile window before restart decisions are made.
- Reboot path is escalation-only and must remain explicit, auditable, and rare.

### Anti-Churn Principles

- Prefer fewer controllers over layered concurrent controllers.
- Preserve ownership truth over speed of relaunch.
- Treat uncertain runtime state as "hold and observe", not "restart now".
- Keep one clear source of restart truth per window.

### Disallowed Control Patterns

- Multiple runtime layers issuing independent restart actions in the same window.
- Fast fixed relaunch loops after repeated short failures without cooldown.
- Automatic reboot escalation from observer layers during normal runtime ownership windows.
- Clearing ownership markers before boundary/finalization truth is known.

### Fail-Closed Approval Model

- Reboot must never execute unless safe idle and finalized conditions are positively proven from authoritative runtime artifacts.
- Uncertain state is treated as unsafe state.
- If drain proof is missing, conflicting, stale, or incomplete, the orchestrator must fail closed and skip reboot.
- Forced reboot is not normal behavior for controlled restart.

### Existing Contract Reuse Model

- Controlled restart must reuse existing lifecycle contracts first:
- H controlled mode and one-shot boundary behavior through `run_H_cycle.bat` and `h_controlled_mode.active`
- H launcher, lock, in-progress, finalized, boundary, and result artifacts under `out/systems/H/live/`
- A and B maintenance handoff markers:
- `out/locks/maintenance.requested`
- `out/locks/maintenance.ready`
- `out/locks/maintenance.active`
- legacy supported pause marker:
- `out/locks/b_cycle.maintenance`
- Existing locks, heartbeats, manifests, runtime-status files, and archive markers are the primary proof plane for restart safety.
- Controlled restart must not introduce a parallel truth model when authoritative markers already exist.

### Protected Restart Blocker States

- Restart approval must be blocked when any protected blocker state exists.
- Minimum mandatory blockers:
- H finalize-blocked conditions including `FINALIZE_BLOCKED_NO_PUBLISH` or equivalent wrapper/core finalize-blocked outcomes
- H unresolved ownership where `H_run_in_progress.txt` does not have matching finalized release evidence
- unresolved or ambiguous H boundary state for the active/owned run
- boundary/result/finalizer marker conflicts that prevent authoritative run classification
- B still active without maintenance boundary readiness proof
- B maintenance handoff incomplete (`maintenance.requested` without valid `maintenance.ready` progression, or active maintenance not safely cleared)
- B health WARN/FAIL states that prevent proving safe idle for restart approval
- stale, conflicting, or ambiguous lock/run markers across H, B, A, or E that prevent positive safety proof
- Current live fault policy:
- restart orchestration must not treat known H finalize-blocked behavior as reboot-safe
- restart orchestration must not treat known B WARN behavior as reboot-safe
- these remain blocker states until a later implementation provides explicit approved gating behavior

### Orchestration Stage Contract

- The intended controlled restart sequence is:
- restart request created inside window
- loops stop starting new work through existing maintenance/controlled mechanisms
- active work drains to a safe boundary
- orchestrator verifies safety and ownership from authoritative artifacts
- restart is approved or explicitly skipped
- reboot executes only on approved state
- post-boot verification confirms expected loop/service resumption
- Any stage that cannot prove state must terminate as skipped, not guessed success.

### Startup And Post-Boot Recovery Model

- Post-reboot recovery should continue to rely on the normal Windows startup/task model already used by operations.
- H, B, and pricing-related recovery assumptions must not be hardcoded until task-to-entrypoint bindings are validated against real scheduler configuration.
- Implementation must explicitly verify actual scheduler bindings before relying on reboot recovery assumptions.

### Scheduler-Model Reconciliation Requirement

- Architecture currently states Task Scheduler is bootstrap/recovery for H rather than normal per-cycle cadence.
- Inspection observed a scheduler pattern suggesting repeated startup triggering.
- Controlled restart implementation must reconcile this documented-vs-observed model before production reliance:
- confirm each relevant Windows task entrypoint and trigger behavior
- confirm no conflicting repeated trigger causes overlap or restart churn
- record reconciled task-to-entrypoint mapping as implementation evidence

### Restart Observability Contract

- Controlled restart implementation must write auditable restart-state evidence, including at minimum:
- restart requested
- drain in progress
- drain ready
- restart approved
- restart skipped
- post-boot verification result
- Evidence must represent actual state transitions; synthetic success states are not allowed.

### Scope And Change Boundaries

- Controlled restart implementation should be narrow, reversible, and additive.
- Avoid broad runtime refactors when existing lifecycle contracts can be reused.
- Do not change Google Sheets behavior as part of restart orchestration.
- Restart logic must not be used as a workaround for unresolved runtime defects; unresolved defects remain blocking signals.

## Home Time Mode Architecture

- Home time mode is a Codex unattended-work mode for a single active umbrella issue while Luke is away.
- Home time mode is a supervisory task-execution layer, not a replacement for launcher ownership, guard-wrapper ownership, maintenance ownership, or failed-run archive authority.
- Home time mode must preserve the existing H production service model:
- `run_H_cycle.bat` remains the production launcher
- H continuous self-relaunch remains the default runtime model
- home time mode must not stop H merely to hand control back to GPT or Luke
- home time mode may work around H state only through already-approved ownership paths

## Home Time Mode Activation Model

- Home time mode must start from an explicit operator action, not from inferred user absence.
- The preferred activation path is a dedicated operator tool such as:
- `python scripts/tools/start_home_time_mode.py`
- Activation should write a durable repo artifact rather than relying on chat continuity.
- The preferred activation artifact is a timestamped or session-scoped marker under `out/systems/H/live/`, for example:
- `H_home_time_mode.active.json`
- The activation artifact should record at minimum:
- activation timestamp
- operator or initiator
- umbrella issue or ticket label
- allowed scope summary
- current H ownership snapshot
- current session id

## Home Time Mode Allowed Action Envelope

- Home time mode may continue the current umbrella issue through:
- inspection
- planning
- implementation
- validation
- Home time mode may read the artifacts needed to prove safe ownership and current state, including:
- launcher, lock, heartbeat, runtime-status, boundary, wait, result, archive, manifest, and health artifacts
- Home time mode may make repo code and control-file changes that are otherwise allowed by the active approved task.
- Home time mode may run narrow validation and test commands needed for the active task, subject to existing flow-specific restrictions.
- Home time mode may use `scripts/tools/archive_failed_H_run.py` only when its existing archive safety gate passes.
- Home time mode may run controlled one-shot maintenance or diagnostic commands only when those runs do not replace the standing H background service and do not create ambiguous ownership.

## Home Time Mode Forbidden Action Envelope

- Home time mode must not stop H just to return control.
- Home time mode must not clear `H_run_in_progress.txt` directly.
- Home time mode must not bypass failed-run archive rules or write failed-run release markers outside the approved archive tool.
- Home time mode must not bypass maintenance-mode ownership rules or maintenance handoff readiness rules.
- Home time mode must not treat partial manifests, stale checklist files, stale markers, or partial run evidence as proof of successful completion.
- Home time mode must not release ownership for an H run unless authoritative artifacts prove release is allowed.
- Home time mode must not rely on chat history as the only unattended-state record.

## Home Time Mode Fail-Closed Contract

- Home time mode must fail closed on ownership uncertainty.
- If Codex cannot prove a safe ownership state from authoritative artifacts, it must stop making modifying actions.
- Required fail-closed cases include:
- unresolved or ambiguous H boundary state
- active H run without approved ownership-release evidence
- failed-run archive conditions not satisfied
- active, incomplete, or ambiguous maintenance state
- validation evidence that is stale, partial, or not current-run proof
- In those cases, home time mode must leave a durable handoff artifact and stop in a blocked state rather than guessing or cleaning up aggressively.

## Home Time Mode Handoff Artifact Model

- Home time mode must leave a durable handoff artifact whenever unattended work completes, pauses, or blocks.
- The preferred artifact family is:
- `out/systems/H/live/H_home_time_report.<timestamp>.json`
- The report should be created as a new timestamped file rather than by mutating one shared summary file.
- The report should contain at minimum:
- home-time session id
- umbrella issue or ticket label
- activation time
- finish or block time
- tasks attempted
- files changed
- validation or test commands executed
- current ownership state
- current boundary or archive state if relevant
- blocker or completion reason
- recommended next step
- verification status and evidence paths

## Home Time Mode Interaction With Existing Modes

- Home time mode must never override H controlled mode.
- If controlled mode is active, home time mode may observe it and may use it only in explicitly approved maintenance-style work. It must not silently clear the controlled-mode flag.
- Home time mode must never override maintenance mode.
- If B or future A maintenance artifacts indicate an active handoff, home time mode must respect those ownership boundaries and fail closed when required.
- Home time mode must never override `run_H_cycle.bat` ownership or relaunch policy.
- Home time mode must treat `scripts/tools/archive_failed_H_run.py` as the only approved failed-run ownership-release path during unattended work when archive conditions are satisfied.

## H And A016 Subprocess Boundary Model Today

- H phase1 daily-intel alignment is launched from `scripts/cycles/run_H_pricing_cycle.py` inside `_run_phase1_daily_intel_refresh_subprocess()`.
- H spawns `scripts/flows/A/A016_refresh_phase1_daily_intel.py` as a child subprocess with:
- `A016_RESULT_PATH=<run-scoped result json path under out/systems/H/live/>`
- `A016_PARENT_PID=<the H core python pid>`
- `H_RUN_ID=<current H run id>`
- `A016_PROGRESS_LOG_PATH` and `H_PHASE1_INTEL_PROGRESS_PATH` pointed at the shared `out/systems/H/live/phase1_intel.progress.log`
- H launches the child with `subprocess.Popen(...)` and pipes both stdout and stderr.
- H records boundary-start evidence before waiting:
- `phase1 daily_intel alignment subprocess_start`
- `phase1 daily_intel alignment child_started`
- H then waits in a polling loop using `proc.communicate(timeout=5.0)`.
- H only records the explicit H-side boundary outcome after `communicate()` returns:
- `subprocess_done`
- `payload_check`
- `decision ... payload_source=stdout|result_file`
- or `boundary_failure ...`
- If a boundary exception is raised in the phase1-intel caller, H should then record `FATAL phase1_intel_boundary_failure ...` and terminate with a boundary-specific exit code.

## H Core Parent-Liveness Contract During Phase1-Intel

- During `phase1_intel`, the authoritative parent token enforced by A016 is the H core process from `scripts/cycles/run_H_pricing_cycle.py`.
- Launcher `cmd.exe` residency is not the parent token A016 enforces.
- Guard-wrapper residency is not the parent token A016 enforces.
- H core passes its own pid through `A016_PARENT_PID` and then becomes the active waiter on the A016 subprocess.
- Therefore the `phase1_intel` subprocess wait path in H core is a protected ownership window.
- H core must remain alive through:
- child completion
- timeout kill and payload classification
- controlled failure handling after child return
- any explicit controlled shutdown path that preserves durable evidence
- H core must not disappear silently during that wait window.

## H Core Wait-Path Evidence Requirement

- If H core exits, is forced out, or is interrupted during the protected `phase1_intel` wait window, the runtime must preserve enough evidence to distinguish:
- controlled shutdown
- internal handled failure
- external termination or interruption
- unexpected wait-path disappearance while the child is still running
- This evidence belongs primarily to the H core wait path because that layer owns:
- the child subprocess handle
- the parent pid A016 watches
- the wait loop that decides timeout, success, or boundary failure after child return
- Launcher heartbeat staleness alone is not sufficient evidence for this defect class because the launcher heartbeat is not designed to refresh continuously while the launcher is blocked waiting on its child.

## H And A016 Result Contract Today

- The intended success contract is dual-path:
- A016 writes a JSON payload to the run-scoped `A016_RESULT_PATH`
- A016 also emits the same JSON payload on stdout
- The intended failure contract is result-file-based:
- A016 top-level failure handling writes a failure JSON payload to `A016_RESULT_PATH`
- H accepts payload from stdout first when the last stdout line is JSON, otherwise from the result file
- H treats the boundary as resolved only after it can parse a usable payload and classify the child result as `ok`, `failed`, or `timeout`
- The current contract breaks down because A016 writes core outputs before payload emission, while H does not surface any H-side outcome until after the child wait returns cleanly into H control.

## A016 Output Ordering Today

- A016 currently does substantial real work before boundary payload emission:
- resolves scope and target universe
- processes SKUs
- writes or upserts daily-intel rows
- runs post-run coverage repair
- writes final output rows for the day
- only after that builds the success payload and calls `_emit_success_payload(...)`
- Because of this order, staged or authoritative daily-intel output can exist even when no result payload exists yet.
- This means the current pipeline allows `core outputs exist` and `boundary result missing` to be true at the same time.

## H Boundary Failure Surface Confirmed On March 10

- Fresh H run `20260310T105440Z` reached:
- `phase1 daily_intel alignment child_started`
- That same run did not record:
- `subprocess_done`
- `payload_check`
- `decision`
- `boundary_failure`
- `FATAL phase1_intel_boundary_failure`
- No run-scoped boundary result file was created in `out/systems/H/live/` for that run.
- Child-side progress for the same run stopped before payload emission markers, but staged output later appeared at `out/systems/H/staged/20260310T105440Z/data/sku_daily_intel.csv`.
- This confirms a real architecture gap: boundary ownership and boundary truth are not currently coupled tightly enough to guarantee an explicit outcome before H ownership is considered finished.

## H Launcher Ownership Model Today

- `run_H_cycle.bat` is the production launcher and ownership gate for H.
- Launcher ownership is represented by:
- `out/systems/H/live/H_launcher.lock`
- a live launcher `cmd.exe` process
- H parent `python.exe` processes matching `run_H_pricing_cycle.py` or `run_H_pricing_cycle_guarded.py`
- H run ownership is represented by:
- `out/systems/H/live/H_pricing_cycle.lock`
- `out/H_pricing_cycle.lock`
- `out/systems/H/live/H_run_in_progress.txt`
- `out/systems/H/live/H_cycle_current_run_id.txt`
- `out/systems/H/live/H_last_finalized_run_id.txt`
- Current launcher overlap checks do not consider unresolved A016 child processes.
- Current cleanup logic removes or archives H ownership markers when the H parent is gone, even if an A016 child spawned by that H run is still alive.
- Therefore ownership currently ends at the H parent boundary, not at the full H to A016 subprocess boundary.

## H Launcher Ownership And Finalization Contract

- H relaunch eligibility is controlled by run finalization truth, not only by child-process boundary state.
- A run remains ownership-active for launcher gating until that same run is explicitly finalized or explicitly archived by approved failure-handling logic.
- A boundary transition away from `active` does not by itself release launcher ownership.
- `resolved_failure` is still a blocking ownership state for relaunch when the run is not yet finalized.
- `out/systems/H/live/H_run_in_progress.txt` is the launcher-facing ownership marker for the active H run.
- If `H_run_in_progress.txt` names run `X` and `H_last_finalized_run_id.txt` does not also name run `X`, launcher must treat run `X` as still owning cleanup/finalization.
- For that not-yet-finalized run, a run-scoped boundary file and/or run-scoped result payload count as affirmative evidence that the run still owns failure cleanup.
- Nonzero child exit is not sufficient proof that launcher ownership may be cleared.
- Deleting or reusing the in-progress marker for a failed run is a finalization action, not a generic nonzero-exit cleanup action.

## H Relaunch Blocking Contract

- Launcher relaunch must fail closed for any run that is still ownership-active.
- The launcher must not clear `H_run_in_progress.txt` merely because the run-scoped boundary file has transitioned to `resolved_failure`.
- The launcher must not treat `resolved_failure` as equivalent to `fully cleaned up` or `safe to reuse`.
- If run `X` has:
- `H_run_in_progress.txt = X`
- `H_last_finalized_run_id.txt != X`
- and run-scoped boundary and/or result artifacts for `X`
- then launcher must block relaunch for `X` until explicit finalization/archive logic releases ownership.
- This blocking rule applies even when the H parent process is already gone.

## H Failure-Path Cleanup Rule

- Failure cleanup is split from ownership release.
- The guarded wrapper and H core may establish truthful child failure evidence, but they do not by themselves authorize launcher ownership release.
- Launcher cleanup after nonzero exit may archive dead locks and preserve evidence, but it must not silently delete ownership for a failed run that still has run-scoped boundary/result artifacts and is not finalized.
- Explicit finalization/archive logic is the only layer allowed to release ownership for such a failed run.

## H Failed-Run Archive And Release Contract

- Failed-run release must use a dedicated archive marker, not the normal success finalization marker.
- The planned archive marker is:
- `out/systems/H/live/H_failed_run_archived.<run_id>.json`
- This marker is the explicit proof that a failed run has been reviewed and intentionally released for relaunch.
- The archive marker must preserve failure evidence rather than replace it. Run-scoped boundary, result, wait, and log artifacts remain in place after archive.
- The archive marker is separate from:
- `out/systems/H/live/H_last_finalized_run_id.txt`
- normal publish/completed markers
- lock archival under `out/locks/archive/`
- Ownership release for a failed run is therefore:
- not a success finalization
- not a generic cleanup side effect
- not a boundary-status transition
- but an explicit failed-run archive action

## H Failed-Run Archive Authority

- The launcher must not write the failed-run archive marker on its own.
- The guarded wrapper must not write the failed-run archive marker on its own.
- H core must not self-archive a failed run on its own.
- The planned writer is an explicit operator tool so archive remains a deliberate recovery action:
- `scripts/tools/archive_failed_H_run.py --run-id <run_id>`
- That tool is expected to validate live safety conditions before writing the archive marker and before clearing launcher ownership.

## H Failed-Run Archive Safety Gate

- Failed-run archive must fail closed unless all of these are true for run `X`:
- `H_run_in_progress.txt == X`
- `H_last_finalized_run_id.txt != X`
- no active H core or guarded-wrapper python process exists for the repo
- run-scoped boundary and/or result evidence exists for `X`
- archive marker does not already conflict with another run
- Archive must not be allowed to hide an active run.
- If H python is still alive, archive must refuse to release ownership.
- If the in-progress marker names a different run, archive must refuse to release ownership.
- If there is no run-scoped failure evidence, archive must refuse to release ownership.

## H Launcher Interpretation Of Failed-Run Archive

- Launcher relaunch gating continues to fail closed by default.
- The only approved failed-run ownership release path is:
- `H_run_in_progress.txt = X`
- `H_last_finalized_run_id.txt != X`
- `H_failed_run_archived.X.json` exists and passed archive safety validation when written
- Once that archive marker exists for the same run, launcher may:
- preserve the run-scoped boundary/result evidence
- clear `H_run_in_progress.txt` for run `X`
- allow a fresh run to start
- Launcher must not treat the failed-run archive marker as a success finalization marker.
- `H_last_finalized_run_id.txt` remains reserved for normal finalized-success release only.

## H Failed-Run Operator Procedure

- The approved operational release path should be a narrow explicit command:
- `python scripts/tools/archive_failed_H_run.py --run-id <run_id>`
- The operator tool should:
- verify the safety gate
- write `H_failed_run_archived.<run_id>.json`
- record who/when/why the release happened
- then clear `H_run_in_progress.txt` only for that same run
- The tool must not delete the run-scoped boundary/result artifacts that justified the archive action.

## H Layer Authority Split

- `scripts/flows/A/A016_refresh_phase1_daily_intel.py` is authoritative for child-side boundary/result truth once launched.
- `scripts/cycles/run_H_pricing_cycle.py` is authoritative for H run execution state, stage progression, and whether the run reached finalizer/write points.
- `scripts/cycles/run_H_pricing_cycle_guarded.py` is authoritative for preserved wrapper-side exit evidence and for surfacing boundary-aware finalizer outcomes when the H child exits.
- `run_H_cycle.bat` is authoritative for launcher relaunch eligibility and ownership gating across runs.
- During `phase1_intel`, only H core is authoritative for parent liveness because only H core owns the pid that A016 enforces through `A016_PARENT_PID`.
- Child failure truth is decided from A016 boundary/result artifacts plus wrapper/H-core interpretation.
- Run finalization truth is decided by explicit finalized-run markers, not by boundary status alone.
- Relaunch eligibility is decided by the launcher from ownership markers plus finalized-run truth, using boundary/result artifacts as blocking evidence for failed-but-unfinalized runs.

## H Secondary Launcher Residency Note

- The stale `cmd.exe` launcher residency observed after the latest child death remains a secondary H issue.
- That issue is separate from, and lower priority than, the ownership/relaunch defect where failed-but-unfinalized runs are being cleared too early.
- Ownership and relaunch correctness should be fixed first so duplicate or premature H restarts stop before the launcher-residency edge case is adjusted.
- The next runtime hardening focus is now the H core `phase1_intel` wait path, not launcher relaunch policy.
- Launcher stale residency remains follow-on work unless a minimal coupled change is required to support H core wait-path evidence.
- This architecture note remains intentionally limited to H core disappearance during `phase1_intel` wait plus the already-approved launcher ownership/finalization contract, and does not expand into SP-API or unrelated runtime work.

## Why Overlap Can Still Happen

- The launcher restart gate checks for active H parent processes, not boundary child-tree completeness.
- If the H parent exits early during the A016 wait window, the launcher can:
- archive H locks
- remove `H_run_in_progress.txt`
- relaunch a fresh H parent after the restart delay
- An unresolved A016 child can continue writing run-scoped output after H ownership has already been cleared.
- This creates a duplicate-risk architecture state:
- prior run boundary unresolved
- prior child still active
- next H cycle already started

## Safe Fix Design For Boundary Outcome Integrity

- H boundary ownership must be extended from `H parent alive` to `boundary resolved`.
- A boundary is only resolved when exactly one of these is true for the run:
- success payload parsed and accepted
- failure payload parsed and accepted
- timeout or kill path recorded with explicit run-scoped boundary failure evidence
- hard-exit or nonlocal-exit path recorded with explicit run-scoped unresolved-boundary evidence
- H should write a run-scoped boundary marker as soon as the child is launched and update it through explicit states such as:
- `started`
- `waiting`
- `resolved_success`
- `resolved_failure`
- `resolved_timeout`
- `unresolved_parent_exit`
- H should record explicit hard-exit evidence around the wait window so abnormal parent loss cannot leave the boundary silent.
- A016 should not be able to leave authoritative core outputs without also leaving an authoritative boundary artifact.
- The safest design is:
- create a run-scoped boundary artifact before final output commit
- update that artifact to success or failure as the last required boundary step
- treat missing payload with existing outputs as a boundary-specific failure, not as a generic publish/finalizer failure
- If H sees child outputs but no contract payload, H should classify the run as boundary-failed and surface a truthful boundary-specific reason code rather than only `FINALIZE_BLOCKED_NO_PUBLISH`.

## Safe Fix Design For Ownership And Overlap Integrity

- Launcher restart gating must include unresolved H-owned boundary children, not only H parent processes.
- Ownership should be represented by both:
- a run-scoped boundary-state marker
- live process ownership checks for boundary children spawned by H
- The launcher should not start a new H cycle when the latest run is still in any unresolved boundary state.
- Safe stale handling should distinguish:
- live unresolved child still running
- dead parent with unresolved boundary artifact
- dead child with unresolved boundary artifact
- fully stale unresolved boundary beyond an approved stale threshold
- Orphan cleanup should never silently discard an unresolved boundary.
- The launcher should preserve the unresolved marker and force the next cycle start to fail closed until the boundary is explicitly resolved or explicitly recovered.

## Boundary Resolution Artifacts Required By The Fix

- The safe design should make these artifacts authoritative for the H to A016 boundary:
- run-scoped boundary-state marker under `out/systems/H/live/`
- run-scoped result payload file
- shared progress log with payload-emission checkpoints
- H-side watchdog enter and exit markers
- H-side fatal unresolved-boundary marker when the parent exits before resolution
- Launcher restart checks should treat those artifacts as the proof source for whether the previous boundary is still open.

## Implementation-Ready Plan For H And A016 Boundary Integrity

- Likely code files:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/cycles/run_H_pricing_cycle_guarded.py`
- `run_H_cycle.bat`
- possibly `scripts/tools/h_session_tally.py` only if run accounting needs boundary-state awareness
- Recommended implementation order:
- add run-scoped boundary-state artifacts and explicit unresolved-parent-exit evidence in H
- tighten A016 output versus payload ordering so authoritative outputs cannot exist without authoritative boundary artifacts
- update H to classify missing payload after child work as a boundary-specific failure with a truthful exit code and reason
- update launcher restart gating to block on unresolved boundary markers and unresolved A016 child ownership
- add safe stale and orphan handling for unresolved boundary markers
- Validation approach:
- normal success run with full boundary signals and publish proof
- forced child failure with failure payload and H-side boundary-failure logging
- forced child timeout with watchdog kill evidence
- forced parent-abnormal-exit during wait window to confirm unresolved-boundary evidence is written and launcher restart is blocked
- overlap test proving a fresh H run cannot start while a prior A016 child boundary is unresolved
- Rollback and safety:
- keep the first change additive with new markers and new logs rather than replacing existing markers immediately
- preserve current staged-output paths
- fail closed on unresolved boundary states rather than guessing success
- keep launcher stale cleanup conservative so unresolved artifacts are visible for recovery rather than silently deleted

## H Cycle Regression Note

- The restructure introduced a launcher-policy regression where `run_H_cycle.bat` defaults to one-shot exit after a clean child run unless restart is explicitly enabled.
- That behavior conflicts with the intended H operating model, because the available scheduler evidence is bootstrap-oriented rather than a documented recurring cadence controller.

## Repricer Architecture

### Current Live Repricer Contract

- The live repricer is the H flow, not a separate standalone service.
- Runtime orchestration lives in:
- `run_H_cycle.bat`
- `scripts/cycles/run_H_pricing_cycle_guarded.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- Repricer decision logic lives primarily in:
- `scripts/phase1/`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/flows/A/A018_build_phase1_floor_table.py`
- The current live contract is multi-SKU and active-merchant scoped, with scope and write eligibility materialized through:
- `out/phase1_sku_scope.csv`
- `config/h_sku_switches.csv`
- current H/Phase1 runtime artifacts under `out/systems/H/live/`
- The current runtime contract should be read from:
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- the implemented H/Phase1 code paths above
- supporting live artifacts under `out/` and `data/`

### Target Repricer Architecture

- The target architecture remains broader than the current live contract.
- It includes the multi-layer repricer design described in:
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md`
- This target architecture includes concepts not yet established as live runtime contract, including:
- notification-led orchestration
- portfolio governor logic
- broader suppression architecture completion
- pressure-state workflow
- demand-ceiling learning and later-stage intelligence layers

### Suppression Fallback Completion Boundary

- Suppressed Buy Box handling is already partially built inside the current live repricer.
- Existing live suppression capability already includes:
- suppression detection
- suppression threshold memory
- suppression-specific runtime state
- direct and inferred suppression targeting
- temporary suppression ceilings
- suppression case and reactivation logging
- longer suppression verification windows
- The next suppression feature is therefore a current-contract completion layer, not a subsystem redesign.
- The intended current-contract completion is:
- explicit decision order across cycles between direct target, learned threshold, inferred upper bound, carry-forward ceiling, and bounded downward probing
- explicit retry-budget, cooldown, stop, and re-entry rules
- explicit resolved-state and audit outcomes
- explicit storage guardrails so persisted suppression ceilings cannot remain below anchor-floor governance
- Portfolio-aware suppression strategy, notification-led suppression handling, and richer learned suppression models remain target-only or deferred.

### Repricer Document Roles

- Current runtime contract:
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- Current control-file runtime contract:
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- Target architecture:
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md`
- Historical implementation plan and reference proof:
- `out/process_guides/repricing_tool/master plans/Phased execution/phase_1.md`
- `out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md`
- `out/process_guides/repricing_tool/master plans/Phased execution/phase_1_deep_study_report_2026-02-13.md`
- Archive and reference material:
- older `strategy-steps*` versions
- older masterplans under `out/process_guides/repricing_tool/master plans/old/`

### Repricer Boundaries

- The repricer planning lane must distinguish:
- current live contract
- target architecture
- deferred ideas
- The suppression fallback planning lane must also distinguish:
- must-have current-contract completion
- should-have audit and validation hardening
- deferred future suppression intelligence
- Repricer governance belongs in `project_control/` as system architecture and planning authority.
- Repricer process-guide documents remain detailed design references, but project-control files must state which repricer document is currently authoritative for runtime and which is target-only.

## Not Yet Settled

- Ownership of some non-token datasets remains unresolved, including inbound shipment contents and other duplicate-truth groups identified in the authority report.
- The older module plan in `APP_PLAN.txt` references a DB-centered future architecture, but this repo still needs an explicit decision on whether that remains the intended direction.
