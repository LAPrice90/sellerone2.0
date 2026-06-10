# B MOT: b_backdate_recovery_quarantine needs repair

## Manager Authority
- task_id: MOT_B_B_BACKDATE_RECOVERY_QUARANTINE
- job_ref: B-BACKDATE-RECOVERY-QUARANTINE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B recovery scanner and quarantine proof code only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, live merge, ROI use, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_backdate_recovery_quarantine` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_BACKDATE_RECOVERY_QUARANTINE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_order_recovery\b_order_recovery_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B recovery scanner and quarantine proof code only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, live merge, ROI use, or data correction.",
  "check": "b_backdate_recovery_quarantine",
  "created_utc": "2026-05-27T11:38:51Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T13:44:20Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B recovery task to build the read-only backdate scanner and quarantine proof. Do not run B or merge data from MOT.",
  "notes": "sellerboard_missing=1;unrecovered=1;quarantine_rows=0",
  "observed_utc": "2026-05-27T13:44:20Z",
  "priority": "high",
  "producer": "sellerone_manager.b_order_recovery",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_backdate_recovery_quarantine` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Sellerboard shows shipped orders that are not API-proved in quarantine.",
  "safe_repair_boundary": "B recovery scanner and quarantine proof code only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, live merge, ROI use, or data correction.",
  "seen_count": "26",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_order_recovery\\b_order_recovery_summary.csv",
  "status": "new",
  "title": "B MOT: b_backdate_recovery_quarantine needs repair",
  "updated_utc": "2026-05-27T13:44:20Z",
  "work_item_id": "MOT_B_B_BACKDATE_RECOVERY_QUARANTINE"
}
```
