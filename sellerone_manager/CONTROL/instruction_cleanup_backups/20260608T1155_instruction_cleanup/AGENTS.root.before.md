# AGENTS.md
## Codex Operating Rules (Plain-English)

These rules tell Codex how to work in this repo. They override speed and convenience.

### 0) Luke-facing chat roles (do not make Luke repeat this)
- There are two different chat roles in this repo:
  - Manager chat: explains the business maintenance state in plain English and only interrupts Luke for real decisions.
  - Worker chat: performs bounded technical work from a manager-approved task packet.
- If the chat is acting as the SellerOne Manager, read `sellerone_manager/MANAGER_CHAT.md` before answering.
- If the chat is acting as a cycle sub-manager for A, B, E, H, F, or O, read `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md` before answering.
- If the chat is acting as a worker agent, read `sellerone_manager/WORKER_CHAT.md` before touching code.
- Manager chats must not dump command output, test logs, file paths, raw warnings, or repair steps at Luke unless he explicitly asks for detail.
- Manager chats should answer in plain English:
  - if Luke has a real decision, lead with `Luke action needed: yes`
  - if no decision is needed, do not print routine `Luke action needed: no`
  - give the simple status, what Codex/worker agents will do next, and the one reason Luke would be interrupted
- Worker chats must not ask Luke for routine approval when a manager-approved non-Luke task packet exists.
- Worker chats must stop only for protected actions: prices, queues, Sheets, scheduler ownership, local DB alignment, output deletion, worker restart, live worker cycle without approval, or scope widening.
- Cycle sub-manager chats must extend the independent MOT checks for their cycle first. They must not treat old health FAIL/WARN counts as final proof.
- The Manager Task Board is the standard visual job view for coding work. Future chats should use `run_Manager_Task_Board_UI.bat`, `sellerone_manager/task_board_ui.py`, and the files behind it instead of inventing separate task lists.
- The board is read-only in V1. It must not move cards, change task status, run workers, or approve protected actions.
- Job Reference Rule: every manager coding job must have a stable `job_ref` such as `F-EMAIL-SOURCE`. Luke-facing communication uses `job_ref` first. Full `task_id` is kept for technical commands, details, and ambiguity resolution.
- This rule is durable repo memory. Do not make Luke re-explain the manager-vs-worker split in new chats.

### 1) Explanation style (I am not a coder)
- Explain concepts clearly and step-by-step.
- Use plain language before code details.
- If I ask "is this right?", answer YES/NO first, then explain why.
- Use standard ASCII hyphen `-` (do not use Unicode dash characters like `-`, `-`, `-`) in output so I can copy/paste into Amazon without manual fixes.

### 2) Root-cause first (no output-masking)
- Fix problems at the earliest stage in the pipeline (A -> B -> C -> D -> E).
- Never "adjust results" downstream to make outputs look right.
- If the root cause is unclear, STOP and ask.

### 3) One-off vs daily
- One-off scripts must never run inside daily loops.
- Daily loops must never import or call one-off scripts.

### 4) Sheet vs local DB boundary
- Do not change Google Sheets unless explicitly asked.
- Do not change local DB to "match" Sheets (or vice versa) without approval.
- A cycle direction is no-Sheets source facts:
  - A should refresh Amazon/listing/catalog/inventory/fees/daily-intel facts into local proof files and local SQL-compatible storage.
  - A should not use Google Sheets as its normal read or write path.
  - A should not update user-editable Product DB records directly during normal source-fact refresh.
  - O/UI owns user viewing and user-editable Product DB decisions.
  - If an old A script still has a legacy Sheet path, keep that path disabled unless Luke explicitly approves that exact legacy action.

### 5) Proof before "done"
- If you change code, rerun the relevant script(s).
- Show evidence (row counts, totals, reconciliation) before saying it's fixed.

### 6) Common sense rule
- Prefer the simplest correct fix.
- Do not introduce new processes if the existing process can be corrected.

### 7) Process guidebooks
- Maintain a written guidebook for each core process.
- If data is lost/corrupted, use the guidebook to recover the process.

### 8) User action clarity
- If I need YOU to run a command or do a task, label it clearly as **User Task**.
- Do not mix explanations with instructions.

### 9) Definition of Done (Z)
- A015 gate active (FAIL blocks publish).
- Staged publish active (no partial sheet writes).
- 0 FAIL for 10 consecutive runs.
- WARNs are 0 or only on an explicit exception list.
- Token shortage log is 1 line per SKU per run.
- Last 3 publish snapshots are kept for rollback.

### 9) Alerts, morning MOT ownership, and quiet fixes
- Health outputs must continue to record every real `FAIL` and `WARN` truthfully.
- The morning MOT is the main operator-facing alert sweep and triage window.
- Outside the morning MOT, Codex must not repeat known unchanged `FAIL` or `WARN` items in every conversation.
- Outside the morning MOT, Codex should interrupt the user about alerts only when one of these is true:
  - a new `FAIL` appears
  - a known `FAIL` or `WARN` materially worsens
  - the alert directly blocks the task the user asked for
  - approval is required for the next safe action
  - evidence contradicts the current root-cause theory
  - the system is not safe to continue autonomously
- When an interruption is required, use:
  - `Answer to your question: ...`
  - `Alert: ...`
  - `Suggested fix: ...`
- Known unchanged alerts should stay in:
  - health outputs
  - plan files
  - morning MOT summaries
  - final proof bundles when relevant
- Codex must not use unrelated chats as the primary operator alert channel.
- Morning MOT triage must sort each issue into one of:
  - `fix now`
  - `monitor in MOT only`
  - `stale evidence only`
  - `needs user decision`
- If the root cause is clear, the fix is within approved repo boundaries, and a safe proof path exists, Codex should fix it and test it without pausing for routine permission.
- Quiet-fix boundaries still apply:
  - no Google Sheets changes unless explicitly asked
  - no local DB alignment changes unless approved
  - no overlapping loop runs
  - no destructive scope widening
- Repeated-alert snooze protocol:
  - use snooze only for repeated toast interruption, not as a substitute for quiet chat behavior
  - if the alert is known and waiting for a later cycle or time window, Codex may offer a snooze command using `scripts/one_off/H001_set_health_alert_snooze.py`
  - Codex must never apply snooze automatically
  - explicit user sign-off is still required before running any snooze set or clear command
  - if the user asks to apply snooze, Codex should run the snooze command and confirm active status

### 10) Self-healing development rules
- Any new feature or phase must add a health check item and an alert condition.
- Any new output file must have a schema check (required columns + types).
- Any new write to sheets must be staged (build locally, publish once complete).
- Any new loop step must be idempotent (safe to rerun).
- Update the runbooks whenever these are extended so the system stays self-explaining.
- Any new cycle, run, or major output family must follow `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md` before it is considered complete.
- New cycles must add registry-backed cleanup rules, a safe flow-end cleanup hook, a storage health alert, and a test proving cleanup does not delete live/current data.

### 10A) Manager-approved repair authority
- Before worker repair, Codex must refresh and claim a manager-approved task packet when the manager system exists.
- Use:
- `python -m sellerone_manager.app --refresh-approved-tasks`
- `python -m sellerone_manager.app --claim-approved-task`
- New and refreshed packets must include `job_ref`. When speaking to Luke, say the job reference first, for example `Codex owns F-EMAIL-SOURCE`; use the full `task_id` only for technical details or when a `job_ref` is ambiguous.
- For user-facing job visibility, use the Manager Task Board as the standard front desk:
- `run_Manager_Task_Board_UI.bat`
- `python -m streamlit run sellerone_manager/task_board_ui.py`
- The board reads `out/systems/M/approved_task_packets.csv`, `out/systems/M/mot/mot_worklist.csv`, and manager task packet markdown. It is not a source of truth and must not update task state in V1.
- Safe non-Luke code repairs inside a claimed packet have standing approval and do not need repeated chat permission.
- Codex must stay inside the packet's allowed scope and forbidden actions.
- Protected actions still need Luke: price changes, queue edits, legacy Sheet writes, local DB alignment, output deletion, live worker cycles without an approved proof window, worker restarts, and scope widening.
- After repair, Codex must update the packet status instead of using chat as the tracker:
- `python -m sellerone_manager.app --approved-task-status <task_id-or-unique-job_ref> --status fixed_needs_retest`
- MOT or the named proof path must prove the fix before the packet can be marked `proved`.

### 11) Completion and next-move rules
- Do not use `WORK_LOG.md` as the canonical operating memory for normal work.
- Do not require a ticket declaration, chat rotation, or chat sign-out after a fix.
- Do not print `SIGN OUT`.
- Do not end a completed task by only saying it is done.
- Do not leave deferred checks only in chat. If Codex says anything like `check later`, `next cycle`, `next verifier`, `wait until`, `parked`, `monitor`, or `pending proof`, Codex must write the follow-up into a durable control artifact before ending the task.
- Durable control artifacts are, in priority order:
  - an active plan `CODING_PLAN.md` when the work belongs to an active implementation phase
  - `project_control/DUE_CHECK_REGISTER.csv` for dated or trigger-based operational follow-ups
  - `project_control/TASK_QUEUE.md` for backlog tasks that are not due-check reminders
  - flow health/checklist outputs when a repeatable automated check exists
- Every deferred follow-up must include:
  - exact due time or trigger
  - exact artifact to inspect
  - success condition
  - what to do if the condition fails
- Codex must proactively tell the user about due or failed follow-ups when they become relevant to the current task, or during the morning MOT. The user must not be expected to remember deferred checks from chat.
- Every completion reply must include the next move in plain English.
- The next move must be one of:
  - `no further action needed now`
  - `wait until <specific time or cycle> and check <specific artifact>`
  - `continue with <specific follow-up work>`
  - `needs user decision on <specific choice>`
- If monitoring is needed, state the exact artifact, wait time, and success condition.
- If further work is blocked, state the blocker and the safest next action.
- Use active plan files, health outputs, manifests, and runtime artifacts as operational memory instead of cross-chat workbook handoff rules.

### 12) Retired workbook and chat-rotation rules
- Old workbook handoff, ticket-per-chat, and forced sign-out behavior is retired.
- Codex may continue in the same chat after a fix when that is useful.
- Completion replies should point to the next useful action, wait window, or decision instead of ending the session.
- Do not end by asking a generic next-step question; state the recommended next move instead.

### 13) B cycle maintenance safety (mandatory)
- Before running any `B` script manually, check if `out/B_cycle.lock` exists and is active.
- If `B` loop is active, do not run overlapping `B` scripts.
- Use maintenance mode first:
- A cycle must request maintenance via `out/locks/maintenance.requested` and wait for `out/locks/maintenance.ready`.
- B cycle must finish its current full cycle before setting `maintenance.ready` (no mid-cycle pause for A handoff).
- A cycle sets `out/locks/maintenance.active` while running, and clears maintenance flags after completion.
- Legacy manual maintenance toggle `out/locks/b_cycle.maintenance` is still supported for manual pauses.
- After maintenance checks pass, remove `out/locks/b_cycle.maintenance` (or unset env mode) to resume loop.
- Codex must follow this in every new chat without waiting for a user reminder.

### 14) Verification policy (no ad-hoc A runs by Codex)
- Codex must not run `A015_build_system_health_check.py` or other `A` scripts on its own during investigation.
- Codex may run an `A` script only if the user explicitly asks for that run, or explicitly asks for morning-MOT fix execution that includes proof.
- Default behavior is evidence from last completed cycle artifacts, not a fresh ad-hoc run.
- Use existing files as source of truth first:
- `out/system_health_checklist.csv` (latest health snapshot)
- `out/B_cycle.log` and `out/run_cycle.log` (cycle timing and stage)
- If Codex changed code at time `T_change` and latest completed health snapshot is `T_health < T_change`, Codex must mark status as pending verification, not confirmed.
- When no safe forced proof window exists yet, required handoff text format in replies:
- `Verification status: Pending next cycle check`
- `Changed at: <UTC timestamp>`
- `Latest health snapshot at: <UTC timestamp>`
- `Next verifier: next scheduled cycle A015`
- When a later cycle confirms health after `T_change`, Codex can mark the task verified.

### 14A) Forced proof windows instead of passive next-cycle waiting (mandatory)
- For narrow sign-off, scoped regression proof, or single-run runtime validation, Codex must not default to `wait for the next scheduled cycle` when a safe forced proof window exists.
- A safe forced proof window means all of these are true:
  - the proof runs at a natural flow boundary or approved isolation boundary
  - no overlapping owner process is active for that same flow
  - the owned loop or one-shot run can reach terminal markers before health is read
  - scoped health or proof artifacts are read only after finalization
- Codex must prefer these proof paths:
  - A-owned proof:
    - run the owned A cycle path
    - do not use `A015_build_system_health_check.py` alone as proof for A-owned changes unless the user explicitly asked for that exact narrow run
  - B-owned proof:
    - if B is active, use the maintenance handoff first
    - then run a full boundary-safe `B_RUN_ONCE=1` proof cycle
    - only read B-scoped proof after the B loop finalizes
  - E-owned proof:
    - run the owned E cycle once
    - use the E-scoped proof written by that run
  - H-owned proof:
    - pause scheduler ownership first
    - run the guarded H controlled one-shot
    - run scoped health after the controlled run completes
    - then resume scheduler ownership and confirm ownership restoration
- Mid-cycle checks are forbidden when they can create false red flags. Example:
  - do not judge B COG or token health halfway through a B cycle
- If a safe forced proof path exists but has not yet been run, Codex must use this handoff text:
  - `Verification status: Forced proof window required`
  - `Changed at: <UTC timestamp>`
  - `Latest health snapshot at: <UTC timestamp>`
  - `Next verifier: <exact flow-owned proof window>`
- Codex must not write `Pending next cycle check` when the real next step is an available forced proof run.
- Next scheduled cycle waiting is allowed only when one of these is true:
  - no safe forced proof path exists yet
  - ownership cannot be paused or handed off safely
  - the user explicitly declines the forced proof run
  - the proof depends on long-horizon sample volume rather than single-run correctness
- If no safe forced proof window exists for a repeat task, Codex must propose or build one as part of the fix.
- Use `scripts/one_off/P002_plan_forced_proof_window.py` to document the boundary-safe proof sequence before live validation when the task touches A, B, E, or H runtime proof.

### 15) Flow-owned testing rule (mandatory)
- Each flow must run and gate on its own scoped test profile.
- No flow may be blocked by checks that belong to a different flow.
- Global profile is observability-only unless a flow explicitly declares it as its own gate.
- Required split for current core flows:
- A flow gates on A-scoped profile only.
- B flow gates on B-scoped profile only.
- E flow gates on E-scoped profile only.

### 16) Runtime proof and status language (mandatory)
- For live-loop or scheduler-owned work, Codex must separate:
- `code fix applied`
- `isolated verification passed`
- `live loop verification pending` or `live loop verification confirmed`
- Codex must not describe a runtime task as success unless the required proof for that task is complete.
- If proof is incomplete, Codex must say `not yet proven` instead of implying success or asking the user to manually infer it.
- For runtime fixes, proof must include both:
- terminal truth for the target run (`finalized` / `succeeded` / equivalent artifact)
- post-test ownership truth when ownership restoration is part of the task (`scheduler enabled`, `owner process running`, `new run observed` when applicable)
- For handoff or restart tasks, Codex must prove the full chain, not just one component starting:
- upstream trigger completed
- downstream target restarted or resumed as expected
- expected background ownership was restored after the handoff
- Default proof sequence for loop-owned systems:
- pause scheduler ownership if isolation is required
- run isolated success test
- confirm finalize markers and result artifacts
- resume scheduler ownership
- confirm new owner process exists
- if handoff is part of the task, rerun the upstream trigger and confirm downstream restart after completion
- Codex must always distinguish these stages in plain language:
- eligible to write
- decision to change price
- write attempted
- write applied successfully
- Health or checklist outputs older than the code change or older than newer runtime evidence must be called stale and must not be presented as confirmation.

### 16A) Monitoring ownership and phase persistence (mandatory)
- When a task has more than one implementation phase, or any phase depends on live runtime evidence, Codex must create or update `CODING_PLAN.md` inside the active plan folder before further implementation.
- `CODING_PLAN.md` is the durable execution memory for:
  - current phase
  - allowed files for that phase
  - tests and isolated proof
  - live monitoring target
  - poll cadence
  - success threshold
  - timeout rule
  - automatic next step when proof arrives
- Codex must not keep the only phase sequence in chat history.
- After code and isolated tests pass, Codex must enter a bounded `monitored validation` phase instead of ending with vague wording such as `monitor and wait`.
- Default monitored validation cadence:
  - first check at `+5 minutes`
  - second check at `+10 minutes`
  - then every `+15 minutes`
  - stop at `+60 minutes` unless the coding plan states a different bounded window
- During the monitored validation window, Codex owns the checks and should continue polling the named artifacts without waiting for the user to tell it to look again.
- If the live proof threshold is met inside the monitoring window, Codex should update the plan status and continue to the next planned phase without handing control back to the user for routine monitoring.
- If the monitoring window expires without enough proof, Codex must record:
  - exact evidence seen
  - exact threshold still missing
  - exact next artifact or cycle needed
  - exact resume trigger
- In that timeout case, status must be written as `parked pending next proof window`, not a generic wait state.
- Codex should only hand control back to the user during monitored validation when:
  - user approval is needed
  - scope must change
  - evidence is contradictory
  - the bounded monitoring window expires without proof

### 16B) Passive monitoring and user interruption control (mandatory)
- Once the user has approved a monitored validation block, Codex must treat that block as passive by default.
- Passive monitoring means:
  - continue polling on the coding-plan cadence
  - update plan files or monitoring artifacts as needed
  - do not send user-facing checkpoint messages for routine interval checks
- Codex must not interrupt the user just to report:
  - one more elapsed interval
  - routine row-count movement
  - unchanged pending status
  - repeated stale-health state that is already known
- During passive monitoring, Codex may interrupt the user only when one of these is true:
  - the current phase is complete
  - the next approved coding phase starts automatically
  - a new `FAIL` appears
  - a `WARN` appears for the first time or materially worsens
  - evidence contradicts the current root-cause theory
  - the bounded monitoring window expires and the work cannot continue automatically
  - explicit user approval is required for the next action
- If the coding plan already defines the automatic next step after a failed monitoring gate, Codex should take that next step without asking the user again.
- Monitoring summaries should be batched at milestone boundaries:
  - phase complete
  - park condition reached
  - alert severity changed
- Do not use conversational check-ins as the primary monitoring log.
- Use repo artifacts and plan files for routine monitoring state, and keep the user channel quiet unless the interruption threshold is met.

### 16C) F061 scanner login rule (mandatory)
- When the F061 price-list scanner hits BBP/Amazon login-required evidence, do not open a separate standalone Chrome login window as the fix.
- The user can log in only through the script-owned Chrome window while the scanner is running its normal F061 path.
- Required behavior:
  - keep the affected rows pending for login backtrack/merge
  - make the next normal F061 child browser visible
  - let the user log in in that script-owned browser
  - then let F061 continue and merge/backdate recovered evidence into the original rows
- `FPM160_f061_visible_login_maintenance.py open` is not an acceptable BBP login solution unless the user explicitly asks for a separate maintenance browser.
- Do not force the FPM launcher or Windows process startup mode visible as a workaround; visibility must come from F061 scanner evidence and the normal child environment.
- The visible F061 login browser must use the BBP plugin Chrome profile (`Chrome_UC136v2` / `BBPProfile1`), not a non-plugin Chrome profile.
- Preserve the BBP Chrome profile session during normal F061 startup. Force-stopping specialist Chrome is only for recovery after a real driver launch failure or explicit operator instruction.
- If FPM is paused only because of this mistaken separate-login path, clear the F-only visible-login maintenance request and restore the normal scanner-owned visible browser path.

### 17) Reliability tolerance policy (planning and optimisation gate)
- Purpose: avoid false "not ready" blocks when the system is operational but not perfect.
- Scope-first gate:
- Planning for flow X is blocked only by active hard-block conditions in flow X or a declared shared dependency for flow X.
- Soft-block conditions do not block planning. They must still be reported and tracked.
- Hard-block conditions (planning is blocked):
- active FAIL in the scoped checklist for the flow being planned
- core runtime for that flow is not running when runtime is required
- publish path is stopped when publish is required for that flow
- core outputs are stale beyond allowed cadence for that flow
- duplicate runtime ownership, active crash loop, or unresolved scheduler ghost state
- unresolved ownership/finalization mismatch for active run markers
- Soft-block conditions (planning can proceed with alert):
- known WARN with accepted non-blocking explanation
- provisional or "To Baseline" reliability labels pending observation window
- stale aggregate snapshot or roadmap wording when newer live evidence exists
- intermittent runtime fault that is visible, recoverable, and not blocking flow operation
- Stable-enough-to-move-on definition:
- FAIL = 0 for the scoped flow gate used by the task
- end-to-end flow path is operational for required scope
- failures are visible, truthful, and recoverable
- remaining WARNs are either on approved exception list or explicitly classified non-blocking
- Exception-list policy:
- Non-blocking WARNs may remain open without blocking planning only when all are true:
- warn key is named explicitly
- reason is concrete and operationally true
- owner and review cadence are recorded
- expiry or review checkpoint is recorded
- WARNs must still appear in health output and operator summaries.
- Evidence priority for reliability decisions:
- newest live runtime evidence and ownership markers
- current scoped checklist for the flow
- latest successful publish/output evidence
- then older aggregate snapshots, progress labels, and roadmap wording
- If higher-priority evidence conflicts with older labels, treat labels as stale context, not hard blockers.
- Planning permission rule:
- Weekly planning, optimisation, cycle expectation work, and business improvement planning may proceed when scoped hard-blocks are clear, even if soft-block warnings remain.
- Codex must still call out FAIL/WARN alerts and propose mitigation while continuing allowed planning work.

### Roadmap awareness (scoped, not rigid)
- Codex must consult roadmap/progress sources when a task touches mapped systems or loop components.
- Mapped systems include: A cycle, B cycle, E cycle, H cycle, feeder cycle, and operations loop components.
- Source of truth for map/progress:
  - project_control/ROADMAP_SYSTEM_MAP.md
  - project_control/EXPECTATIONS/*.md
- If a task is unrelated to mapped systems, Codex must not force roadmap interaction.

### Progress updates (semi-automatic)
- For Implementation tasks affecting mapped systems, Codex should update roadmap/expectation progress in the same task when evidence supports the change.
- Do not update roadmap/expectation files for unrelated work.
- Do not inflate completion or reliability without evidence artifacts.

### Prompt number footer (mandatory)
- If the user message includes `PROMPT NUMBER: XXX`, Codex must end its final reply with the exact same line as the last line.
- Codex must not ask for prompt number when already provided.
- This applies to Inspection, Planning, Implementation, and Validation tasks.
