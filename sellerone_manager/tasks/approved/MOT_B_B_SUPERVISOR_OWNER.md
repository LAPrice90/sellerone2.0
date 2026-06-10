# B MOT: b_supervisor_owner needs repair

## Manager Authority
- task_id: MOT_B_B_SUPERVISOR_OWNER
- job_ref: B-SUPERVISOR-OWNER
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B supervisor proof only; no restart or lock deletion.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_supervisor_owner` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_SUPERVISOR_OWNER
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\live\B_supervisor.lock

## Exact Source Row
```json
{
  "allowed_scope": "B supervisor proof only; no restart or lock deletion.",
  "check": "b_supervisor_owner",
  "created_utc": "2026-05-27T09:08:19Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T10:45:00Z",
  "luke_action_required": "0",
  "manager_action": "If fail, package a B supervisor ownership repair. Do not restart B from MOT.",
  "notes": "stale_or_dead",
  "observed_utc": "2026-05-27T10:45:00Z",
  "priority": "high",
  "producer": "scripts/cycles/run_B_supervisor.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_supervisor_owner` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "B supervisor heartbeat evidence is stale or missing.",
  "safe_repair_boundary": "B supervisor proof only; no restart or lock deletion.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\live\\B_supervisor.lock",
  "status": "new",
  "title": "B MOT: b_supervisor_owner needs repair",
  "updated_utc": "2026-05-27T10:45:00Z",
  "work_item_id": "MOT_B_B_SUPERVISOR_OWNER"
}
```
