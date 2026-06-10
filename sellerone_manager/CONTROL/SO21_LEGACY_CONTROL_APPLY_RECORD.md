# SO21 Legacy Control Apply Record

Job: SO21-LEGACY-CONTROL-APPLY-PLAN
Applied: 20260608T161449Z
Status: first cleanup apply completed

## What Changed

Old control-looking folders and old daily/hometime manager plan files were backed up, then moved into the legacy control archive.

No files were permanently deleted.
No business runtime, Task Scheduler job, Codex automation, queue packet, database, Google Sheet, price, Amazon login, or worker process was changed.

## Backup And Archive

- Primary full-content backup: CONTROL/legacy_control_apply_backups/20260608T161138Z
- Primary full-content archive: legacy_control_archive/20260608T161138Z
- Later pointer-only backup snapshot: CONTROL/legacy_control_apply_backups/20260608T161449Z
- Later pointer-only archive snapshot: legacy_control_archive/20260608T161449Z

## Moved

- directory: agent_launch_prompts
- directory: thread_prompts
- directory: thread_starters
- directory: project_threads
- directory: goals
- file: DAILY_MANAGER_PLAN_20260602.md
- file: DAILY_MANAGER_PLAN_20260603.md
- file: DAILY_MANAGER_PLAN_20260605.md
- file: DAYTIME_MANAGER_PLAN_20260606.md
- file: HOMETIME_PLAN_20260605.md
- file: HOMETIME_PLAN_20260606_WEEKEND.md
- file: MORNING_ISSUE_PLAN_20260606.md
- file: TONIGHT_MANAGER_PLAN_20260604.md

## Skipped

- Nothing skipped from the safe first-pass candidate list.

## Skipped Risky Items

These were deliberately left in place because they are current control, generated proof/runtime evidence, or need a separate reconciliation before movement:

- `sellerone_manager/tasks/approved` - canonical active approved queue packet source.
- `sellerone_manager/tasks/blocked` - canonical Luke-blocked queue packet source.
- `sellerone_manager/tasks/proposed` - candidate packet source.
- `sellerone_manager/tasks/archive` - current archive lane.
- `plans/active` - legacy active-plan library; needs reconciliation into packets/backlog before archive movement.
- `plans/archive` - existing historical plan archive; no movement needed by this packet.
- `project_control` - large governance/audit area; needs file-level dry-run retention manifest before movement.
- `out/systems/M` - generated manager/MOT proof evidence; protected as current evidence.
- `out/sql` - runtime output area; outside this cleanup packet.
- `out/locks` - runtime lock area; outside this cleanup packet.
- `out/parking` - runtime parking area; outside this cleanup packet.
- `sellerone_manager/current_state.json` - stale-looking machine support, but retirement needs a separate migration/regeneration ticket.
- `sellerone_manager/CODING_PLAN.md` - bridge history only; leave until a separate pointer-only cleanup ticket.
- `project_control/TASK_QUEUE.md` - old queue-looking governance file; leave until project-control retention is approved.
- `sellerone_manager/CONTROL/scheduler_pause_backups` - scheduler-related backup evidence; needs Luke retention decision.
- `sellerone_manager/CONTROL/storage_index_backups` - rollback/audit backups; needs retention decision.
- `sellerone_manager/CONTROL/coding_plan_archive_backups` - rollback/audit backups; needs retention decision.
- `sellerone_manager/CONTROL/instruction_cleanup_backups` - rollback/audit backups; needs retention decision.
- `sellerone_manager/CONTROL/prompt_folder_archive_backups` - rollback/audit backups; needs retention decision.
- `sellerone_manager/CONTROL/role_file_trim_backups` - rollback/audit backups; needs retention decision.

## Supplemental Observation - 20260608T171146 Local Worker

A later local worker pass observed that the main apply had already completed. No additional old manager-plan, goal, or project-thread source files were moved by that pass because those source folders/files were already pointer-only or already archived by the main apply.

Additional non-destructive support folders observed:

- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\legacy_control_apply_backups\20260608T171139_SO21_LEGACY_CONTROL_APPLY_PLAN`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\archive\legacy_control_quarantine\20260608T171139_SO21_LEGACY_CONTROL_APPLY_PLAN`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\legacy_control_cleanup_backups\20260608T171146_SO21_LEGACY_CONTROL_APPLY_PLAN`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\archive\legacy_control_quarantine\20260608T171146_SO21_LEGACY_CONTROL_APPLY_PLAN`

These supplemental folders are non-destructive evidence only. They should not be treated as a new source of truth over the main apply record.

## Deliberately Untouched

- CONTROL current files
- tasks/approved, tasks/blocked, tasks/proposed, and tasks/archive
- plans/active
- project_control
- out, runtime outputs, scheduler state, automations, databases, Google Sheets, prices, and Amazon login/security

## Recovery

Rollback is possible by copying items back from the primary full-content backup folder above. Because this was a move-and-backup pass, recovery does not depend on deleted files.

Recommended next move: continue with SO21-LEGACY-CONTROL-RETIREMENT-REVIEW

## Verified Filesystem Clarification - 20260608T171139 Local Worker

The cleanup evidence now has three non-destructive layers:

- Full original legacy material archive: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\legacy_control_archive\20260608T161138Z`
- Full original legacy material rollback backup: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\legacy_control_apply_backups\20260608T161138Z`
- Later pointer-only archive: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\legacy_control_archive\20260608T161449Z`
- Later pointer-only rollback backup: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\legacy_control_apply_backups\20260608T161449Z`
- Supplemental placeholder quarantine archive: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\archive\legacy_control_quarantine\20260608T171139_SO21_LEGACY_CONTROL_APPLY_PLAN`
- Supplemental placeholder rollback backup: `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\legacy_control_apply_backups\20260608T171139_SO21_LEGACY_CONTROL_APPLY_PLAN`

The full original legacy material archive includes the old prompt folders, old project-thread folder, old goals folder, and old dated manager plan files.

The supplemental 20260608T171139 pass moved only leftover pointer or placeholder items:

- `sellerone_manager\tasks\done`
- `sellerone_manager\tasks\in_progress`
- `sellerone_manager\tasks\rejected`
- `sellerone_manager\agent_launch_prompts`
- `sellerone_manager\thread_prompts`
- `sellerone_manager\thread_starters`

Pointer README files now remain at the live surface:

- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\done\README.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\in_progress\README.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\rejected\README.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\agent_launch_prompts\README.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_prompts\README.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_starters\README.md`

Skipped risky or out-of-scope areas remain untouched:

- `sellerone_manager\tasks\approved`
- `sellerone_manager\tasks\blocked`
- `sellerone_manager\tasks\proposed`
- `sellerone_manager\tasks\archive`
- `plans\active`
- `project_control`
- `out\systems\M`
- `out\sql`
- `out\locks`
- `out\parking`
- current `sellerone_manager\CONTROL` files except this apply record
- scheduler state, Codex automations, runtime outputs, databases, Google Sheets, prices, and Amazon login/security

No permanent deletion was performed. The supplemental pass used rollback copy first, then move-to-archive. No compression or purge was performed.
