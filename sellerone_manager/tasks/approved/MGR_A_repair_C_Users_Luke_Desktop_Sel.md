# Repair A blocked proof evidence

## Manager Authority
- task_id: MGR_A_repair_C_Users_Luke_Desktop_Sel
- job_ref: A-BLOCKED-EVIDENCE-USERS
- status: in_progress
- authority: manager_task_packaging_only
- luke_action_required: 0

## Boundary
- allowed_scope: manager classification, A expectation mapping, A proof planning, and scoped Codex repair task creation
- forbidden_actions: no ad hoc A015 proof; no worker cycle run; no B overlap; no legacy Sheet write; no local DB alignment; no pricing change
- proof_required: Use the next A-owned run or an explicitly approved A-owned proof window; do not run A015 ad hoc as proof.
- retest_command: 
- rollback_path: No worker rollback path. This task may only package manager scope, proof, and stop conditions.
- stop_condition: Stop after manager classification, task packaging, and proof path are recorded for this flow.

## Source
- source_type: manager_candidate
- source_id: A_repair_C_Users_Luke_Desktop_Sel
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\A\live\a_maintenance_handoff_latest.json

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, A expectation mapping, A proof planning, and scoped Codex repair task creation",
  "flow": "A",
  "forbidden_actions": "no ad hoc A015 proof; no worker cycle run; no B overlap; no legacy Sheet write; no local DB alignment; no pricing change",
  "job_ref": "A-BLOCKED-EVIDENCE-USERS",
  "needs_luke_decision": "0",
  "notes": "A maintenance handoff proof recorded an unsafe or failed handoff.",
  "observed_utc": "2026-06-09T12:56:49Z",
  "priority": "high",
  "proof_required": "Use the next A-owned run or an explicitly approved A-owned proof window; do not run A015 ad hoc as proof.",
  "root_artifact": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\A\\live\\a_maintenance_handoff_latest.json",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "A_repair_C_Users_Luke_Desktop_Sel",
  "task_type": "repair",
  "title": "Repair A blocked proof evidence"
}
```
