# SO21 Legacy Control Apply Plan

## Manager Authority
- task_id: MGR_SO21_LEGACY_CONTROL_APPLY_PLAN
- job_ref: SO21-LEGACY-CONTROL-APPLY-PLAN
- flow: SO21
- task_type: cleanup_apply_planning
- status: proved
- authority: luke_approved_backup_and_archive_apply
- priority: high
- luke_action_required: 0

## Plain English
After the legacy-control retirement manifest is reviewed, SellerOne needs an exact apply plan before anything old is moved, renamed, archived, compressed, or deleted.

This ticket is now approved to create the exact backup-and-archive apply plan and perform only non-destructive archive movement if the exact scope stays inside old control-layer clutter.

No permanent deletion is approved.

## Allowed Work
- use `CONTROL/SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST.md` as input
- group candidate old-control files into exact future actions
- define rollback or recovery path for each future action
- mark each future action as safe, needs Luke decision, or not allowed
- create a future approval list for Luke
- create a dated rollback backup before any movement
- move only approved old-control archive-candidates into a dated archive/quarantine folder
- leave pointer/README files where removing a live-looking folder name would otherwise confuse future chats

## Forbidden Work
- no deletion
- no moving business runtime files
- no moving current control files
- no moving active task packets
- no compression
- no purging
- no permanent deletion
- no renaming
- no Task Scheduler changes
- no business runtime changes
- no price, Sheet, database, or Amazon changes
- no scheduler, automation, runtime, database, Sheet, Amazon, price, lock, or output cleanup

## Acceptance Proof
- A backup-and-archive apply record exists under `CONTROL/`.
- Every proposed future action has exact paths, action type, reason, risk, and rollback route.
- Anything destructive remains marked as needing Luke approval.
- Any movement performed is limited to old control-layer archive-candidates from the retirement manifest.
- A dated backup or rollback path exists for every moved item.
- No permanent deletion was performed.

## Retest
- retest_command: Inspect the apply record, archive/quarantine folder, rollback path, and current control files.

## Stop Condition
Stop before any deletion, compression, purge, business runtime change, scheduler change, automation change, active queue change, current control-file movement, or protected action.
