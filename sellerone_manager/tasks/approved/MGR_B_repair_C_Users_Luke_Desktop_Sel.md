# Repair B blocked proof evidence

## Manager Authority
- task_id: MGR_B_repair_C_Users_Luke_Desktop_Sel
- job_ref: B-EVIDENCE-USERS-LUKE
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
- source_id: B_repair_C_Users_Luke_Desktop_Sel
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\B_cycle_expectations.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, B expectation mapping, B proof planning, and scoped Codex repair task creation",
  "flow": "B",
  "forbidden_actions": "no overlapping B run; no worker restart; no legacy Sheet write; no token/data correction without approved task",
  "needs_luke_decision": "0",
  "notes": "Mapped B MOT row needs a protected decision: b_pnl_daily.",
  "observed_utc": "2026-05-30T18:58:17Z",
  "priority": "high",
  "proof_required": "Use B independent MOT proof first. Use B maintenance handoff and a boundary-safe B_RUN_ONCE proof only when a manual B proof is approved.",
  "root_artifact": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\project_control\\EXPECTATIONS\\B_cycle_expectations.md",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "B_repair_C_Users_Luke_Desktop_Sel",
  "task_type": "repair",
  "title": "Repair B blocked proof evidence"
}
```
