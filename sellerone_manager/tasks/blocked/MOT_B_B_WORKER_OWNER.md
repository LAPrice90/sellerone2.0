# B MOT: b_worker_owner needs repair

## Manager Authority
- task_id: MOT_B_B_WORKER_OWNER
- job_ref: B-WORKER-OWNER-02
- status: blocked_needs_luke
- authority: standing_safe_code_repair
- luke_action_required: 1

## Boundary
- allowed_scope: B ownership proof only; no lock deletion, restart, or worker run.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_worker_owner` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_WORKER_OWNER
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\live\B_cycle.lock;C:\Users\Luke\Desktop\SellerOne 2.0\out\B_cycle.lock

## Exact Source Row
```json
{
  "allowed_scope": "B ownership proof only; no lock deletion, restart, or worker run.",
  "check": "b_worker_owner",
  "created_utc": "2026-05-27T09:08:19Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T10:45:00Z",
  "luke_action_required": "0",
  "manager_action": "If fail, package a B ownership repair. Do not clear locks or restart B from MOT.",
  "notes": "B worker ownership proof is stale/dead. Resolving it would require protected B restart, lock action, or live B recovery approval.",
  "observed_utc": "2026-05-27T10:45:00Z",
  "priority": "high",
  "producer": "scripts/cycles/run_B_cycle.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_worker_owner` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "B worker lock exists, but heartbeat or process evidence is stale or dead.",
  "safe_repair_boundary": "B ownership proof only; no lock deletion, restart, or worker run.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\live\\B_cycle.lock;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\B_cycle.lock",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_worker_owner needs repair",
  "updated_utc": "2026-05-27T10:45:00Z",
  "work_item_id": "MOT_B_B_WORKER_OWNER"
}
```
