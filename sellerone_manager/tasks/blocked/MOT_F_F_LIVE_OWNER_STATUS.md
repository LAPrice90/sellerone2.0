# F MOT: f_live_owner_status needs Luke decision

## Manager Authority
- task_id: MOT_F_F_LIVE_OWNER_STATUS
- job_ref: F-OWNER
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Owner proof only; no F061 run, no restart, no queue edit, no scanner repair.
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
  "allowed_scope": "Owner proof only; no F061 run, no restart, no queue edit, no scanner repair.",
  "check": "f_live_owner_status",
  "created_utc": "2026-06-03T06:00:14Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-OWNER",
  "last_seen_utc": "2026-06-05T08:45:05Z",
  "luke_action_required": "1",
  "manager_action": "Needs protected decision: approve a bounded F source-shape recovery preview for the active row, or leave F parked. Do not edit active rows from MOT.",
  "notes": "blocked_source_shape_guard",
  "observed_utc": "2026-06-05T08:45:05Z",
  "priority": "high",
  "producer": "FPM130_run_live_cycle.py / FPM170_supervise_live_cycle.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_live_owner_status` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "source_shape_guard:unit_cost_not_positive_numeric|count=1|sample_row_key=9639381947e967ce6636787a0e82b723e39a1acc|sample_supplier_sku=GCT019|sample_supplier_title=",
  "safe_repair_boundary": "Owner proof only; no F061 run, no restart, no queue edit, no scanner repair.",
  "seen_count": "31",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\live_cycle_status.csv",
  "status": "blocked_needs_luke",
  "title": "F MOT: f_live_owner_status needs Luke decision",
  "updated_utc": "2026-06-05T08:45:05Z",
  "work_item_id": "MOT_F_F_LIVE_OWNER_STATUS"
}
```
