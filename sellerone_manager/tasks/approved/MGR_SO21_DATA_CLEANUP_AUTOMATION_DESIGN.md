# SO21 Data Cleanup Automation Design

## Manager Authority
- task_id: MGR_SO21_DATA_CLEANUP_AUTOMATION_DESIGN
- job_ref: SO21-DATA-CLEANUP-AUTOMATION-DESIGN
- flow: SO21
- task_type: custodian_automation_design
- status: proved
- authority: waits_for_inventory_duplicates_and_retention_rules
- priority: normal
- luke_action_required: 0

## Plain English
After inventory, duplicate report, and retention rules exist, SellerOne can design the automation that keeps data growth under control.

This is design only until reviewed.

## Allowed Work
- design read-only storage reporting automation
- design duplicate reporting automation
- design dry-run manifest automation
- design safe cleanup apply gates
- define what can run automatically and what needs approval

## Forbidden Work
- no automatic deletion
- no cleanup apply
- no file movement
- no compression
- no purge
- no database write
- no Sheet write
- no runtime change

## Acceptance Proof
- Automation design exists under `CONTROL/`.
- It starts with read-only reporting and dry-run manifests.
- It does not approve blind cleanup.
- It names stop conditions and protected data exclusions.

## Retest
- retest_command: Inspect design and confirm it is design-only.

## Stop Condition
Stop before building or enabling cleanup automation that changes files.
