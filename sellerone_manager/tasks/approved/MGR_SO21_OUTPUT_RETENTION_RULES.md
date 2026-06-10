# SO21 Output Retention Rules

## Manager Authority
- task_id: MGR_SO21_OUTPUT_RETENTION_RULES
- job_ref: SO21-OUTPUT-RETENTION-RULES
- flow: SO21
- task_type: custodian_retention_rules
- status: proved
- authority: luke_requested_data_storage_cleanup_system
- priority: high
- luke_action_required: 0

## Plain English
SellerOne needs retention rules so outputs do not pile up forever.

Rules should say what to keep, what to archive, what can expire, and what must never be touched automatically.

## Allowed Work
- review storage policy
- use data-family inventory when available
- propose retention rules by data family
- mark which rules can be automatic and which need approval
- write rules under `CONTROL/`

## Forbidden Work
- no cleanup apply
- no deletion
- no file movement
- no compression
- no purge
- no database write
- no Sheet write
- no runtime change

## Acceptance Proof
- Retention rules exist under `CONTROL/`.
- Rules separate automatic-safe candidates from approval-required candidates.
- Protected data remains excluded.

## Retest
- retest_command: Inspect rules and confirm they are not an apply manifest.

## Stop Condition
Stop before applying retention rules to files.
