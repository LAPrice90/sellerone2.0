# B MOT: b_sellerboard_order_reconciliation needs repair

## Manager Authority
- task_id: MOT_B_B_SELLERBOARD_ORDER_RECONCILIATION
- job_ref: B-SELLERBOARD-ORDER-RECONCILIATION
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B Sellerboard reconciliation proof only; no B run, restart, Sheet write, local DB alignment, output deletion, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_order_reconciliation` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_SELLERBOARD_ORDER_RECONCILIATION
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\sellerboard_bridge\b_sellerboard_bridge_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B Sellerboard reconciliation proof only; no B run, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "check": "b_sellerboard_order_reconciliation",
  "created_utc": "2026-05-27T10:00:00Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T10:45:00Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B bridge task to inspect missing order or SKU mapping proof. Do not backfill, run B, or correct data from MOT.",
  "notes": "missing_orders=1;unmapped_shipped=1;required_columns_missing=0",
  "observed_utc": "2026-05-27T10:45:00Z",
  "priority": "high",
  "producer": "sellerone_manager.sellerboard_bridge",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_order_reconciliation` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Sellerboard has outside order/SKU evidence that SellerOne has not fully matched.",
  "safe_repair_boundary": "B Sellerboard reconciliation proof only; no B run, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\sellerboard_bridge\\b_sellerboard_bridge_summary.csv",
  "status": "new",
  "title": "B MOT: b_sellerboard_order_reconciliation needs repair",
  "updated_utc": "2026-05-27T10:45:00Z",
  "work_item_id": "MOT_B_B_SELLERBOARD_ORDER_RECONCILIATION"
}
```
