# Execute Stax Login Mode plan from normal hidden scanner

## Manager Authority
- task_id: MGR_F_user_decision_project_control_feeder_s
- job_ref: F-EXECUTE-STAX-LOGIN
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning
- forbidden_actions: no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change
- proof_required: Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: F_user_decision_project_control_feeder_s
- source_path: project_control/feeder_scanner_speed/CODING_PLAN.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
  "flow": "F",
  "forbidden_actions": "no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
  "needs_luke_decision": "1",
  "notes": "Phase 9M matched Price List Manager shortcut exactly: normal hidden Chrome pid 25024 and visible Login Mode Chrome pid 30316 used Chrome_UC136/BBPProfile. Login button still not detected; DevTools showed no BuyBotPro extension worker and profile inspection showed BBPProfile lacks extension id docdmgijbdlobilamkipaleciekbgbgl. Chrome_UC136/Profile 2 has the BBP extension and laprice90@gmail.com.",
  "observed_utc": "2026-05-27T18:37:10Z",
  "priority": "high",
  "proof_required": "Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
  "root_artifact": "project_control/feeder_scanner_speed/CODING_PLAN.md",
  "status": "blocked_needs_user_decision",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "F_user_decision_project_control_feeder_s",
  "task_type": "user_decision",
  "title": "Execute Stax Login Mode plan from normal hidden scanner"
}
```
