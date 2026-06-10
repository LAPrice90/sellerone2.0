# Decide F protected proof evidence

## Manager Authority
- task_id: MGR_F_user_decision_C_Users_Luke_Desktop_Sel
- job_ref: F-DECIDE-EVIDENCE-USER
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
- source_id: F_user_decision_C_Users_Luke_Desktop_Sel
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\F_cycle_expectations.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
  "flow": "F",
  "forbidden_actions": "no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
  "job_ref": "F-DECIDE-EVIDENCE-USER",
  "needs_luke_decision": "1",
  "notes": "Mapped F MOT row needs a protected decision: f_seller_central_eligibility_auth_state.",
  "observed_utc": "2026-06-07T09:52:25Z",
  "priority": "high",
  "proof_required": "Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
  "root_artifact": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\project_control\\EXPECTATIONS\\F_cycle_expectations.md",
  "status": "blocked_needs_user_decision",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "F_user_decision_C_Users_Luke_Desktop_Sel",
  "task_type": "user_decision",
  "title": "Decide F protected proof evidence"
}
```
