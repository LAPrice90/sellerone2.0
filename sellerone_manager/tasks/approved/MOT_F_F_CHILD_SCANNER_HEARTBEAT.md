# F MOT: f_child_scanner_heartbeat needs repair

## Manager Authority
- task_id: MOT_F_F_CHILD_SCANNER_HEARTBEAT
- job_ref: F-CHILD-SCANNER-HEARTBEAT
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Heartbeat proof only; no worker restart, no scanner run, no process kill.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_child_scanner_heartbeat` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_CHILD_SCANNER_HEARTBEAT
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f061_child_status.txt

## Exact Source Row
```json
{
  "allowed_scope": "Heartbeat proof only; no worker restart, no scanner run, no process kill.",
  "check": "f_child_scanner_heartbeat",
  "created_utc": "2026-06-05T23:37:36Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-CHILD-SCANNER-HEARTBEAT",
  "last_seen_utc": "2026-06-09T01:00:26Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded F owner/child proof task. Do not restart workers from MOT.",
  "notes": "39479s",
  "observed_utc": "2026-06-09T01:00:26Z",
  "priority": "high",
  "producer": "F061 child process status writer",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_child_scanner_heartbeat` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "F owner says running, but scanner child heartbeat is stale.",
  "safe_repair_boundary": "Heartbeat proof only; no worker restart, no scanner run, no process kill.",
  "seen_count": "21",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\f061_child_status.txt",
  "status": "new",
  "title": "F MOT: f_child_scanner_heartbeat needs repair",
  "updated_utc": "2026-06-09T01:00:26Z",
  "work_item_id": "MOT_F_F_CHILD_SCANNER_HEARTBEAT"
}
```
