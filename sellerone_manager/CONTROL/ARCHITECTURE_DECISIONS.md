# SellerOne 2.1 Architecture Decisions

This file is the Architect layer.

It is not an automation, bot, or scheduled manager. It records major control-system decisions so the reason is still visible months later.

## ADR-0001 - SellerOne 2.1 Is Control Desk Stabilisation

Date: 2026-06-08

Decision:

- Treat SellerOne 2.1 as a control-layer stabilisation project, not a business-system rewrite.

Reason:

- The live issue is not one broken feature. SellerOne has accumulated several generations of manager prompts, task stores, automation loops, health outputs, and chat rules.
- The safest next step is to collapse the control layer into one operating model before doing more feature work.

Alternatives rejected:

- Call it SellerOne 3.0 and start a broad rewrite.
- Continue adding cycle managers and heartbeat automations.
- Fix only F login and leave the wider control drift untouched.

Owner:

- Luke

Review trigger:

- After `SO21-CONTROL-INVENTORY` and `SO21-QUEUE-CONTRACT` are complete.

## ADR-0002 - Four Visible Roles

Date: 2026-06-08

Decision:

- SellerOne 2.1 has four visible roles: Rep, Builder, Reviewer, and Custodian.
- Dispatching is an internal queue function, not a visible role.

Reason:

- A visible Dispatcher adds another personality and another place for state to drift.
- The Rep should decide what enters the queue, and the queue contract should decide what is ready.

Alternatives rejected:

- Visible Dispatcher role.
- Manager-per-cycle role tree.
- Manager, Sub Manager, Micro Manager, Cycle Manager, and Worker Manager hierarchy.

Owner:

- Luke

Review trigger:

- If the Rep becomes too overloaded or if ticket routing becomes ambiguous after the queue contract is live.

## ADR-0003 - Human State Beats Machine Snapshot

Date: 2026-06-08

Decision:

- `sellerone_manager/CONTROL/CURRENT_STATE.md` is the official human-readable state snapshot.
- `sellerone_manager/current_state.json` remains machine support only and must not outrank newer MOT evidence.

Reason:

- `current_state.json` can drift behind newer MOT output.
- Luke needs a state file that can be opened and understood directly.
- Machines can still use JSON underneath, but the human-facing control desk needs Markdown.

Alternatives rejected:

- Keep `current_state.json` as the official state.
- Use chat memory as state.
- Use the Task Board as source of truth.

Owner:

- Luke

Review trigger:

- When a generator exists for `CURRENT_STATE.md`, or if the Markdown and evidence disagree.

## ADR-0004 - Approved Task Packets Are The Canonical Queue Candidate

Date: 2026-06-08

Decision:

- Approved task packets are the leading candidate for the canonical engineering queue.
- The inventory will verify this before the queue contract is finalized.

Reason:

- The packet system already carries bounded scope, proof, job references, allowed actions, and protected boundaries.
- It is more mature than free-form chat, old work logs, or board-only state.

Alternatives rejected:

- Manager Task Board as source of truth.
- `WORK_LOG.md` as source of truth.
- Prompt folders as live queue.
- Chat history as live queue.

Owner:

- Luke

Review trigger:

- During `SO21-QUEUE-CONTRACT`.

## ADR-0005 - Custodian Owns Lifecycle Discipline

Date: 2026-06-08

Decision:

- Custodian owns disk, tokens, logs, archives, temp files, old outputs, stale packets, dead automations, dead schedulers, and stale locks.

Reason:

- SellerOne has historically built faster than it has cleaned.
- The 700GB to 50GB cleanup signal means lifecycle policy is missing, not just overdue.
- Storage, tokens, dead jobs, and stale artifacts need one owner.

Alternatives rejected:

- Treat storage cleanup as occasional manual housekeeping.
- Let each cycle own its own cleanup rules with no central policy.
- Allow silent deletion without retention classes.

Owner:

- Luke

Review trigger:

- Before any cleanup automation is re-enabled.

## ADR-0006 - Automations Stay Paused During 2.1 Inventory

Date: 2026-06-08

Decision:

- Codex app automations stay paused while SellerOne 2.1 inventory and queue contract work is performed.

Reason:

- The current purpose is to map the control system, not add more background movement.
- Paused automations prevent old manager roles from continuing to write state while the new model is being defined.

Alternatives rejected:

- Leave old heartbeat managers running during the inventory.
- Immediately rebuild the automation set before the queue contract exists.

Owner:

- Luke

Review trigger:

- After `SO21-CONTROL-INVENTORY`, `SO21-QUEUE-CONTRACT`, and the initial Custodian policy are complete.

## ADR-0007 - Rep And Operations Are Separated

Date: 2026-06-08

Decision:

- Rep and Operations are separated.
- Rep is conversational and Luke-facing.
- Operations is a back-office evidence/reporting function.
- Luke does not talk directly to Operations.
- Rep reads Operations reports and turns them into queue decisions or plain-English status.

Reason:

- Raw automation, MOT, storage, token, scheduler, and stale-lock evidence should not spill directly into Luke-facing chat.
- The Rep should remain the front desk.
- Operations should produce reports and ticket candidates, not become another visible manager hierarchy.

Rep owns:

- conversation with Luke
- planning
- ticket creation
- status explanation
- deciding what enters the queue

Operations owns:

- reading automations
- reading MOT
- reading storage reports
- reading token reports
- reading scheduler/lock reports
- creating operational ticket candidates
- producing summaries for the Rep

Alternatives rejected:

- Let Rep read raw automation noise directly every time.
- Create a visible Operations Manager chat.
- Let automations speak directly to Luke as routine status.

Owner:

- Luke

Review trigger:

- When `SO21-CUSTODIAN-POLICY` and `SO21-AUTOMATION-REBUILD` are designed.

## ADR-0008 - Custodian Cleanup Is Manifest-First

Date: 2026-06-08

Decision:

- SellerOne cleanup must be manifest-first and approval-gated.
- The Custodian may measure, classify, report, and produce dry-run cleanup manifests without changing business runtime.
- Destructive cleanup needs an exact manifest, protected-file exclusions, a recovery route, and explicit approval when protected data or runtime evidence could be touched.

Reason:

- The 2026-05-25 emergency cleanup estimated 667.123 GB of removable buildup.
- That proves SellerOne had a missing lifecycle, not just a one-time storage problem.
- Future cleanup must be repeatable and boring instead of urgent and risky.

Alternatives rejected:

- Letting each worker clean up its own historical outputs without a shared policy.
- Deleting old files based only on age or folder name.
- Treating `out/` as one cleanup bucket even though it contains live runtime files and proof.
- Restarting storage automations before the policy and queue are stable.

Owner:

- Luke owns the decision.
- Custodian owns measurement, reports, manifests, and policy compliance.
- Rep owns converting cleanup recommendations into queue tickets.

Review trigger:

- Before the first SellerOne 2.1 cleanup apply run.
- Any time a cleanup proposal touches live runtime files, task packets, backups, databases, lock files, or business evidence.

## ADR-0009 - Current Tickets And Backlog Are Generated Views

Date: 2026-06-08

Decision:

- `CONTROL/CURRENT_TICKETS.md` is the human-readable active Builder and Reviewer queue view.
- `CONTROL/BACKLOG.md` is the human-readable view for Luke-blocked decisions, parked work, MOT candidates, and 2.1 control follow-ups.
- Both files are generated from packet and MOT evidence.
- They are read-only views and must not move task packets or approve protected actions.

Reason:

- The packet index is accurate but too noisy for Luke-facing planning.
- Active work must not be mixed with parked history, Luke decisions, or raw MOT candidate rows.
- A generated view gives Luke a simple front desk without making chat memory the source of truth.

Alternatives rejected:

- Hand-writing the active work list from chat.
- Treating MOT worklist rows as active work before packet promotion.
- Showing all proved history as current work.
- Letting the Manager Task Board become the queue source of truth.

Owner:

- Luke owns the queue decisions.
- Rep owns the plain-English view.
- Builders and Reviewers still work from approved packet boundaries.

Review trigger:

- When the queue contract changes.
- When the Task Board or Manager Briefing starts reading these control files.
- When new statuses are added to approved task packets.

## ADR-0010 - Instructions Route Through The 2.1 Control Model

Date: 2026-06-08

Decision:

- Root `AGENTS.md` and manager `AGENTS.md` are short bootstraps.
- Detailed role routing lives in `CONTROL/ROLE_BOOTSTRAP.md`.
- Detailed runtime safety lives in `CONTROL/RUNTIME_SAFETY_RULES.md`.
- Current work lives in `CONTROL/CURRENT_TICKETS.md` and `CONTROL/BACKLOG.md`.
- Old plans, prompt folders, and chat history are context only.

Reason:

- SellerOne was carrying several generations of instruction methods at once.
- Future Codex chats need one front door, not a pile of overlapping rulebooks.
- The short bootstrap keeps startup fast while preserving safety detail in durable control files.

Alternatives rejected:

- Keeping every detailed rule repeated in every chat role file.
- Deleting old rulebooks without backup.
- Making `CODING_PLAN.md` or chat history the current operating memory.
- Moving to automations before the instruction source of truth was clear.

Owner:

- Luke owns the operating decision.
- Rep owns the readable instruction model.
- Custodian owns future instruction lifecycle cleanup.

Review trigger:

- Before trimming `MANAGER_CHAT.md`, `WORKER_CHAT.md`, or `CYCLE_SUB_MANAGER_CHAT.md`.
- When a new repeat workflow becomes a skill or template.
- When automations are rebuilt.

## ADR-0011 - AI Usage Reporting Starts With Usage Pressure

Date: 2026-06-08

Decision:

- `CONTROL/AI_USAGE.csv` and `CONTROL/AI_USAGE.md` track AI usage pressure first.
- The report must not pretend to know pounds, dollars, model billing, or real token spend until a real billing or token-spend source is connected.
- Business stock-token and token-ledger data is excluded from AI usage accounting.

Reason:

- The control desk currently has evidence for repeated loops, oversized instruction files, stale prompt folders, active tickets, MOT pressure, and automation count.
- It does not yet have a reliable local source for real AI billing or token cost.
- A pressure report is still useful because it shows where AI time is most likely being wasted before a real cost feed exists.

Alternatives rejected:

- Guessing costs from file size, ticket count, or chat activity.
- Mixing business stock-token data with AI billing language.
- Waiting for perfect billing data before reducing obvious AI usage pressure.

Owner:

- Luke owns cost decisions.
- Custodian owns measurement and reporting.
- Rep owns turning usage pressure into queue tickets.

Review trigger:

- When a real Codex/OpenAI billing, model-usage, or token-spend source is connected.
- Before any automation restarts based on usage-report output.

## ADR-0012 - Legacy Coding Plan Is Archived, Not Active Memory

Date: 2026-06-08

Decision:

- The oversized legacy `sellerone_manager/CODING_PLAN.md` is no longer active operating memory.
- The historical contents are preserved in `sellerone_manager/CONTROL/CODING_PLAN_ARCHIVE.md`.
- The live `sellerone_manager/CODING_PLAN.md` is now a short pointer to the SellerOne 2.1 control files.

Reason:

- The old plan was still focused on the F login weekend work and was large enough to create avoidable AI context pressure.
- SellerOne 2.1 current work now belongs in approved task packets plus generated control views.
- Archiving keeps the evidence without forcing every future chat to load old implementation history.

Alternatives rejected:

- Deleting the old plan.
- Leaving the old F login plan as active memory.
- Splitting the old plan across more live chat files.

Owner:

- Luke owns the operating decision.
- Rep owns the live control front door.
- Custodian owns the archive and future plan lifecycle.

Review trigger:

- If historical F login evidence is needed for a future repair.
- Before any further live plan file is created outside the approved queue and control views.

## ADR-0013 - Old Prompt And Plan Folders Are History Or Templates

Date: 2026-06-08

Decision:

- Old prompt and plan folders are marked as history/template material, not live control memory.
- The marker is `sellerone_manager/CONTROL/PROMPT_FOLDER_ARCHIVE.md`.
- Folder contents were not moved or deleted.

Reason:

- The `plans` folder and manager prompt folders were still large enough to create avoidable AI context pressure.
- SellerOne 2.1 already has live sources for current state, current tickets, backlog, queue contract, and architecture decisions.
- Keeping old prompts available as reference is useful, but treating them as current instructions creates duplicate control systems.

Alternatives rejected:

- Deleting prompt and plan folders.
- Moving them before a full storage policy dry run.
- Continuing to let old prompt folders compete with the approved queue.

Owner:

- Luke owns whether any historical prompt should become a modern reusable workflow.
- Rep owns live task intake from current control files.
- Custodian owns the archive marker and future prompt-folder lifecycle.

Review trigger:

- During `SO21-SKILL-SPECS`.
- Before any prompt folder is deleted, compressed, or moved by a Custodian cleanup manifest.

## ADR-0014 - Role Files Are Short Front Doors

Date: 2026-06-08

Decision:

- `MANAGER_CHAT.md`, `CYCLE_SUB_MANAGER_CHAT.md`, and `WORKER_CHAT.md` are short role front doors.
- `MANAGER_PROGRESS_TRACKER.md` is no longer active progress memory.
- Detailed shared rules live in `CONTROL/ROLE_BOOTSTRAP.md` and `CONTROL/RUNTIME_SAFETY_RULES.md`.
- Current progress lives in generated control files and task packet evidence.

Reason:

- The old role files repeated manager rules, worker rules, task board rules, safety rules, proof rules, and historical state.
- That made future chats load too much old context before reading current evidence.
- SellerOne 2.1 needs role files to route the chat, not carry every old operating layer.

Alternatives rejected:

- Keeping long role files as live memory.
- Deleting historical role detail.
- Moving role rules back into chat-only instructions.

Owner:

- Luke owns the operating decision.
- Rep owns role routing.
- Custodian owns role-file lifecycle and backups.

Review trigger:

- During `SO21-SKILL-SPECS`.
- If a future chat cannot identify its role from the shortened front-door files.

## ADR-0015 - Repeat Workflows Become Skill Specs Before Automations

Date: 2026-06-08

Decision:

- SellerOne repeat workflows are written as skill or template specs before any automation rebuild.
- The specs live in `sellerone_manager/CONTROL/SKILL_SPECS.md`.
- The specs are design recipes, not installed automations.

Reason:

- SellerOne had repeated workflow instructions spread across role files, prompt folders, plans, and automation prompts.
- Rebuilding automations before stable recipes would recreate the old overlap.
- Skill specs give Builders, Reviewers, Rep, Custodian, MOT promotion, automation rebuild, and storage indexing a shared shape.

Alternatives rejected:

- Rebuilding automations immediately after trimming role files.
- Letting each future chat infer its own workflow from old prompt history.
- Installing new Codex skills before the specs are reviewed.

Owner:

- Luke owns which specs become installed skills or automations.
- Rep owns using specs for future task shaping.
- Custodian owns keeping unused specs from becoming another stale control layer.

Review trigger:

- Before `SO21-AUTOMATION-REBUILD`.
- Before converting any spec into an installed Codex skill or recurring automation.

## ADR-0016 - Out Folder Cleanup Requires Subtree Classification First

Date: 2026-06-08

Decision:

- The mixed `out/` folder is classified by top-level subtree before any cleanup manifest is proposed.
- The subtree index lives in `sellerone_manager/CONTROL/STORAGE_INDEX_OUT_SUBTREE.csv`.
- The readable summary lives in `sellerone_manager/CONTROL/STORAGE_INDEX_OUT_SUBTREE.md`.
- Cleanup is still not approved.

Reason:

- `out/` contains live runtime areas, SQL, locks, proof history, reports, backups, temp folders, and top-level mixed files.
- Treating `out/` as one cleanup bucket would be unsafe.
- The subtree index separates protected live areas from possible dry-run cleanup candidates.

Alternatives rejected:

- Bulk cleanup of `out/`.
- Deleting temp-looking folders before an active-owner check.
- Treating `out/systems`, `out/sql`, `out/locks`, or `out/parking` as cleanup candidates.

Owner:

- Custodian owns classification and dry-run manifests.
- Luke owns approval for any destructive cleanup.

Review trigger:

- Before `SO21-CUSTODIAN-DRY-RUN-MANIFEST`.
- Before any cleanup action touches `out/`.

## ADR-0017 - Dry-Run Cleanup Manifest Is Preview Only

Date: 2026-06-08

Decision:

- `CONTROL/CUSTODIAN_DRY_RUN_MANIFEST.csv` and `.md` are preview-only cleanup planning files.
- They may classify paths, proposed actions, approval requirements, protected exclusions, rules, and recovery routes.
- They are not approval to delete, move, compress, purge, archive, or quarantine files.

Reason:

- SellerOne needs to see possible cleanup material without risking live runtime proof, locks, SQL, task packets, or business evidence.
- The first 2.1 cleanup step must prove the no-touch boundary before any apply workflow is designed.
- A dry-run manifest gives Luke a readable future approval list while keeping all files in place.

Alternatives rejected:

- Applying cleanup directly after the `out/` subtree index.
- Treating `preview_purge_candidate` or `preview_archive_candidate` as approval.
- Bulk cleanup of backup, proof, report, or temp folders without live-owner checks.

Owner:

- Custodian owns manifest generation and protected exclusions.
- Luke owns any future destructive cleanup approval.

Review trigger:

- Before any cleanup apply ticket.
- Before any automation is allowed to clean, archive, compress, purge, or quarantine storage.

## ADR-0018 - Windows Scheduler Is A Separate Automation Layer

Date: 2026-06-08

Decision:

- Codex app automations and Windows scheduled tasks are separate control layers.
- Pausing Codex app automations does not pause Windows scheduled tasks.
- SellerOne 2.1 automation rebuild must review both layers before any background control loop is trusted.

Reason:

- `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW` found 19 Codex app automations, all paused.
- The same review found ready Windows scheduled tasks for old runtime and manager paths.
- That means the control pause was incomplete at the OS scheduler layer even though the Codex app automation layer was quiet.

Alternatives rejected:

- Treating paused Codex app automations as proof that every background manager or scheduler is paused.
- Restarting or reusing old Windows scheduled tasks before the 2.1 queue and automation model decide their purpose.
- Silently disabling Windows scheduled tasks without a named Luke decision.

Owner:

- Luke owns any scheduler pause/disable decision.
- Custodian owns scheduler inventory and evidence.
- Rep owns converting scheduler findings into a plain-English decision.

Review trigger:

- Before any old scheduled task is disabled, deleted, edited, restarted, or replaced.
- Before `SO21-AUTOMATION-REBUILD`.

## ADR-0019 - Temporary Windows Scheduler Pause During 2.1 Stabilisation

Date: 2026-06-08

Decision:

- Luke approved a temporary Windows scheduler pause while SellerOne 2.1 management cleanup is completed.
- The pause applies to eight named ready scheduled tasks.
- The tasks were disabled, not deleted.

Reason:

- SellerOne was still able to move through Windows scheduled tasks even though Codex app automations were paused.
- The 2.1 control system needs a still background before automations are rebuilt deliberately.
- Disabling is reversible because each task was exported before the pause.

Tasks paused:

- `AMZ Controlled Restart`
- `AMZ H Cycle`
- `AMZ Morning MOT Post A`
- `AMZ Morning MOT Post Restart`
- `AMZ Orders`
- `AMZ Price List Manager`
- `AMZ Pricing Summary`
- `SellerOne Manager Hourly MOT`

Alternatives rejected:

- Leaving old Windows scheduler tasks ready during the management cleanup.
- Deleting scheduled tasks.
- Restarting or editing scheduled tasks before automation rebuild.

Owner:

- Luke approved the pause.
- Custodian owns rollback exports and pause proof.
- Rep owns explaining when automation rebuild is ready.

Review trigger:

- Before any paused scheduled task is re-enabled.
- During `SO21-AUTOMATION-REBUILD`.

## ADR-0020 - Automation Rebuild Is Plan-First And Paused-First

Date: 2026-06-08

Decision:

- SellerOne 2.1 automations must be rebuilt from the control model, not resumed from old automation IDs.
- New automations should be created paused first, then activated only after Luke approves the exact pilot behavior.
- The first proposed pilot is `SO21-REP-BRIEFING`.
- Windows scheduled tasks must stay disabled during the first automation pilot unless Luke approves a separate re-enable decision.

Reason:

- Old manager and cycle heartbeats created too much overlapping control noise.
- The queue, current state file, Operations report, Custodian policy, and architecture decisions now give a cleaner source for automation behavior.
- Paused-first creation keeps the system reviewable before any background work resumes.

Alternatives rejected:

- Re-enabling old Codex app automations because they already exist.
- Re-enabling Windows scheduled tasks during the automation rebuild.
- Creating several new automations at once before a single Rep briefing pilot proves useful.

Owner:

- Rep owns the activation decision.
- Custodian owns automation inventory and pause evidence.
- Luke owns approval to activate or re-enable any recurring automation.

Review trigger:

- Before creating or activating `SO21-REP-BRIEFING`.
- Before any old automation ID or Windows scheduled task is resumed.

## ADR-0021 - Worker Threads Must Not Fork The Rep Chat

Date: 2026-06-08

Decision:

- The SellerOne Manager project is the clean Luke-facing Rep chat.
- Noisy technical execution belongs in separate SellerOne 2.0 worker threads.
- Worker threads must start from the task packet and worker instructions, not from a forked copy of this Rep conversation.
- Forking this Rep chat is not the normal worker-start method because it copies management discussion into the worker context.

Reason:

- Luke needs one calm management front desk.
- Copying this conversation into a worker creates another muddy manager chat and repeats the old problem.
- Workers should execute approved tickets from clean task context, not inherit planning discussion.

Alternatives rejected:

- Forking the Rep chat for worker execution.
- Running worker proof inside the management conversation.
- Letting the Manager project become both front desk and technical workshop.

Owner:

- Luke owns the operating decision.
- Rep owns keeping the management chat clean.
- Workers own execution only after a clean SellerOne 2.0 task handoff.

Review trigger:

- Before creating or sending work to any temporary worker thread.
- If a worker thread contains copied Rep-chat history.

## ADR-0022 - Manager Project Has Rep And Operations Chats

Date: 2026-06-08

Decision:

- The SellerOne Manager project has two control-layer chat types:
  - Rep Chat: talks to Luke, plans, explains, and turns decisions into tickets.
  - Operations Chat: runs control-desk automations, monitors workers, creates reports, and maintains queue visibility.
- The SellerOne 2.0 project owns execution:
  - Worker Chats execute approved tickets.
  - Reviewer Chats verify tickets from fresh context.
- Worker and Reviewer chats must not fork or inherit the Rep conversation.

Reason:

- The system needs a living control loop, not just one-off prompts.
- Luke needs a clean front desk, but the work still needs monitoring while Luke is away.
- Operations is the shift-manager layer for control work, but it must not become another noisy Luke-facing manager.
- Business runtime remains separate from SellerOne 2.1 control-layer stabilisation.

Alternatives rejected:

- Having only the Rep chat with no Operations monitor.
- Letting old noisy manager automations act as Operations.
- Running workers inside the Manager project.
- Forking the Rep chat into worker threads.
- Letting Operations redesign the system or start unapproved work.

Owner:

- Luke owns the operating model.
- Rep owns Luke-facing planning and decisions.
- Operations owns control-layer monitoring and reports.
- Workers and Reviewers own ticket execution and proof in the SellerOne 2.0 project.

Review trigger:

- Before creating or activating any Operations automation.
- Before starting any worker or reviewer thread.
- If work begins to appear in the wrong project or chat type.

## ADR-0023 - Approved Cycle Work Includes Controlled Pause And Restart

Date: 2026-06-09

Decision:

- When Luke approves a named task for a named cycle, Operations may use controlled pause, reload, or restart for that same cycle if it is genuinely needed to complete the approved repair, proof, or addition.
- This authority applies only inside the named task and named cycle.
- Operations must record the target, reason, pause/reload method, restart method, and post-restart proof.
- Operations must prove the cycle restarted or record a blocker immediately.
- Operations must not leave a cycle stopped silently.
- Operations must not create a second owner to avoid a reload.

Reason:

- Approved maintenance work often cannot be completed safely while an old child process or cycle owner is still running behind old state.
- Requiring Luke to re-approve every bounded pause/reload inside an already-approved cycle task creates unnecessary stoppage.
- The safety requirement is not "never pause"; it is "pause only the named thing, restart it properly, and prove it."

Working-hours note:

- Future maintenance planning should classify cycles by safe working window.
- Repricer or sales-sensitive work may need stricter working-hour protection.
- Price-list scanner work may be less time-sensitive and can usually tolerate broader maintenance windows.

Alternatives rejected:

- Treating every pause/reload as a fresh Luke decision even when it is inside an already-approved named task.
- Allowing a broad kill switch with no named target, restart path, or proof.
- Creating duplicate cycle owners instead of reloading the existing owner safely.

Owner:

- Luke owns the authority decision.
- Rep owns explaining the business boundary.
- Operations owns maintenance records, reload routing, and restart proof.
- Workers own staying inside the approved packet and stop conditions.

Review trigger:

- Before pausing, reloading, restarting, or relaunching any named cycle.
- If the cycle cannot be restarted cleanly.
- If work would touch sales-sensitive runtime during a future protected working window.
