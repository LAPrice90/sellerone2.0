# Classify F active WARN group

## Manager Authority
- task_id: MGR_F_classification_out_systems_M_f_price_li
- job_ref: F-CLASSIFY-ACTIVE-WARN
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
- source_id: F_classification_out_systems_M_f_price_li
- source_path: out\systems\M\f_price_list_manager_snapshot.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
  "flow": "F",
  "forbidden_actions": "no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
  "job_ref": "F-CLASSIFY-ACTIVE-WARN",
  "needs_luke_decision": "0",
  "notes": "1 active WARN/stale rows found.",
  "observed_utc": "2026-06-04T11:34:52Z",
  "priority": "normal",
  "proof_required": "Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
  "root_artifact": "out\\systems\\M\\f_price_list_manager_snapshot.csv",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "F_classification_out_systems_M_f_price_li",
  "task_type": "classification",
  "title": "Classify F active WARN group"
}
```
