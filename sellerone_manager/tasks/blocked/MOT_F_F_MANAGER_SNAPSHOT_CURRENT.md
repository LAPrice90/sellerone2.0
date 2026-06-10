# F MOT: f_manager_snapshot_current needs Luke decision

## Manager Authority
- task_id: MOT_F_F_MANAGER_SNAPSHOT_CURRENT
- job_ref: F-MANAGER-SNAPSHOT-CURRENT
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Manager snapshot proof only; no F061 run, queue edit, handoff approval, or scanner repair.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_manager_snapshot_current` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_MANAGER_SNAPSHOT_CURRENT
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\f_price_list_manager_snapshot.csv

## Exact Source Row
```json
{
  "allowed_scope": "Manager snapshot proof only; no F061 run, queue edit, handoff approval, or scanner repair.",
  "check": "f_manager_snapshot_current",
  "created_utc": "2026-05-28T01:00:17Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-MANAGER-SNAPSHOT-CURRENT",
  "last_seen_utc": "2026-06-05T08:45:05Z",
  "luke_action_required": "1",
  "manager_action": "Approve a bounded F source-shape recovery preview for the active row, or leave F parked.",
  "notes": "needs_user",
  "observed_utc": "2026-06-05T08:45:05Z",
  "priority": "high",
  "producer": "sellerone_manager.f_price_list_snapshot",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_manager_snapshot_current` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "source_shape_guard:unit_cost_not_positive_numeric|count=1|sample_row_key=9639381947e967ce6636787a0e82b723e39a1acc|sample_supplier_sku=GCT019|sample_supplier_title=",
  "safe_repair_boundary": "Manager snapshot proof only; no F061 run, queue edit, handoff approval, or scanner repair.",
  "seen_count": "124",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\f_price_list_manager_snapshot.csv",
  "status": "blocked_needs_luke",
  "title": "F MOT: f_manager_snapshot_current needs Luke decision",
  "updated_utc": "2026-06-05T08:45:05Z",
  "work_item_id": "MOT_F_F_MANAGER_SNAPSHOT_CURRENT"
}
```
