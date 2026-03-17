# Decisions

## Purpose

This file records durable project and system decisions that are already supported by repo artifacts or explicit prior control reports. It should not be used for speculative ideas.

## Confirmed Decisions

### Governance

- `AGENTS.md` remains the active authority for Codex behavior until a deliberate migration says otherwise.
- `WORK_LOG.md` remains the canonical append-only audit trail and approved history ledger.
- `project_control/` is the intended permanent governance lane for project brief, architecture, current state, decisions, task queue, and guardrails.

### Data Source Authority

- B token live files under `out/systems/B/live/` are the intended canonical live source for the token datasets already classified in the authority report.
- Legacy `out/token_ledger_live.csv` and `out/token_allocations_live.csv` should be treated as mirror or fallback paths under the compat model rather than as the preferred live read target.
- Compat-mapped readers should resolve paths through the approved mechanism in `scripts/core/out_paths.py` instead of hardcoding legacy mirror reads for those datasets.

### Planning And Reporting

- `project_control/DATA_LINEAGE_REPORT.md` is the canonical reference for the current lineage map.
- `project_control/SOURCE_AUTHORITY_REPORT.md` is the canonical reference for current source authority classification.
- `project_control/CANONICAL_ENFORCEMENT_PLAN.md` is the canonical phased plan for source enforcement work.
- `project_control/GOVERNANCE_AUDIT.md` is the canonical audit of repo governance overlap and control-file ambiguity.

## Working Decisions Adopted From Governance Audit

- `NOTES.md` should be treated as a legacy backlog source and migrated into `project_control/TASK_QUEUE.md`.
- `APP_PLAN.txt` should be treated as reference material for project brief, architecture, and guardrails rather than as a parallel authority.
- `cycle_recovery_plan_v1.md` should remain a scoped operational recovery reference until its durable rules are promoted into maintained control docs or runbooks.

### H Operating Model

- `run_H_cycle.bat` is the approved operational launcher for H production starts.
- H production operation is a continuous self-relaunch service model, not a default one-shot launcher model.
- `scripts/cycles/run_H_pricing_cycle_guarded.py` remains required for production starts so exit, crash, phase, and heartbeat evidence survives child-process failures.
- One-shot H execution is maintenance-only and diagnostic-only. It must require an explicit signal such as `H_RUN_ONCE=1`, controlled mode, or a dedicated maintenance launcher.
- Task Scheduler may bootstrap or recover the H launcher, but it is not the normal cadence engine for each completed H child cycle unless a separate recurring schedule is explicitly approved and documented.
- Restart policy for the H operational launcher must be explicit and production-safe by default.

### Controlled Overnight Restart Policy

- Controlled overnight restart is approved as the replacement policy for unsafe hard shutdown behavior.
- Controlled restart is an architecture-level orchestration concern and must be implemented against existing lifecycle contracts, not as ad hoc script termination.
- The intended restart window is a quiet local-time window around 02:00 to 03:00.
- Restart is requested during that window and is not forced at a blind fixed cutoff.

### Controlled Restart Fail-Closed Decision

- Reboot approval must fail closed by default.
- Reboot is allowed only when safe idle/finalized state is positively proven from authoritative runtime artifacts.
- If safety proof is missing, stale, conflicting, or incomplete, reboot must be skipped and logged.
- Forced reboot is not normal controlled-restart behavior.

### Controlled Restart Contract-Reuse Decision

- Controlled restart must prefer existing lifecycle signals over parallel new mechanisms.
- Required reuse baseline:
- H controlled mode / run-once lifecycle controls and launcher ownership signals
- H boundary, result, lock, in-progress, finalized, heartbeat, and runtime-status artifacts
- A/B maintenance request-ready-active handoff markers
- Existing lock and marker families are the proof source for drain and approval checks unless an explicit approved gap is documented.

### Controlled Restart Blocker-State Decision

- Controlled restart must block reboot when any protected blocker state exists.
- Mandatory blockers include:
- H finalize-blocked states, including `FINALIZE_BLOCKED_NO_PUBLISH` class outcomes
- unresolved H ownership/finalization mismatch (`H_run_in_progress.txt` not safely released by finalized/archive contract)
- unresolved or ambiguous H boundary/result state for the owned run
- B maintenance not ready or B still actively processing without safe boundary proof
- B WARN/FAIL conditions where safe idle cannot be proven
- stale or conflicting lock/run-marker evidence that makes safety uncertain
- Policy for current known live faults:
- current H finalize-blocked behavior is not an acceptable reboot condition
- current B WARN behavior is not an acceptable reboot condition
- controlled restart must fail closed on these states until later approved gating proves safety

### Controlled Restart Orchestration-Stage Decision

- The required stage sequence is:
- restart request created
- loops stop starting new work
- active work drains to safe boundary
- orchestrator verifies safe state from authoritative artifacts
- restart approved or skipped
- reboot runs only when approved
- post-boot verification confirms expected services resumed
- Stage completion must be evidence-backed; no inferred success transitions.

### Startup-On-Boot Recovery Decision

- Startup-on-boot remains the approved recovery path after controlled reboot.
- Controlled restart must not replace normal startup ownership with a parallel post-boot launcher model.

### Scheduler Binding Validation Decision

- Inspection found scheduler-model ambiguity: control docs describe H scheduler usage as bootstrap/recovery while observed operations suggest repeated startup triggering.
- Before controlled restart implementation can be considered complete, implementation/validation must confirm real Windows scheduler task-to-entrypoint bindings for relevant startup loops.
- Reboot recovery assumptions must not be treated as validated until that binding check is completed and recorded.

### Controlled Restart Scope-Control Decision

- Controlled restart implementation must be narrow and reversible.
- Broad refactors are out of scope unless explicitly approved.
- Controlled restart must not change Google Sheets behavior.
- Controlled restart must not be used as a band-aid for unresolved runtime faults.

### Controlled Restart Observability Decision

- Controlled restart must produce durable auditable state evidence, including:
- restart requested
- drain in progress
- drain ready
- restart approved
- restart skipped
- post-boot verification result
- Observability must reflect real state; fake success states are forbidden.

### H And A016 Boundary Contract

- The H to A016 daily-intel subprocess boundary must have an authoritative run-scoped success or failure contract.
- A boundary is not considered resolved until H can point to explicit run-scoped evidence of one of:
- success payload accepted
- failure payload accepted
- timeout kill recorded
- unresolved-parent-exit recorded as a boundary failure
- `child_started` alone is not proof of boundary completion.
- `FINALIZE_BLOCKED_NO_PUBLISH` must not be the only visible outcome for an unresolved H to A016 boundary defect.
- Boundary-specific truth must be surfaced before or alongside finalizer failure so root cause is not masked downstream.

### A016 Output And Payload Ordering

- A016 must not be allowed to leave authoritative or staged daily-intel outputs without also leaving an authoritative boundary artifact for the same run.
- Core-output completion and boundary-result emission must be coupled by design.
- If full reordering is unsafe, boundary-result emission must be duplicated or checkpointed so H can still classify the run truthfully even when A016 exits abnormally after writing outputs.
- Missing payload with existing outputs is a boundary failure, not a success and not a publish-layer problem.

### H Boundary Failure Interpretation

- If H launches A016 and cannot later obtain a valid success or failure payload, H must classify that run as a boundary failure.
- H must emit an explicit H-side failure reason for:
- missing result
- invalid result
- child timeout
- child non-success payload
- unresolved parent exit while boundary is open
- Downstream finalizer and publish logic must treat unresolved boundary state as fail-closed and boundary-owned, not as a generic publish mismatch only.

### Launcher Overlap Rules For Boundary Children

- H launcher overlap protection must cover unresolved H-owned boundary child processes, not only the H parent process and launcher process.
- Restart gating must fail closed when the previous H run still has an unresolved A016 boundary, whether represented by:
- a live child process
- an unresolved boundary-state marker
- both
- Ownership for the H to A016 boundary must extend to the whole boundary, not end at H parent exit.

### Boundary Resolution Proof Artifacts

- The proof set for H to A016 boundary resolution must include run-scoped artifacts under `out/systems/H/live/`.
- The authoritative proof artifacts should include:
- boundary-state marker
- result payload file
- shared boundary progress checkpoints
- H-side watchdog enter and exit markers
- H-side unresolved-parent-exit marker when applicable
- Absence of these artifacts is not neutral. It is evidence of unresolved or failed boundary resolution.

### Parent Exit Before Boundary Resolution

- If the H parent exits before boundary resolution, the system must preserve explicit unresolved-boundary evidence for that run.
- Launcher cleanup must not archive or clear ownership in a way that makes the unresolved boundary invisible.
- A later H restart must be blocked until the unresolved boundary is either:
- resolved by child evidence accepted by policy
- or explicitly recovered by an approved recovery path

### H Finalization Ownership Rule

- H launcher ownership remains active until a run is explicitly finalized or explicitly archived by approved failure-path logic.
- Boundary state alone is not the ownership-release signal.
- A run with boundary state `resolved_failure` still blocks relaunch if that run is not the finalized run.
- `H_last_finalized_run_id.txt` is the authoritative release marker for normal run finalization.

### H Relaunch Blocking Rule For Failed Runs

- If `H_run_in_progress.txt` points to run `X` and `H_last_finalized_run_id.txt` does not point to `X`, launcher must fail closed for relaunch.
- Launcher must not clear or reuse the in-progress marker merely because run `X` has a boundary file whose state is `resolved_failure`.
- A run-scoped boundary file and/or run-scoped result payload for run `X` count as evidence that run `X` still owns cleanup/finalization.
- This rule applies even if the original H parent process is already gone.

### H Failure Cleanup Versus Ownership Release

- Nonzero H child exit is not sufficient authority to delete `H_run_in_progress.txt`.
- Lock archival, dead-pid cleanup, and evidence preservation are launcher cleanup actions.
- Ownership release for a failed run with boundary/result artifacts is a separate finalization/archive action and must be explicit.
- Until that explicit release happens, launcher must continue treating the failed run as ownership-active.

### H Failed-Run Archive Marker Decision

- Failed H runs must not reuse `H_last_finalized_run_id.txt` as their release signal.
- Normal finalization and failed-run archive are separate meanings and must use separate markers.
- The planned failed-run release marker is:
- `out/systems/H/live/H_failed_run_archived.<run_id>.json`
- This marker means:
- run `X` failed
- run `X` was reviewed and intentionally released
- run `X` may stop blocking relaunch
- This marker does not mean:
- success
- normal finalization
- publish completed

### H Failed-Run Archive Authority Decision

- The archive marker for a failed H run should be written by an explicit operator tool, not automatically by launcher, wrapper, or H core.
- The planned operator entrypoint is:
- `scripts/tools/archive_failed_H_run.py --run-id <run_id>`
- This keeps failed-run release deliberate, reviewable, and evidence-backed.

### H Failed-Run Archive Safety Decision

- Failed-run archive must fail closed unless all of these are true:
- `H_run_in_progress.txt` names the same run
- `H_last_finalized_run_id.txt` does not name that run
- no active H python or guarded-wrapper python process exists for the repo
- run-scoped boundary and/or result artifacts exist for that run
- The archive action must preserve boundary/result/wait evidence.
- The archive action must not be allowed to hide an active run.

### Home Time Mode Decision

- Home time mode is approved as a future unattended Codex mode for one active umbrella issue.
- Home time mode is a task-execution mode, not a runtime-ownership mode.
- Home time mode must operate inside existing runtime ownership contracts rather than replacing them.

### Home Time Mode Activation Decision

- Home time mode must require explicit operator activation.
- The preferred activation entrypoint is a dedicated tool such as:
- `python scripts/tools/start_home_time_mode.py`
- Activation must write a durable repo artifact describing the unattended session.
- Home time mode must not start implicitly from chat inactivity or absence of user replies.

### Home Time Mode Allowed Actions Decision

- During an active home time session, Codex may continue the current umbrella issue through:
- inspection
- planning
- implementation
- validation
- Codex may read control files, logs, manifests, health snapshots, status markers, runtime artifacts, and boundary evidence required to prove safety and continue work.
- Codex may make repo code and control-document changes that are otherwise allowed by the approved task scope.
- Codex may run narrow validation and test commands required by the active task, subject to existing flow-specific rules and existing restrictions on ad hoc A runs.
- Codex may use `scripts/tools/archive_failed_H_run.py` only when the tool's existing safety gates pass and the release is required for the unattended work.
- Codex may run controlled one-shot maintenance or diagnostic commands only when those runs preserve the standing production H service contract and do not create ambiguous ownership.

### Home Time Mode Forbidden Actions Decision

### H Runtime Restart Ownership Decision (PROMPT 022)

- One active restart authority at a time is mandatory for H.
- Normal-operation active owner: `run_H_cycle.bat`.
- Windows Scheduler role: bootstrap and recovery trigger only.
- Controlled restart gate/controller role: escalation-only orchestration for approved restart windows.
- Home time monitor role: observe and report, then escalate through approved ownership path.
- Parallel restart authorities are no longer allowed.

### H Windows-Tolerance Decision (PROMPT 022)

- H restart behavior must prioritize tolerance over rapid recycle.
- Relaunch cadence must include cooldown behavior after short failed runs.
- Lock and heartbeat stale thresholds must tolerate normal Windows session/scheduler jitter before cleanup.
- SIGBREAK/session interruption evidence must be handled as interruption-class events with reconcile windows.
- Parent-child mismatch must enter reconcile-hold state before any restart action is approved.

### H Failure Escalation Decision (PROMPT 022)

- One short failure:
- retain launcher ownership
- apply normal relaunch delay
- continue with warning evidence
- Repeated short failures in a burst:
- enter anti-churn cooldown
- suppress immediate rapid relaunch loops
- raise escalation signal for controlled restart evaluation
- Lock/heartbeat mismatch:
- hold and reconcile first
- stale cleanup only after tolerance window
- Scheduler refusal or session-interruption signal:
- classify as platform-interruption risk
- do not chain rapid restarts
- escalate to controlled restart decision path
- Reboot request conditions:
- reboot remains escalation-only and explicit
- no implicit reboot from observer-only layers

### H Anti-Churn Decision (PROMPT 022)

- Simpler control is preferred to stacked control.
- Ownership truth, boundary truth, and finalization truth are higher priority than quick recovery appearance.
- Any new H restart policy must show that it reduces restart churn and avoids duplicate authority actions.

- Home time mode must not stop H simply to hand control back to GPT or Luke.
- Home time mode must not clear `H_run_in_progress.txt` directly.
- Home time mode must not bypass `archive_failed_H_run.py` or write failed-run archive markers by any other path.
- Home time mode must not bypass maintenance-mode ownership rules or maintenance handoff readiness rules.
- Home time mode must not treat partial manifests, stale checklist files, stale markers, or partial run evidence as proof of success.
- Home time mode must not use chat history as the sole record of unattended work state.

### Home Time Mode Fail-Closed Decision

- If Codex cannot prove a safe ownership state from authoritative artifacts, home time mode must stop modifying the system.
- Safe ownership proof must be artifact-backed, not inferred from absence of obvious errors.
- Required fail-closed cases include:
- unresolved or ambiguous H boundary state
- active H run without approved ownership-release evidence
- failed-run archive conditions not satisfied
- active or ambiguous maintenance state
- missing, stale, or partial validation evidence being used as if current
- In these cases, Codex must leave a durable handoff artifact and mark the session blocked.

### Home Time Mode Handoff Artifact Decision

- Home time mode must write a durable handoff artifact whenever unattended work finishes, pauses, or blocks.
- The approved artifact family is:
- `out/systems/H/live/H_home_time_report.<timestamp>.json`
- The report must record at minimum:
- session id
- umbrella issue or ticket label
- tasks attempted
- files changed
- tests or validations executed
- current ownership state
- blocker or completion reason
- recommended next step
- evidence paths for review
- The handoff artifact is the authoritative unattended-work summary for Luke and GPT review.

### Home Time Mode Interaction Decision

- Home time mode must never override H controlled mode.
- Home time mode must never override B maintenance mode or future equivalent maintenance ownership controls.
- Home time mode must never override `run_H_cycle.bat` as the H production launcher.
- Home time mode must preserve the H continuous background-process model by default.
- Background-process preservation is part of the home time mode feature contract.
- If unattended work reaches a point where only stopping H would simplify handoff, home time mode must not do that and must instead leave a blocked handoff artifact.

### H Launcher Interpretation Of Failed-Run Archive Decision

- Launcher relaunch gating must continue to use finalized-run truth first.
- For a failed run, launcher may release ownership only when:
- `H_run_in_progress.txt = X`
- `H_last_finalized_run_id.txt != X`
- `H_failed_run_archived.X.json` exists
- When those conditions are met, launcher may clear `H_run_in_progress.txt` for run `X` and allow a fresh run.
- Launcher must not write `H_last_finalized_run_id.txt = X` for a failed archived run.
- `H_last_finalized_run_id.txt` remains the authoritative normal release marker for finalized-success runs only.

### H Layer Authority Decision

- A016 artifacts are the authoritative child-side truth for phase1-intel failure or success.
- H core and the guarded wrapper are responsible for surfacing truthful run outcome and boundary-aware finalizer evidence.
- The launcher is responsible for deciding whether another H run may start.
- During `phase1_intel`, H core is the authoritative parent token because A016 enforces `A016_PARENT_PID` from H core, not launcher pid and not wrapper pid.
- Therefore:
- child failure truth does not authorize relaunch by itself
- finalization markers authorize ownership release
- launcher gating must use finalization truth first and boundary/result artifacts as blocking evidence

### H Core Parent-Liveness Decision

- The `phase1_intel` subprocess wait in `scripts/cycles/run_H_pricing_cycle.py` is a protected ownership window.
- H core must remain alive while A016 is running until one of these explicit outcomes occurs:
- child completion and payload classification
- timeout kill and timeout classification
- controlled shutdown with durable evidence
- controlled failure path with durable evidence
- Silent disappearance of H core during this wait window is a runtime defect.
- Because A016 watches H core pid through `A016_PARENT_PID`, this defect must be hardened primarily in H core rather than in launcher policy or wrapper-only logic.

### H Core Wait-Path Evidence Decision

- If H core exits during the protected `phase1_intel` wait window, the system must preserve enough evidence to distinguish:
- controlled shutdown
- handled internal failure
- external termination or interruption
- unexpected disappearance while the A016 child is still running
- Launcher heartbeat staleness is not by itself sufficient evidence for that distinction because launcher heartbeat is only guaranteed at loop-entry and postchild checkpoints.
- The next implementation must therefore add or strengthen evidence in the H core wait path itself.

### H Secondary Launcher Residency Decision

- The observed stale persistent launcher residency after child death is a real but secondary H issue.
- Launcher ownership/finalization correctness is already the approved and completed prerequisite.
- The next implementation focus is H core parent-liveness hardening during `phase1_intel` wait, mainly in `scripts/cycles/run_H_pricing_cycle.py`.
- Launcher-residency tuning remains follow-on work unless a minimal coupled change is required only to support H core wait-path evidence.
- No SP-API work is included in this decision scope.

### Downstream Finalizer Policy For Unresolved Boundary States

- Publish, completed-marker, and finalizer checks must interpret unresolved H to A016 boundary state as a boundary failure first.
- Finalizer checks may still report publish mismatch, but they must not be the first or only failure surfaced for this defect class.
- The exit code for unresolved boundary states should remain truthful to the boundary failure class so launcher and operators can distinguish:
- publish not reached because boundary failed
- publish failed after boundary success
- finalizer mismatch after otherwise successful publish

### Repricer Governance

- The live repricer is the H flow and its current production behavior is governed through the H runtime plus the implemented `scripts/phase1/` stack.
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md` is the current repricer runtime-contract reference until a later approved control-file migration replaces it.
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md` is the target repricer architecture reference, not the current live runtime contract.
- `out/process_guides/repricing_tool/master plans/Phased execution/phase_1.md` and its related Phase 1 execution records are implementation-history and reference documents, not the current runtime contract, because the live repricer has already moved beyond single-SKU Phase 1 scope.
- Older repricer strategy-step versions and older masterplan versions should be treated as archive/reference-only unless specific content is deliberately promoted.

### Repricer Runtime Position

- The repricer has moved beyond single-SKU operation and currently runs against active-merchant scope with parked and stock filtering.
- The current repricer governance must distinguish three lanes:
- current live repricer contract
- target repricer architecture
- deferred future ideas
- Repricer planning and conflict cleanup should be tracked in `project_control/*` rather than left only inside repricer process-guide files.
- `project_control/REPRICER_RUNTIME_CONTRACT.md` is the control-file authority for describing the live repricer as it actually runs today.

### Repricer Conflict Cleanup Priorities

- The following repricer conflicts require planning cleanup before further feature expansion:
- single-SKU Phase 1 wording versus multi-SKU live reality
- v1.3 runtime-contract wording versus v10 target-architecture wording
- stock-source priority wording drift
- ceiling fallback and CPT wording drift
- writer-mode and config authority ambiguity
- file naming and terminology drift between plan docs and implemented tables/artifacts
- outdated suppression fallback wording in `strategy-steps-v1.3.md` versus the current suppression code path

### Suppressed Buy Box Fallback Planning Decision

- Suppressed Buy Box fallback completion is approved as an incremental completion of the current live repricer contract, not as a broad architecture redesign.
- The planned current-contract policy order is:
- direct suppression target first
- then learned threshold when confidence is sufficient and fresher direct evidence is absent
- then competitor-inferred upper bound when Buy Box is suppressed and no Buy Box offer exists
- then carry-forward temporary suppression ceiling when still valid
- then bounded downward probing
- The planned current-contract completion must add:
- retry-budget and cooldown rules
- stop and re-entry rules
- resolved-state audit logging
- persisted ceiling reclamping to anchor-floor governance
- Broader suppression intelligence, notifications, and portfolio-aware suppression handling remain deferred.

### A Cycle Manifest Truth Model

- The A manifest must be treated as the execution truth for that cycle, not as a best-effort summary.
- A manifest step must distinguish at least:
- launched
- child completed
- outputs verified
- policy-skipped
- failed
- A step with `rc=0` must not be interpreted as full success unless required outputs were also verified.
- Manifest finalization must record configured step count and actual traversed counts so partial traversal is explicit.
- A cycle that does not traverse the full configured step list must not finalize as successful.

### A Required Output Verification Rules

- A-step outputs must be classified as required or optional at the orchestrator layer.
- Required outputs must be verified after each step before the step is marked successful.
- Verification must prove existence and current-run freshness.
- If a child returns `rc=0` but required outputs are missing or stale, the step result is a failure, not a warning and not a success.
- For blocking A steps, required-output verification failure must stop the cycle immediately.
- Non-blocking behavior is allowed only for explicitly documented exception cases and must be represented as degraded or skipped, not ordinary success.

### A015 And Health Artifact Freshness Rules

- `out/system_health_checklist.csv` and any A-split checklist must not be treated as current-cycle evidence unless they are freshly written by the current A-cycle A015 execution.
- File existence alone is insufficient. Current-cycle evidence must be bound to the current cycle by freshness at minimum, and preferably by run-linked metadata.
- If the latest available checklist predates the current A cycle, the A cycle health state must be recorded as stale or unverified rather than healthy.
- A015 must treat a partial A manifest as failed or degraded current-cycle evidence, not as a clean completed A run.

### A015 And A016 Shared Required-SKU Derivation Decision

- Problem being solved:
- false daily-intel coverage FAILs can appear when A015 and A016 evaluate required non-parked in-stock SKUs from non-identical local derivation paths or from mixed-freshness artifacts.
- Why false coverage FAILs occurred:
- partial A traversal can leave scope refreshed while daily-intel rows are not refreshed for the same operational window
- stock-source precedence drift between A015 and A016 can produce different required-SKU sets
- genuine health checks then receive inconsistent eligibility inputs
- Decision:
- A015 and A016 must use one shared required-SKU derivation implementation.
- Canonical required-SKU rule:
- source scope is `out/phase1_sku_scope.csv`
- SKU must be non-parked after parked overrides
- SKU must have stock quantity greater than zero
- Canonical stock-source precedence order:
- latest `out/inventory_snapshot_*.csv`
- `out/inventory_summaries.csv`
- `out/parking/stock_snapshot_latest.csv`
- Why shared logic is chosen over separate local logic:
- separate local logic allows silent drift under normal maintenance edits
- a shared helper keeps eligibility semantics stable and inspectable
- a shared helper reduces repeated bug surface and makes root-cause debugging deterministic

### A015 Daily Intel Freshness Prerequisite Decision

- A015 must evaluate a freshness prerequisite before daily-intel coverage and compliance checks.
- If freshness is not satisfied, A015 must emit a dedicated prerequisite-style failure.
- In that stale-prerequisite state, A015 must not emit false missing-SKU coverage/compliance failures.
- Why freshness gating is preferred:
- it is fail-closed and explicit
- it preserves diagnostic truth instead of masking drift as business failure
- it avoids orchestration-only masking that can hide the root cause
- silent pass-through is explicitly rejected because it suppresses operational risk visibility

### Scope And Non-Goal Decision For This Change

- This change does not alter pricing strategy, repricing behavior, suppression policy, or other business repricing rules.
- This change is limited to eligibility consistency and health diagnostic trustworthiness for daily-intel checks.
- Genuine daily-intel failures remain genuine failures and must still surface as FAIL.

### A Daily Intel Operational Sequencing Decision

- Trusted daily-intel health interpretation requires full A-cycle progression through `A016_refresh_phase1_daily_intel.py` and then `A015_build_system_health_check.py`.
- Partial A runs may leave mixed-freshness scope and intel artifacts and must be interpreted accordingly.
- Operational recovery for this issue class should prioritize a clean full A completion before interpreting new coverage/compliance outcomes.

### A Traversal Enforcement

- `scripts/cycles/run_A_all.py` should hard-fail if the configured step list is not fully traversed, unless an explicit future design introduces a documented early-stop state that still finalizes as non-success.
- Reaching the manifest finalizer is not proof that the cycle completed.
- The finalizer must preserve partial/interrupted evidence, but it must not stamp a partial cycle as healthy or complete.

### Downstream Interpretation Of Partial A Cycles

- Downstream readers must interpret partial A manifests as incomplete production evidence.
- A partial A cycle may be useful for forensics, but it must not be accepted as proof that later A outputs, A015 status, or publish gates are current.
- Any consumer that needs "latest successful A cycle" must require:
- full configured traversal
- no blocking-step failure
- required outputs verified
- current-cycle A015 evidence verified

## Open Decisions Needed

- Confirm ownership of unresolved duplicate-truth datasets before broader rewiring outside the already-approved safe compat-mapped files.
- Confirm whether the older DB-centered architecture direction from `APP_PLAN.txt` is still an active product intention.
- Confirm what content should ultimately live in `project_control/OPERATING_SYSTEM.md` versus staying solely in `AGENTS.md`.

## Implementation-Ready Plan

- Files likely to need code changes:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/cycles/run_H_pricing_cycle_guarded.py`
- `run_H_cycle.bat`
- optional small helper additions if boundary-state parsing is shared
- Recommended order of implementation:
- add run-scoped H boundary-state markers and unresolved-parent-exit evidence
- make H boundary failure classification explicit and boundary-specific
- couple A016 output completion with authoritative payload/result emission
- extend launcher restart gating to block on unresolved boundary children and unresolved boundary-state markers
- add conservative stale-orphan recovery logic for unresolved boundary states
- Validation approach:
- one normal H run proving `child_started`, `subprocess_done`, `payload_check`, `decision`, and publish markers
- one forced child failure proving failure payload and `boundary_failure`
- one forced timeout proving watchdog kill evidence and truthful timeout classification
- one forced parent-exit-during-wait test proving unresolved-boundary evidence survives and restart is blocked
- one overlap test proving no new H run starts while the previous A016 boundary remains unresolved
- Rollback and safety considerations:
- implement additively first with new markers before removing any old checks
- preserve existing logs, result paths, and staged-output locations
- keep fail-closed behavior for unresolved boundary states
- avoid silent cleanup of unresolved markers so recovery remains evidence-backed
