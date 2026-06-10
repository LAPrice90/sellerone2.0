# B MOT: b_refund_return_warning_workpack needs repair

## Manager Authority
- task_id: MOT_B_B_REFUND_RETURN_WARNING_WORKPACK
- job_ref: B-REFUND-WARNING-WORKPACK
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B refund-return warning workpack only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_return_warning_workpack` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_REFUND_RETURN_WARNING_WORKPACK
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_return_warning_workpack.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_return_warning_workpack_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B refund-return warning workpack only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.",
  "check": "b_refund_return_warning_workpack",
  "created_utc": "2026-06-03T17:17:16Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-06-03T22:03:54Z",
  "luke_action_required": "0",
  "manager_action": "Use the workpack to create bounded B worker packets. Keep bridge warnings visible and keep ROI/restocking blocked from unproved stock recovery.",
  "notes": "workpack_lanes=4;unclassified_lanes=1",
  "observed_utc": "2026-06-03T22:03:54Z",
  "priority": "high",
  "producer": "B051_build_refund_return_warning_workpack.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_return_warning_workpack` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Some refund-return warning lanes are not manager-classified.",
  "safe_repair_boundary": "B refund-return warning workpack only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.",
  "seen_count": "4",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_warning_workpack.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_warning_workpack_summary.csv",
  "status": "new",
  "title": "B MOT: b_refund_return_warning_workpack needs repair",
  "updated_utc": "2026-06-03T22:03:54Z",
  "work_item_id": "MOT_B_B_REFUND_RETURN_WARNING_WORKPACK"
}
```
