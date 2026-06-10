# Add or confirm E manager proof coverage

## Manager Authority
- task_id: MGR_E_proof_gap_project_control_EXPECTAT
- job_ref: E-ADD-OR-CONFIRM
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
- source_id: E_proof_gap_project_control_EXPECTAT
- source_path: project_control/EXPECTATIONS/E_cycle_expectations.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, E expectation mapping, E proof summary planning, and scoped Codex repair task creation",
  "flow": "E",
  "forbidden_actions": "no publish enablement; no legacy Sheet write; no worker run unless separately approved as E-owned proof",
  "job_ref": "E-ADD-OR-CONFIRM",
  "needs_luke_decision": "0",
  "notes": "3 expectations are not yet manager-verified.",
  "observed_utc": "2026-06-04T11:14:22Z",
  "priority": "low",
  "proof_required": "Use E-owned run logs and E-scoped health; keep E proof separate from global health.",
  "root_artifact": "project_control/EXPECTATIONS/E_cycle_expectations.md",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "E_proof_gap_project_control_EXPECTAT",
  "task_type": "proof_gap",
  "title": "Add or confirm E manager proof coverage"
}
```
