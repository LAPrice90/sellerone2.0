# SO21 Data Family Inventory

## Manager Authority
- task_id: MGR_SO21_DATA_FAMILY_INVENTORY
- job_ref: SO21-DATA-FAMILY-INVENTORY
- flow: SO21
- task_type: custodian_inventory
- status: proved
- authority: luke_requested_data_storage_cleanup_system
- priority: high
- luke_action_required: 0

## Plain English
Before cleanup automation can exist, SellerOne needs to know what data families it produces and which ones are live, raw, derived, proof, backup, or temp.

## Allowed Work
- inspect output folders read-only
- group outputs into data families
- identify owner flow where possible
- identify likely retention class
- write inventory under `CONTROL/`

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
- A data-family inventory exists under `CONTROL/`.
- The inventory identifies owner, class, and proposed retention direction.
- Protected current runtime areas remain excluded from cleanup.

## Retest
- retest_command: Inspect the inventory and confirm it is read-only.

## Stop Condition
Stop before any cleanup apply or protected action.
