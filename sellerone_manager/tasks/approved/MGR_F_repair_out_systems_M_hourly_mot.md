# Repair F active FAIL group

## Manager Authority
- task_id: MGR_F_repair_out_systems_M_hourly_mot
- job_ref: F-ACTIVE-FAIL-GROUP
- status: approved
- authority: manager_task_packaging_only
- luke_action_required: 0

## Boundary
- allowed_scope: manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning
- forbidden_actions: no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change
- proof_required: Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: F_repair_out_systems_M_hourly_mot
- source_path: out\systems\M\hourly_mot_F.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
  "flow": "F",
  "forbidden_actions": "no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
  "job_ref": "F-ACTIVE-FAIL-GROUP",
  "needs_luke_decision": "0",
  "notes": "1 active FAIL/blocker rows found.",
  "observed_utc": "2026-06-09T14:29:22Z",
  "priority": "high",
  "proof_required": "Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
  "root_artifact": "out\\systems\\M\\hourly_mot_F.csv",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "F_repair_out_systems_M_hourly_mot",
  "task_type": "repair",
  "title": "Repair F active FAIL group"
}
```
