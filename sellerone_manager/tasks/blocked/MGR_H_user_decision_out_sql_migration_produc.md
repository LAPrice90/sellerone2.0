# Confirm repricer tracker UI can replace Sheet after one normal operating day

## Manager Authority
- task_id: MGR_H_user_decision_out_sql_migration_produc
- job_ref: H-CONFIRM-REPRICER-TRACKER
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: manager classification, H expectation mapping, H repair package creation, and proof planning
- forbidden_actions: no live H overlap outside a manager-approved proof window; no price write change; no scheduler ownership change outside controlled technical pause/resume proof; no worker run without approved H proof window
- proof_required: Use guarded H isolation or scheduler-owned proof; confirm terminal and publish truth before claiming success.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: H_user_decision_out_sql_migration_produc
- source_path: out/sql_migration/product_db_contract/repricer_tracker_ui_parity_summary.json

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, H expectation mapping, H repair package creation, and proof planning",
  "flow": "H",
  "forbidden_actions": "no live H overlap outside a manager-approved proof window; no price write change; no scheduler ownership change outside controlled technical pause/resume proof; no worker run without approved H proof window",
  "needs_luke_decision": "1",
  "notes": "Latest parity summary is stale at 2026-05-02T11:58:20Z with fail_count=0 and tracker_rows=89; cannot confirm one normal operating day of UI-as-main-tracker usage without operator decision or a fresh P017/P016 observation run.",
  "observed_utc": "2026-05-27T18:28:51Z",
  "priority": "high",
  "proof_required": "Use guarded H isolation or scheduler-owned proof; confirm terminal and publish truth before claiming success.",
  "root_artifact": "out/sql_migration/product_db_contract/repricer_tracker_ui_parity_summary.json",
  "status": "blocked_needs_user_decision",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "H_user_decision_out_sql_migration_produc",
  "task_type": "user_decision",
  "title": "Confirm repricer tracker UI can replace Sheet after one normal operating day"
}
```
