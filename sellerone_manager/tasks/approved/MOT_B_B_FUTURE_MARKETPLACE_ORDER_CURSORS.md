# B MOT: b_future_marketplace_order_cursors needs repair

## Manager Authority
- task_id: MOT_B_B_FUTURE_MARKETPLACE_ORDER_CURSORS
- job_ref: B-FUTURE-MARKETPLACE-ORDER
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B per-marketplace cursor proof code only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_future_marketplace_order_cursors` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_FUTURE_MARKETPLACE_ORDER_CURSORS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_order_recovery\b_order_recovery_marketplace_plan.csv

## Exact Source Row
```json
{
  "allowed_scope": "B per-marketplace cursor proof code only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "check": "b_future_marketplace_order_cursors",
  "created_utc": "2026-05-27T11:38:51Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-FUTURE-MARKETPLACE-ORDER",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B future-coverage task to add per-marketplace cursor proof. Do not edit the shared marker from MOT.",
  "notes": "missing_cursors=0;stale_cursors=12",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "sellerone_manager.b_order_recovery",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_future_marketplace_order_cursors` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "One or more Amazon marketplaces do not have fresh independent cursor proof.",
  "safe_repair_boundary": "B per-marketplace cursor proof code only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "seen_count": "284",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_order_recovery\\b_order_recovery_marketplace_plan.csv",
  "status": "new",
  "title": "B MOT: b_future_marketplace_order_cursors needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_B_B_FUTURE_MARKETPLACE_ORDER_CURSORS"
}
```
