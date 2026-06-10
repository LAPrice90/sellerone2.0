# Repair B active FAIL group

## Manager Authority
- task_id: MGR_B_repair_out_systems_M_hourly_mot
- job_ref: B-ACTIVE-FAIL-GROUP
- status: approved
- authority: manager_task_packaging_only
- luke_action_required: 0

## Boundary
- allowed_scope: manager classification, B expectation mapping, B proof planning, and scoped Codex repair task creation
- forbidden_actions: no overlapping B run; no worker restart; no legacy Sheet write; no token/data correction without approved task
- proof_required: Use B independent MOT proof first. Use B maintenance handoff and a boundary-safe B_RUN_ONCE proof only when a manual B proof is approved.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: B_repair_out_systems_M_hourly_mot
- source_path: out\systems\M\hourly_mot_B.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, B expectation mapping, B proof planning, and scoped Codex repair task creation",
  "flow": "B",
  "forbidden_actions": "no overlapping B run; no worker restart; no legacy Sheet write; no token/data correction without approved task",
  "job_ref": "B-ACTIVE-FAIL-GROUP",
  "needs_luke_decision": "0",
  "notes": "4 active FAIL/blocker rows found.",
  "observed_utc": "2026-06-09T14:29:22Z",
  "priority": "high",
  "proof_required": "Use B independent MOT proof first. Use B maintenance handoff and a boundary-safe B_RUN_ONCE proof only when a manual B proof is approved.",
  "root_artifact": "out\\systems\\M\\hourly_mot_B.csv",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "B_repair_out_systems_M_hourly_mot",
  "task_type": "repair",
  "title": "Repair B active FAIL group"
}
```
