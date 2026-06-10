# F MOT: f_rescan_priority_proof needs Luke decision

## Manager Authority
- task_id: MOT_F_F_RESCAN_PRIORITY_PROOF
- job_ref: F-RESCAN-PRIORITY-02
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: RESCAN proof only; no F061 run, no worker restart, no queue edit, no output rewrite, no Sheet write, and no price change.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_rescan_priority_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_RESCAN_PRIORITY_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\config\feeder\f_scanner_timeout_policy.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\inbox\supplier_price_list_active_run.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\live\f_screening_row_state_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\test_mode\f061_rescan_recovery_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "RESCAN proof only; no F061 run, no worker restart, no queue edit, no output rewrite, no Sheet write, and no price change.",
  "check": "f_rescan_priority_proof",
  "created_utc": "2026-06-04T13:50:36Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-RESCAN-PRIORITY",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "1",
  "manager_action": "Needs protected decision: approve a preview-first F rescan recovery packet for the parked rows, or leave them parked. Do not rewrite queue/output rows from MOT.",
  "notes": "parked_timeout=170",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "F061 RESCAN retry handling and F timeout policy",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_rescan_priority_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "Existing RESCAN rows still carry timeout dates, so they are parked instead of retry-now.",
  "safe_repair_boundary": "RESCAN proof only; no F061 run, no worker restart, no queue edit, no output rewrite, no Sheet write, and no price change.",
  "seen_count": "443",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\config\\feeder\\f_scanner_timeout_policy.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\inbox\\supplier_price_list_active_run.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\live\\f_screening_row_state_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\test_mode\\f061_rescan_recovery_summary.csv",
  "status": "blocked_needs_luke",
  "title": "F MOT: f_rescan_priority_proof needs Luke decision",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_F_F_RESCAN_PRIORITY_PROOF"
}
```
