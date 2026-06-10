# F MOT: f_login_mode_state needs repair

## Manager Authority
- task_id: MOT_F_F_LOGIN_MODE_STATE
- job_ref: F-LOGIN-MODE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Login proof only; no separate Chrome workaround, no scanner run, no worker restart.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_login_mode_state` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_LOGIN_MODE_STATE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f061_login_mode.requested

## Exact Source Row
```json
{
  "allowed_scope": "Login proof only; no separate Chrome workaround, no scanner run, no worker restart.",
  "check": "f_login_mode_state",
  "created_utc": "2026-05-28T01:00:17Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-LOGIN-MODE",
  "last_seen_utc": "2026-06-09T07:00:25Z",
  "luke_action_required": "0",
  "manager_action": "Classify login recovery state before running any scanner proof.",
  "notes": "still_required",
  "observed_utc": "2026-06-09T07:00:25Z",
  "priority": "high",
  "producer": "FPM130_run_live_cycle.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_login_mode_state` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "F login mode request is stale and not drained.",
  "safe_repair_boundary": "Login proof only; no separate Chrome workaround, no scanner run, no worker restart.",
  "seen_count": "153",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\f061_login_mode.requested",
  "status": "new",
  "title": "F MOT: f_login_mode_state needs repair",
  "updated_utc": "2026-06-09T07:00:25Z",
  "work_item_id": "MOT_F_F_LOGIN_MODE_STATE"
}
```
