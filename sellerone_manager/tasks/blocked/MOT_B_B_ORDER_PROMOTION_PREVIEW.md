# B MOT: b_order_promotion_preview needs Luke decision

## Manager Authority
- task_id: MOT_B_B_ORDER_PROMOTION_PREVIEW
- job_ref: B-ORDER-PROMOTION-PREVIEW
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: B promotion preview and proof only; no live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_order_promotion_preview` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_ORDER_PROMOTION_PREVIEW
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_order_promotion\b_order_promotion_preview.csv

## Exact Source Row
```json
{
  "allowed_scope": "B promotion preview and proof only; no live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
  "check": "b_order_promotion_preview",
  "created_utc": "2026-05-27T14:40:35Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-06-03T16:29:53Z",
  "luke_action_required": "1",
  "manager_action": "Luke must approve the protected B order promotion repair window before Codex can write live B outputs.",
  "notes": "ready_pending_approval=5",
  "observed_utc": "2026-06-03T16:29:53Z",
  "priority": "high",
  "producer": "sellerone_manager.b_order_promotion",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_order_promotion_preview` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Recovered orders are ready for live local promotion, which is a protected action.",
  "safe_repair_boundary": "B promotion preview and proof only; no live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
  "seen_count": "7",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_order_promotion\\b_order_promotion_preview.csv",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_order_promotion_preview needs Luke decision",
  "updated_utc": "2026-06-03T16:29:53Z",
  "work_item_id": "MOT_B_B_ORDER_PROMOTION_PREVIEW"
}
```
