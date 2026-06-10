# B MOT: b_refund_pnl_roi_api_proof needs repair

## Manager Authority
- task_id: MOT_B_B_REFUND_PNL_ROI_API_PROOF
- job_ref: B-REFUND-PNL-ROI
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B refund proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or Sellerboard-as-final-ROI use.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_pnl_roi_api_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_REFUND_PNL_ROI_API_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_pnl_bridge.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_sku_refund_rate.csv

## Exact Source Row
```json
{
  "allowed_scope": "B refund proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or Sellerboard-as-final-ROI use.",
  "check": "b_refund_pnl_roi_api_proof",
  "created_utc": "2026-06-01T11:00:15Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-06-01T11:06:34Z",
  "luke_action_required": "0",
  "manager_action": "Repair the refund proof builder or wait for API refund evidence. Do not use Sellerboard estimates as live ROI or restocking truth.",
  "notes": "missing_or_invalid_refund_proof",
  "observed_utc": "2026-06-01T11:06:34Z",
  "priority": "high",
  "producer": "B037_build_refund_pnl_bridge.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_pnl_roi_api_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "B refund proof files are missing, have schema gaps, or contain API refund rows without required proof fields.",
  "safe_repair_boundary": "B refund proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or Sellerboard-as-final-ROI use.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_pnl_bridge.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_sku_refund_rate.csv",
  "status": "new",
  "title": "B MOT: b_refund_pnl_roi_api_proof needs repair",
  "updated_utc": "2026-06-01T11:06:34Z",
  "work_item_id": "MOT_B_B_REFUND_PNL_ROI_API_PROOF"
}
```
