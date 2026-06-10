# B MOT: b_refund_fee_shipping_gap_review needs repair

## Manager Authority
- task_id: MOT_B_B_REFUND_FEE_SHIPPING_GAP_REVIEW
- job_ref: B-REFUND-FEE-SHIPPING-02
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Read-only B067 money gap proof only; no B run/restart, Sheet write, local DB alignment, output deletion, live ROI/restock use, Sellerboard-final truth, price change, queue edit, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_fee_shipping_gap_review` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_REFUND_FEE_SHIPPING_GAP_REVIEW
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_fee_shipping_gap_review.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_fee_shipping_gap_review_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "Read-only B067 money gap proof only; no B run/restart, Sheet write, local DB alignment, output deletion, live ROI/restock use, Sellerboard-final truth, price change, queue edit, or data correction.",
  "check": "b_refund_fee_shipping_gap_review",
  "created_utc": "2026-06-04T11:33:34Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-REFUND-FEE-SHIPPING",
  "last_seen_utc": "2026-06-04T11:38:44Z",
  "luke_action_required": "0",
  "manager_action": "Keep the gap visible and create bounded API proof tasks where needed. Do not feed Sellerboard estimates into live ROI/restocking.",
  "notes": "api_proved=4;bridge_estimate=2;not_yet_proven=5;live_roi_safe=0",
  "observed_utc": "2026-06-04T11:38:44Z",
  "priority": "normal",
  "producer": "scripts.flows.B.B067_build_refund_fee_shipping_gap_review",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_fee_shipping_gap_review` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Some refund, fee, shipping, ROI, or restock money evidence is still bridge-labelled or not API-proven.",
  "safe_repair_boundary": "Read-only B067 money gap proof only; no B run/restart, Sheet write, local DB alignment, output deletion, live ROI/restock use, Sellerboard-final truth, price change, queue edit, or data correction.",
  "seen_count": "3",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_fee_shipping_gap_review.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_fee_shipping_gap_review_summary.csv",
  "status": "new",
  "title": "B MOT: b_refund_fee_shipping_gap_review needs repair",
  "updated_utc": "2026-06-04T11:38:44Z",
  "work_item_id": "MOT_B_B_REFUND_FEE_SHIPPING_GAP_REVIEW"
}
```
