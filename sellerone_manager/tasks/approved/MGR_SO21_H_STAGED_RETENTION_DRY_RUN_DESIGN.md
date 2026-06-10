# SO21 H Staged Retention Dry-Run Design

## Manager Authority
- task_id: MGR_SO21_H_STAGED_RETENTION_DRY_RUN_DESIGN
- job_ref: SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN
- flow: SO21
- task_type: custodian_storage_design
- status: proved
- authority: morning_improvement_report_recommendation
- priority: high
- luke_action_required: 0

## Plain English
The morning improvement report found that `out/systems/H/staged` is the largest measured storage opportunity.

This does not mean the data is trash. This ticket designs the safe dry-run route only. It must not delete, move, compress, purge, archive, run H, or change runtime.

## Business Reason
SellerOne needs to control storage growth without risking H pricing proof, staged rollback evidence, failed-run investigation evidence, or business-critical runtime data.

## Allowed Work
- inspect existing storage reports and H staged evidence read-only
- design a dry-run manifest route for H staged data
- define H staged categories such as current proof, failed partial, audit history, duplicate candidate, and protected
- define owner-proof checks required before any cleanup proposal
- define graphs Luke should see before deciding
- write a design report under `CONTROL/`

## Forbidden Work
- no deletion
- no movement
- no compression
- no purge
- no archive apply
- no H runtime run
- no H worker restart
- no Task Scheduler change
- no process kill
- no price changes
- no Google Sheets writes
- no database writes or alignment
- no queue edits outside approved status updates
- no Amazon/security
- no purchase, receiving, or send-to-Amazon

## Acceptance Proof
- A H staged dry-run design report exists under `CONTROL/`.
- The design separates current/protected data from cleanup candidates.
- The design requires owner-proof before any cleanup manifest.
- The design recommends proposal graphs using measured data.
- No protected action occurred.

## Retest
- retest_command: Inspect the H staged dry-run design and confirm it is design-only.

## Stop Condition
Stop before any cleanup apply, output change, H run, scheduler change, price change, database change, Sheet write, Amazon/security action, or business action.
