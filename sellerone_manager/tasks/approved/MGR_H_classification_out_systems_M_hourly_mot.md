# Classify H active WARN group

## Manager Authority
- task_id: MGR_H_classification_out_systems_M_hourly_mot
- job_ref: H-CLASSIFY-ACTIVE-GROUP
- status: proved
- authority: manager_task_packaging_only
- luke_action_required: 0

## Boundary
- allowed_scope: manager classification, H expectation mapping, H repair package creation, and proof planning
- forbidden_actions: no live H overlap outside a manager-approved proof window; no price write change; no scheduler ownership change outside controlled technical pause/resume proof; no worker run without approved H proof window
- proof_required: Use guarded H isolation or scheduler-owned proof; confirm terminal and publish truth before claiming success.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: H_classification_out_systems_M_hourly_mot
- source_path: out\systems\M\hourly_mot_H.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, H expectation mapping, H repair package creation, and proof planning",
  "flow": "H",
  "forbidden_actions": "no live H overlap outside a manager-approved proof window; no price write change; no scheduler ownership change outside controlled technical pause/resume proof; no worker run without approved H proof window",
  "needs_luke_decision": "0",
  "notes": "3 active WARN/stale rows found.",
  "observed_utc": "2026-05-30T21:07:39Z",
  "priority": "normal",
  "proof_required": "Use guarded H isolation or scheduler-owned proof; confirm terminal and publish truth before claiming success.",
  "root_artifact": "out\\systems\\M\\hourly_mot_H.csv",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "H_classification_out_systems_M_hourly_mot",
  "task_type": "classification",
  "title": "Classify H active WARN group"
}
```
