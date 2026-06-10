# F MOT: f_storage_drift_clear needs repair

## Manager Authority
- task_id: MOT_F_F_STORAGE_DRIFT_CLEAR
- job_ref: F-STORAGE-DRIFT-CLEAR
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Storage proof only; no local DB alignment, CSV rewrite, output deletion, or scanner run.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_storage_drift_clear` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_STORAGE_DRIFT_CLEAR
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\storage_drift_report.csv

## Exact Source Row
```json
{
  "allowed_scope": "Storage proof only; no local DB alignment, CSV rewrite, output deletion, or scanner run.",
  "check": "f_storage_drift_clear",
  "created_utc": "2026-06-05T15:59:52Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-STORAGE-DRIFT-CLEAR",
  "last_seen_utc": "2026-06-09T01:00:26Z",
  "luke_action_required": "0",
  "manager_action": "Create a manager-approved storage-drift task. Do not align CSV and SQL from MOT.",
  "notes": "7",
  "observed_utc": "2026-06-09T01:00:26Z",
  "priority": "high",
  "producer": "FPM129_storage_drift_guard.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_storage_drift_clear` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "At least one F storage contract is not aligned.",
  "safe_repair_boundary": "Storage proof only; no local DB alignment, CSV rewrite, output deletion, or scanner run.",
  "seen_count": "20",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\storage_drift_report.csv",
  "status": "new",
  "title": "F MOT: f_storage_drift_clear needs repair",
  "updated_utc": "2026-06-09T01:00:26Z",
  "work_item_id": "MOT_F_F_STORAGE_DRIFT_CLEAR"
}
```
