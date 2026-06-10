# F MOT: f_live_owner_status needs repair

## Manager Authority
- task_id: MOT_F_F_LIVE_OWNER_STATUS
- job_ref: F-SCANNER-PROGRESS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: F owner and forward-progress proof only; no F061 run, no restart, no queue edit, no supplier switch, no scanner output rewrite, no Sheet write, and no price change.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_live_owner_status` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_LIVE_OWNER_STATUS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\live_cycle_status.csv

## Exact Source Row
```json
{
  "allowed_scope": "F owner and forward-progress proof only; no F061 run, no restart, no queue edit, no supplier switch, no scanner output rewrite, no Sheet write, and no price change.",
  "check": "f_live_owner_status",
  "created_utc": "2026-06-03T06:00:14Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-SCANNER-PROGRESS",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded F manager task to classify ownership evidence.",
  "notes": "running/paused",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "FPM130_run_live_cycle.py / FPM170_supervise_live_cycle.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_live_owner_status` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "Live owner status and supervisor state disagree.",
  "safe_repair_boundary": "F owner and forward-progress proof only; no F061 run, no restart, no queue edit, no supplier switch, no scanner output rewrite, no Sheet write, and no price change.",
  "seen_count": "71",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\live_cycle_status.csv",
  "status": "new",
  "title": "F MOT: f_live_owner_status needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_F_F_LIVE_OWNER_STATUS"
}
```
