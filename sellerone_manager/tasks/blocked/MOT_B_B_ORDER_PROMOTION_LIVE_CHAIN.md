# B MOT: b_order_promotion_live_chain needs Luke decision

## Manager Authority
- task_id: MOT_B_B_ORDER_PROMOTION_LIVE_CHAIN
- job_ref: B-ORDER-PROMOTION-CHAIN
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: B live promotion proof only; stop before live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_order_promotion_live_chain` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_ORDER_PROMOTION_LIVE_CHAIN
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\order_promotion\b_order_promotion_manifest.json

## Exact Source Row
```json
{
  "allowed_scope": "B live promotion proof only; stop before live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
  "check": "b_order_promotion_live_chain",
  "created_utc": "2026-05-27T14:40:35Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-06-03T16:29:53Z",
  "luke_action_required": "1",
  "manager_action": "Stop for Luke before writing orders, order items, Level 1, Order Master, or SQL shadow tables.",
  "notes": "awaiting_luke_promotion_approval",
  "observed_utc": "2026-06-03T16:29:53Z",
  "priority": "high",
  "producer": "sellerone_manager.b_order_promotion",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_order_promotion_live_chain` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "The final live order-chain repair is protected.",
  "safe_repair_boundary": "B live promotion proof only; stop before live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
  "seen_count": "7",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\order_promotion\\b_order_promotion_manifest.json",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_order_promotion_live_chain needs Luke decision",
  "updated_utc": "2026-06-03T16:29:53Z",
  "work_item_id": "MOT_B_B_ORDER_PROMOTION_LIVE_CHAIN"
}
```
