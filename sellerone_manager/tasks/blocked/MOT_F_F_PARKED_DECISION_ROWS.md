# F MOT: f_parked_decision_rows needs Luke decision

## Manager Authority
- task_id: MOT_F_F_PARKED_DECISION_ROWS
- job_ref: F-ROWS-LUKE
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Decision proof only; do not publish, approve, queue-edit, or accept parked Entertainment Trading rows.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_parked_decision_rows` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_PARKED_DECISION_ROWS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\live\f_login_backtrack_evidence_live.csv

## Exact Source Row
```json
{
  "allowed_scope": "Decision proof only; do not publish, approve, queue-edit, or accept parked Entertainment Trading rows.",
  "check": "f_parked_decision_rows",
  "created_utc": "2026-05-27T16:29:23Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "last_seen_utc": "2026-05-27T16:29:23Z",
  "luke_action_required": "1",
  "manager_action": "Keep the row parked until Luke approves an exception or a targeted authenticated recovery proves it.",
  "notes": "1",
  "observed_utc": "2026-05-27T16:29:23Z",
  "priority": "high",
  "producer": "F061 login backtrack merge proof",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_parked_decision_rows` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "Unresolved F backtrack row remains parked: supplier_sku=CTUSBCFUSBAMAD;asin=B08FSDMVNP;status=missing_dashboard_yes_no.",
  "safe_repair_boundary": "Decision proof only; do not publish, approve, queue-edit, or accept parked Entertainment Trading rows.",
  "seen_count": "1",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\live\\f_login_backtrack_evidence_live.csv",
  "status": "blocked_needs_luke",
  "title": "F MOT: f_parked_decision_rows needs Luke decision",
  "updated_utc": "2026-05-27T16:29:23Z",
  "work_item_id": "MOT_F_F_PARKED_DECISION_ROWS"
}
```
