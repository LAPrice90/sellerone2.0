# Repair E active FAIL group

## Manager Authority
- task_id: MGR_E_repair_out_systems_M_hourly_mot
- job_ref: E-ACTIVE-GROUP-OUT
- status: approved
- authority: manager_task_packaging_only
- luke_action_required: 0

## Boundary
- allowed_scope: manager classification, E expectation mapping, E proof summary planning, and scoped Codex repair task creation
- forbidden_actions: no publish enablement; no legacy Sheet write; no worker run unless separately approved as E-owned proof
- proof_required: Use E-owned run logs and E-scoped health; keep E proof separate from global health.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: E_repair_out_systems_M_hourly_mot
- source_path: out\systems\M\hourly_mot_E.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, E expectation mapping, E proof summary planning, and scoped Codex repair task creation",
  "flow": "E",
  "forbidden_actions": "no publish enablement; no legacy Sheet write; no worker run unless separately approved as E-owned proof",
  "needs_luke_decision": "0",
  "notes": "1 active FAIL/blocker rows found.",
  "observed_utc": "2026-06-01T13:49:03Z",
  "priority": "high",
  "proof_required": "Use E-owned run logs and E-scoped health; keep E proof separate from global health.",
  "root_artifact": "out\\systems\\M\\hourly_mot_E.csv",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "E_repair_out_systems_M_hourly_mot",
  "task_type": "repair",
  "title": "Repair E active FAIL group"
}
```
