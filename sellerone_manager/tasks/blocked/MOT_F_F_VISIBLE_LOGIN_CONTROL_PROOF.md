# F MOT: f_visible_login_control_proof needs Luke decision

## Manager Authority
- task_id: MOT_F_F_VISIBLE_LOGIN_CONTROL_PROOF
- job_ref: F-VISIBLE-LOGIN-CONTROL-02
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Visible-login proof only; no separate Chrome login window, no F061 run, no worker restart, no maintenance-marker change, and no queue edit.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_visible_login_control_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_VISIBLE_LOGIN_CONTROL_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f061_visible_login.requested

## Exact Source Row
```json
{
  "allowed_scope": "Visible-login proof only; no separate Chrome login window, no F061 run, no worker restart, no maintenance-marker change, and no queue edit.",
  "check": "f_visible_login_control_proof",
  "created_utc": "2026-06-04T09:00:24Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-VISIBLE-LOGIN-CONTROL",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "1",
  "manager_action": "Do not open a separate browser from MOT. Keep F login recovery on the normal script-owned F061 path unless Luke approves otherwise.",
  "notes": "requested",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "FPM160_f061_visible_login_maintenance.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_visible_login_control_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "A separate visible-login maintenance request is active for F.",
  "safe_repair_boundary": "Visible-login proof only; no separate Chrome login window, no F061 run, no worker restart, no maintenance-marker change, and no queue edit.",
  "seen_count": "38",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\f061_visible_login.requested",
  "status": "blocked_needs_luke",
  "title": "F MOT: f_visible_login_control_proof needs Luke decision",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_F_F_VISIBLE_LOGIN_CONTROL_PROOF"
}
```
