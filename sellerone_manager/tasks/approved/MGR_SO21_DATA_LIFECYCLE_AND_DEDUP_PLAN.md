# SO21 Data Lifecycle And Dedup Plan

## Manager Authority
- task_id: MGR_SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN
- job_ref: SO21-DATA-LIFECYCLE-AND-DEDUP-PLAN
- flow: SO21
- task_type: custodian_data_lifecycle_planning
- status: proved
- authority: luke_requested_data_storage_cleanup_system
- priority: high
- luke_action_required: 0

## Plain English
Luke wants SellerOne to stop keeping too much raw data and to create a system for cleaning, storing, deduplicating, and safely removing useless output.

This packet creates the plan only. It does not delete or move data.

## Allowed Work
- create `CONTROL/SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN.md`
- define raw, clean, derived, duplicate, archive, and temp/debug data categories
- define likely first workstream tickets
- recommend safe automation layers
- keep protected data excluded from automatic cleanup

## Forbidden Work
- no deletion
- no file moving
- no compression
- no purge
- no runtime changes
- no database writes
- no Google Sheets writes
- no Product DB or local DB alignment
- no queue edits outside approved status updates
- no Amazon/security action
- no business action

## Acceptance Proof
- `CONTROL/SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN.md` exists.
- The plan separates raw, clean, derived, duplicate, archive, and temp/debug data.
- The plan recommends follow-up packets.
- The plan does not approve cleanup apply.

## Retest
- retest_command: Inspect the plan and confirm it is planning-only.

## Stop Condition
Stop before deletion, movement, compression, purge, data writes, runtime changes, or protected business action.
