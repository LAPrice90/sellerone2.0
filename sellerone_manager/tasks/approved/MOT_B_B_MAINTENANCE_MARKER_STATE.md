# B MOT: b_maintenance_marker_state needs repair

## Manager Authority
- task_id: MOT_B_B_MAINTENANCE_MARKER_STATE
- job_ref: B-MAINTENANCE-MARKER
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B maintenance proof only; no marker edits, restart, or worker run.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_maintenance_marker_state` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_MAINTENANCE_MARKER_STATE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\maintenance.requested;C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\maintenance.ready;C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\maintenance.active;C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\b_cycle.maintenance

## Exact Source Row
```json
{
  "allowed_scope": "B maintenance proof only; no marker edits, restart, or worker run.",
  "check": "b_maintenance_marker_state",
  "created_utc": "2026-05-28T05:00:17Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-MAINTENANCE-MARKER",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "If fail, stop and package ownership proof. Do not create, clear, or edit maintenance markers from MOT.",
  "notes": "active_marker_while_b_owner_present",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "B/A maintenance handoff",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_maintenance_marker_state` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Maintenance active marker and B worker ownership are both visible.",
  "safe_repair_boundary": "B maintenance proof only; no marker edits, restart, or worker run.",
  "seen_count": "39",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\maintenance.requested;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\maintenance.ready;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\maintenance.active;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\b_cycle.maintenance",
  "status": "new",
  "title": "B MOT: b_maintenance_marker_state needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_B_B_MAINTENANCE_MARKER_STATE"
}
```
