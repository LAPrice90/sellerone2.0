# SO21 Duplicate Data Report

## Manager Authority
- task_id: MGR_SO21_DUPLICATE_DATA_REPORT
- job_ref: SO21-DUPLICATE-DATA-REPORT
- flow: SO21
- task_type: custodian_duplicate_report
- status: proved
- authority: luke_requested_data_storage_cleanup_system
- priority: high
- luke_action_required: 0

## Plain English
SellerOne needs a duplicate-data report before any dedupe cleanup happens.

This should identify repeated files or repeated generated outputs, but it must not delete them.

## Allowed Work
- inspect output files read-only
- identify likely duplicates using safe signatures
- group duplicate candidates
- estimate space impact
- write report under `CONTROL/`

## Forbidden Work
- no deletion
- no file movement
- no compression
- no purge
- no database write
- no Sheet write
- no runtime change
- no queue edit outside approved status updates

## Acceptance Proof
- A duplicate-data report exists under `CONTROL/`.
- The report separates exact duplicates from likely duplicates.
- The report recommends safe next action without applying cleanup.

## Retest
- retest_command: Inspect the duplicate report and confirm no cleanup occurred.

## Stop Condition
Stop before dedupe apply or protected action.
