# H MOT: h_floor_ceiling_safety_fields needs repair

## Manager Authority
- task_id: MOT_H_H_FLOOR_CEILING_SAFETY_FIELDS
- job_ref: H-FLOOR-CEILING-SAFETY
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_floor_ceiling_safety_fields` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_FLOOR_CEILING_SAFETY_FIELDS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\phase1_runtime_floor_snapshot_latest.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\h_floor_truth_trace.csv

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_floor_ceiling_safety_fields",
  "created_utc": "2026-05-27T21:06:44Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-FLOOR-CEILING-SAFETY",
  "last_seen_utc": "2026-06-05T14:40:18Z",
  "luke_action_required": "0",
  "manager_action": "If fail, create a bounded H floor/ceiling proof task at the source. Do not change prices from MOT.",
  "notes": "blank_floor_rows=0;blank_ceiling_rows=1",
  "observed_utc": "2026-06-05T14:40:18Z",
  "priority": "high",
  "producer": "H floor truth / runtime snapshot",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_floor_ceiling_safety_fields` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "H has current-cycle pricing rows without populated floor or ceiling proof.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "112",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\phase1_runtime_floor_snapshot_latest.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\h_floor_truth_trace.csv",
  "status": "new",
  "title": "H MOT: h_floor_ceiling_safety_fields needs repair",
  "updated_utc": "2026-06-05T14:40:18Z",
  "work_item_id": "MOT_H_H_FLOOR_CEILING_SAFETY_FIELDS"
}
```
