# SellerOne 2.1 - Control Desk Stabilisation Blueprint

Draft date: 2026-06-08

## Plain-English Decision

SellerOne 2.1 should not start as a rewrite of the business logic.

The first move is to clean the control system. Right now SellerOne has working parts, but the "brain" is spread across old logs, prompts, manager files, automations, cycle-specific rules, and newer task packets. That is like running one warehouse from seven different clipboards. Some clipboards are useful history, but only one should decide what work is active today.

SellerOne 2.1 should become:

- one human-facing control desk
- one canonical task queue
- one bounded worker per ticket
- one fresh-context reviewer before proof
- one serious custodian for disk, tokens, logs, archives, temp files, old outputs, stale packets, dead automations, and dead schedulers

The goal is fewer moving control layers, not fewer safety checks.

## Research Basis

The supplied research report recommends the same direction seen in current AI coding guidance:

- OpenAI Codex guidance favors well-scoped tasks, issue-style prompts, a task queue, and durable `AGENTS.md` context.
- OpenAI Codex automations guidance says automations should be specific, repeatable, and easy to review.
- OpenAI Skills guidance treats repeatable workflows as packaged instructions and scripts, not repeated long prompts.
- GitHub Copilot agent guidance starts mature-project improvement with custom instructions, setup files, issue-style work, and reviewable changes.
- Cursor and Claude Code patterns also point toward persistent rules, bounded background sessions, non-interactive checks, and review layers.

Useful references:

- https://openai.com/business/guides-and-resources/how-openai-uses-codex/
- https://openai.com/academy/codex-automations/
- https://github.com/openai/skills
- https://docs.github.com/en/copilot/tutorials/cloud-agent/improve-a-project
- https://docs.cursor.com/context/rules-for-ai
- https://docs.cursor.com/bugbot
- https://code.claude.com/docs/en/cli-usage

## What We Are Consolidating

SellerOne appears to be carrying several generations of control methods at once:

1. Ad-hoc scripts and one-off repair notes.
2. Work-log and chat-history operating memory.
3. Batch launchers and scheduler loops.
4. Cycle-specific manager chats and prompts.
5. MOT worklists, retest queues, and health summaries.
6. Manager Task Board and Manager Briefing UI.
7. Hometime and heartbeat automations.

None of these should be deleted blindly. The 2.1 job is to decide which layer becomes canonical, which layers become read-only history, and which layers become small reusable skills.

## SellerOne 2.1 Target Model

SellerOne 2.1 has four visible operating roles:

- Rep
- Builder
- Reviewer
- Custodian

There is still a dispatching function, but it should not become another visible personality. The Rep and the queue rules decide what enters the queue. The queue contract decides what is ready. No extra "Dispatcher" chat should sit between Luke and the work.

SellerOne 2.1 also separates the front desk from the back office:

- Rep is the front desk Luke talks to.
- Operations is a back-office reporting function.
- Luke does not talk directly to Operations.
- Rep reads Operations reports and turns them into queue decisions, tickets, or plain-English status.

Operations is not a new visible manager. It is the place where automation, MOT, storage, token, scheduler, and stale-lock evidence gets summarized before it reaches the Rep.

## Architect Decision Record

SellerOne 2.1 also needs an Architect layer, but this should be a document, not a bot, loop, or scheduled manager.

The Architect record answers one question:

- Why did we choose this shape?

Recommended file:

- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md`

Every major decision should record:

- date
- decision
- reason
- alternatives rejected
- owner
- review trigger

This prevents future drift. Six months from now, the system should be able to explain why approved task packets became the canonical queue, why the Task Board is read-only, and why `CURRENT_STATE.md` is the human-readable state file.

### 1. Rep

The Rep is the only normal Luke-facing role.

Job:

- talk in plain English
- turn Luke's request into a bounded ticket
- explain current status without raw technical noise
- interrupt Luke only for real decisions
- decide what enters the queue
- use the queue contract to decide what is ready

The Rep does not use chat memory as the source of truth. It reads the queue and current state.

### 2. Builder

The Builder owns one ticket at a time.

Job:

- inspect the scoped files
- make the smallest safe change
- run focused tests
- update ticket proof

The Builder must not widen scope just because it sees nearby problems.

### 3. Reviewer

The Reviewer uses fresh context.

Job:

- review the diff and proof
- run or inspect the required checks
- mark the ticket proved or return it with clear reasons

The Reviewer must not trust the Builder's chat history as proof.

### 4. Custodian

The Custodian keeps the machine clean and trustworthy.

Job:

- own disk usage
- own token and model usage visibility
- own log retention
- own archive policy
- own temp-file cleanup
- own old-output lifecycle
- own stale packet cleanup
- own dead automation detection
- own dead scheduler detection
- own stale lock detection
- enforce retention policy before deletion
- report bloat before it becomes a crisis

The Custodian should be powerful but boring. It is allowed to measure, classify, compress, archive, and quarantine by policy. It must not silently delete protected business data. Cleanup must follow a written retention policy.

## Canonical Sources Of Truth

SellerOne 2.1 needs one source of truth per job.

Recommended control files:

- `sellerone_manager/tasks/approved/*.md` remains the approved engineering queue.
- `sellerone_manager/tasks/blocked/*.md` remains the blocked queue.
- `sellerone_manager/tasks/archive/*.md` becomes completed/history storage.
- `sellerone_manager/CONTROL/CURRENT_STATE.md` becomes the official human-readable state snapshot.
- `sellerone_manager/current_state.json` remains machine support only and must not outrank newer MOT evidence.
- `out/systems/M/mot/` remains health and MOT evidence.
- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md` records major operating decisions and rejected alternatives.
- `sellerone_manager/CONTROL/CURRENT_TICKETS.md` should list only active Builder and Reviewer work.
- `sellerone_manager/CONTROL/BACKLOG.md` should summarize planned and parked work in plain English.
- `sellerone_manager/CONTROL/OPERATIONS.md` should summarize health, disk, token, lock, and automation state.
- `sellerone_manager/CONTROL/AI_USAGE.csv` should track AI usage pressure by ticket and control source until real billing data is connected.
- `sellerone_manager/CONTROL/STORAGE_POLICY.md` should define what can be archived, compressed, or deleted.
- `sellerone_manager/CONTROL/STORAGE_INDEX.csv` should classify major output folders and proof families.

Chat is not a source of truth. Chat is the front desk.

## Ticket Contract

Every SellerOne 2.1 ticket should have:

- `job_ref`
- business reason
- scope
- files to inspect
- allowed actions
- forbidden actions
- done-when proof
- test or verification command
- rollback or backup expectation
- owner role
- status

Allowed statuses:

- inbox
- planned
- approved
- in_progress
- review
- proved
- blocked
- archived

## Automation Policy

All Codex automations were paused on 2026-06-08 before this blueprint was written.

SellerOne 2.1 should restart with fewer automations:

1. Rep briefing
   - on demand or twice daily
   - summarizes queue, blockers, and decisions

2. Health watcher
   - hourly
   - reads latest health/MOT artifacts only
   - opens or refreshes tickets
   - does not patch code

3. Review watcher
   - triggered when a ticket enters review
   - fresh-context review only

4. Storage custodian
   - nightly or weekly
   - compresses or purges only by retention class
   - quarantines before destructive cleanup where practical

5. Usage reporter
   - daily or weekly
   - reports high-cost loops, repeated failures, and noisy instructions

Cycle-specific heartbeat managers should not come back by default. They should return only when a specific stable workflow proves it needs a schedule.

There should be no visible Dispatcher automation. Dispatching is a function of the queue contract and Rep briefing, not a separate manager identity.

## Runtime Boundary

The production business runtime should stay deterministic.

Plain English:

- A, B, E, H, F, and O scripts should keep doing script work.
- AI should plan, diagnose, patch bounded tasks, review, and monitor evidence.
- AI should not become the only live controller of stock, prices, queues, sheets, purchase orders, or Amazon security.

Protected actions still need explicit Luke approval:

- price changes
- queue edits
- Google Sheets writes
- Product DB/local DB alignment
- output deletion
- purchase commitments
- receiving stock
- send-to-Amazon actions
- bypassing Amazon security
- disabling MFA

## Migration Phases

### Phase 0 - Freeze The Managers

Goal:

- pause manager automations
- stop opening new F/H/O/B repair lanes unless critical
- keep live business loops under existing safety rules

Done when:

- Codex automation active count is zero
- the 2.1 blueprint exists
- Luke has one recommended next task

Current status:

- Codex automations active count: 0
- blueprint created: yes
- Custodian policy created: yes
- Current tickets and backlog created: yes
- Instruction cleanup started: yes
- AI usage report created: yes
- Legacy coding plan archived: yes
- Prompt and plan folders marked history/template: yes
- Role files trimmed into short front doors: yes
- Skill specs created: yes
- `out/` subtree index created: yes
- Custodian dry-run manifest created: yes
- Dead automation and scheduler review created: yes
- Windows scheduler pause decision complete: yes
- Automation rebuild plan created: yes
- Automations activated by rebuild plan: 0
- Paused Rep briefing pilot created: yes
- Rep briefing pilot activated: yes
- Current recommended next task: `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

### Phase 1 - Control Inventory

Goal:

Make a map of every place SellerOne currently stores instructions, task state, prompts, manager status, handoff rules, and automation schedules.

Inspect:

- `AGENTS.md`
- `sellerone_manager/AGENTS.md`
- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `sellerone_manager/CODING_PLAN.md`
- `sellerone_manager/tasks/`
- `sellerone_manager/agent_launch_prompts/`
- `sellerone_manager/thread_prompts/`
- `sellerone_manager/thread_starters/`
- `sellerone_manager/goals/`
- `sellerone_manager/project_threads/`
- `project_control/`
- `.codex/automations/`

Output:

- `sellerone_manager/CONTROL/SELLERONE_2_1_CONTROL_INVENTORY.md`

Done when:

- every control path is labelled as keep, merge, archive, or retire
- no code is changed
- no business data is changed

### Phase 2 - Define The Canonical Queue

Goal:

Make one queue the official source of active engineering work.

Recommended decision:

- keep approved task packets as the canonical queue
- make the Manager Task Board read from that queue
- make old work logs and prompt folders historical or template-only

Output:

- `sellerone_manager/CONTROL/QUEUE_CONTRACT.md`

Done when:

- every active job has one `job_ref`
- every active job has one status
- old duplicate task lists are no longer treated as live instruction sources

Current status:

- complete as control document on 2026-06-08.
- output: `sellerone_manager/CONTROL/QUEUE_CONTRACT.md`.

### Phase 3 - Simplify The Instructions

Goal:

Cut the instruction sprawl down into a small set of durable rules and reusable skills.

Keep in `AGENTS.md`:

- safety rules
- proof rules
- role split
- source-of-truth rules
- protected actions

Move into skills or task templates:

- repeated repair workflows
- MOT-specific playbooks
- F login/session routines
- B maintenance handoff routines
- O restock readiness routines

Output:

- shorter root `AGENTS.md`
- shorter manager `AGENTS.md`
- first draft of SellerOne manager skill specs

Done when:

- a new Codex thread can understand SellerOne without reading seven overlapping rulebooks

Current status:

- root `AGENTS.md`: shortened into SellerOne 2.1 bootstrap
- manager `AGENTS.md`: shortened into Manager workspace bootstrap
- `CONTROL/ROLE_BOOTSTRAP.md`: created
- `CONTROL/RUNTIME_SAFETY_RULES.md`: created
- `CONTROL/INSTRUCTION_CLEANUP_PLAN.md`: created
- oversized legacy `CODING_PLAN.md`: archived into `CONTROL/CODING_PLAN_ARCHIVE.md`
- prompt and plan folders: marked as history/template material
- role detail files: trimmed into short front doors
- repeat workflow specs: created
- mixed `out/` folder: classified by top-level subtree
- preview-only cleanup manifest: created
- dead automation and scheduler review: created
- temporary Windows scheduler pause: complete for the eight approved tasks
- automation rebuild plan: created with one active approved pilot, three remaining paused candidates, and one deferred watcher
- remaining work: prove the first scheduled Rep briefing run

### Phase 4 - Build The 2.1 Control Folder

Goal:

Create the durable control folder for the new operating model.

Files:

- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md`
- `sellerone_manager/CONTROL/CURRENT_STATE.md`
- `sellerone_manager/CONTROL/BACKLOG.md`
- `sellerone_manager/CONTROL/CURRENT_TICKETS.md`
- `sellerone_manager/CONTROL/OPERATIONS.md`
- `sellerone_manager/CONTROL/AI_USAGE.csv`
- `sellerone_manager/CONTROL/STORAGE_POLICY.md`
- `sellerone_manager/CONTROL/STORAGE_INDEX.csv`

Done when:

- these files exist
- they are updated by explicit manager commands or safe watchers
- they do not conflict with the approved task packet system

Current status:

- `ARCHITECTURE_DECISIONS.md`: created
- `CURRENT_STATE.md`: generated from evidence
- `QUEUE_CONTRACT.md`: created
- `OPERATIONS.md`: created
- `STORAGE_POLICY.md`: created
- `STORAGE_INDEX.csv`: created
- `CURRENT_TICKETS.md`: generated from queue evidence
- `BACKLOG.md`: generated from queue and MOT evidence
- `AI_USAGE.csv`: created as usage-pressure report
- `AI_USAGE.md`: created as human-readable usage-pressure report
- `CODING_PLAN_ARCHIVE.md`: created from the old oversized live coding plan
- `PROMPT_FOLDER_ARCHIVE.md`: created to mark old prompt and plan folders as history/template material
- `ROLE_FILE_TRIM.md`: created to record trimmed role front doors
- `SKILL_SPECS.md`: created to record reusable workflow recipes
- `STORAGE_INDEX_OUT_SUBTREE.csv`: created to classify the mixed `out/` folder
- `STORAGE_INDEX_OUT_SUBTREE.md`: created as the readable `out/` classification summary
- `CUSTODIAN_DRY_RUN_MANIFEST.csv`: created as the preview-only cleanup manifest
- `CUSTODIAN_DRY_RUN_MANIFEST.md`: created as the readable dry-run cleanup summary
- `DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv`: created as the automation and scheduler inventory
- `DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md`: created as the readable automation and scheduler review
- `AUTOMATION_REBUILD_PLAN.csv`: created as the paused-first automation rebuild plan
- `AUTOMATION_REBUILD.md`: created as the readable automation rebuild plan
- `ROLE_BOOTSTRAP.md`: created
- `RUNTIME_SAFETY_RULES.md`: created
- `INSTRUCTION_CLEANUP_PLAN.md`: created

### Phase 5 - Retire Or Archive Old Control Layers

Goal:

Remove confusion without losing history.

Method:

- do not delete first
- mark old control files as archived, template-only, or replaced
- update manager docs to point to the new queue
- keep rollback copies

Done when:

- Luke has one front door
- workers have one task source
- reviewers have one proof route
- old prompt/control folders no longer compete with live tasks

### Phase 6 - Reintroduce Automations Carefully

Goal:

Bring back only stable, specific, easy-to-review automations.

Allowed first automations:

- daily Rep briefing
- hourly health watcher
- review watcher
- storage custodian
- usage reporter

Done when:

- each automation has a clear purpose
- each automation writes to a control artifact
- no automation performs protected work
- no automation duplicates another automation

Current status:

- automation rebuild plan: created on 2026-06-08
- active approved pilot automations: 1
- paused pilot automations already created: 0
- candidate automations to create paused: 3
- candidate automations deferred: 1
- automations activated after Luke approval: 1
- first recommended pilot: `SO21-REP-BRIEFING`
- next proof: `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

### Phase 7 - Pilot 2.1 On One Lane

Goal:

Prove the model on one safe lane before rolling it across all SellerOne.

Recommended pilot:

- SellerOne Manager control work first
- then F manager visibility and queue handling
- then O restock readiness
- then B/H/E as needed

Done when:

- one lane has one queue, one ticket flow, one review path, and no duplicate manager chatter

## First Execution Tickets

### SO21-CONTROL-INVENTORY

Purpose:

- map all current control paths
- label them keep, merge, archive, or retire

Risk:

- low

Protected actions:

- none allowed

Done when:

- `sellerone_manager/CONTROL/SELLERONE_2_1_CONTROL_INVENTORY.md` exists

### SO21-ARCHITECTURE-DECISIONS

Purpose:

- create the Architect decision record
- record why SellerOne 2.1 is a control-layer stabilisation, not a business-system rewrite
- record which system owns the canonical queue

Risk:

- low

Protected actions:

- none allowed

Done when:

- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md` exists with initial decisions

### SO21-QUEUE-CONTRACT

Purpose:

- define the one official queue and status model

Risk:

- low

Protected actions:

- none allowed

Done when:

- `sellerone_manager/CONTROL/QUEUE_CONTRACT.md` exists
- Manager Task Board source rules are clear

### SO21-INSTRUCTION-CLEANUP

Purpose:

- reduce overlapping instructions and move repeatable workflows into skill candidates

Risk:

- medium

Protected actions:

- no runtime script changes
- no business data changes

Done when:

- root and manager instructions are shorter and non-conflicting

### SO21-STORAGE-CUSTODIAN

Purpose:

- create storage classes and cleanup rules before more build work

Risk:

- medium

Protected actions:

- no deletion until retention policy and quarantine path are approved

Done when:

- storage policy and storage index exist
- cleanup is preview-only until Luke approves destructive behavior

### SO21-AUTOMATION-REBUILD

Purpose:

- rebuild only the small set of stable automations

Risk:

- medium

Protected actions:

- no worker cycles
- no protected business operations

Done when:

- old manager heartbeats stay paused or archived
- new automation set is smaller and easier to audit
- `sellerone_manager/CONTROL/AUTOMATION_REBUILD.md` exists
- no automation is activated by the rebuild plan itself

Current status:

- complete on 2026-06-08
- one automation pilot was activated after Luke approval
- three remaining paused automation candidates were proposed
- one review watcher was deferred until the queue exposes a stable review-ready state
- recommended next task: `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

### SO21-WINDOWS-SCHEDULER-PAUSE-DECISION

Purpose:

- decide what to do with ready Windows scheduled tasks that sit outside the Codex app automation pause

Risk:

- medium

Protected actions:

- no scheduler disable, delete, edit, restart, or ownership change without Luke approval

Done when:

- Luke chooses whether to disable the ready Windows scheduled tasks during SellerOne 2.1 stabilisation
- any approved pause action is recorded in `sellerone_manager/CONTROL/WINDOWS_SCHEDULER_PAUSE_DECISION.md`

Current status:

- complete on 2026-06-08
- the eight approved scheduled task names are disabled
- rollback exports exist under `sellerone_manager/CONTROL/scheduler_pause_backups/`

## Acceptance Criteria For SellerOne 2.1

SellerOne 2.1 is ready when:

- Luke has one normal front door
- every active engineering job has one `job_ref`
- every active job appears in one canonical queue
- `CURRENT_STATE.md` is generated from evidence and readable by Luke
- architecture decisions are recorded before major control changes
- Manager Task Board and briefing read the same queue
- workers only claim approved tickets
- reviewers prove tickets from fresh context
- automations are few, stable, and reviewable
- Custodian owns disk, tokens, logs, archives, temp files, old outputs, stale packets, dead automations, and dead schedulers
- storage retention is written down before cleanup
- AI usage-pressure tracking exists, with real billing data still marked unavailable until a true source is connected
- old control layers are labelled as current, archived, template-only, or retired

## Immediate Recommendation

Continue with `SO21-REP-BRIEFING-FIRST-RUN-PROOF`.

Reason:

- `SO21-CONTROL-INVENTORY` is complete as a first pass.
- `SO21-QUEUE-CONTRACT` is complete as a control document.
- `CURRENT_STATE.md` is now generated from evidence.
- `SO21-AI-USAGE-REPORT` is complete as a usage-pressure report.
- `SO21-CODING-PLAN-ARCHIVE` is complete; the old live plan is now archived.
- `SO21-PROMPT-FOLDER-ARCHIVE` is complete; old prompt and plan folders are now marked history/template only.
- `SO21-ROLE-FILE-TRIM` is complete; role files are now short front doors.
- `SO21-SKILL-SPECS` is complete; repeat workflows are now written as reusable recipes.
- `SO21-STORAGE-INDEX-OUT-SUBTREE` is complete; `out/` is classified into live runtime, rollback, audit history, mixed root files, and temp/debug candidates.
- `SO21-CUSTODIAN-DRY-RUN-MANIFEST` is complete; the cleanup manifest is preview-only and no files were deleted, moved, compressed, purged, or archived.
- `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW` is complete; Codex app automations are paused, but ready Windows scheduled tasks still exist.
- `SO21-WINDOWS-SCHEDULER-PAUSE-DECISION` is complete; the eight approved Windows scheduled tasks are disabled, not deleted.
- `SO21-AUTOMATION-REBUILD` is complete; the smaller automation set is designed and the first pilot is active after Luke approval.
- The next control step is proving the first scheduled `SO21-REP-BRIEFING` run.
