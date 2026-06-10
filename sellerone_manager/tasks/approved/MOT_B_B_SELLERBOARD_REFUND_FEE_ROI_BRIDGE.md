# B MOT: b_sellerboard_refund_fee_roi_bridge needs repair

## Manager Authority
- task_id: MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE
- job_ref: B-SELLERBOARD-REFUND-FEE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Read-only bridge gap reporting only; no live ROI change, data correction, local DB alignment, Sheet write, or price change.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_refund_fee_roi_bridge` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\sellerboard_bridge\b_sellerboard_bridge_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "Read-only bridge gap reporting only; no live ROI change, data correction, local DB alignment, Sheet write, or price change.",
  "check": "b_sellerboard_refund_fee_roi_bridge",
  "created_utc": "2026-05-27T14:17:43Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T18:28:34Z",
  "luke_action_required": "0",
  "manager_action": "Keep this as a bridge-gap warning until API allocation is available. Do not feed Sellerboard values into live ROI without Luke.",
  "notes": "return_refund_gap=5;fee_detail_rows=0;roi_refund_rows=0",
  "observed_utc": "2026-05-27T18:28:34Z",
  "priority": "normal",
  "producer": "sellerone_manager.sellerboard_bridge",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_refund_fee_roi_bridge` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Refund/fee/ROI linkage is not yet fully API-proven.",
  "safe_repair_boundary": "Read-only bridge gap reporting only; no live ROI change, data correction, local DB alignment, Sheet write, or price change.",
  "seen_count": "45",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\sellerboard_bridge\\b_sellerboard_bridge_summary.csv",
  "status": "new",
  "title": "B MOT: b_sellerboard_refund_fee_roi_bridge needs repair",
  "updated_utc": "2026-05-27T18:28:34Z",
  "work_item_id": "MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE"
}
```
