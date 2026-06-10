# Add or confirm A manager proof coverage

## Manager Authority
- task_id: MGR_A_proof_gap_project_control_EXPECTAT
- job_ref: A-ADD-OR-CONFIRM
- status: parked
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
- source_id: A_proof_gap_project_control_EXPECTAT
- source_path: project_control/EXPECTATIONS/A_cycle_expectations.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, A expectation mapping, A proof planning, and scoped Codex repair task creation",
  "flow": "A",
  "forbidden_actions": "no ad hoc A015 proof; no worker cycle run; no B overlap; no legacy Sheet write; no local DB alignment; no pricing change",
  "needs_luke_decision": "0",
  "notes": "2 expectations are not yet manager-verified.",
  "observed_utc": "2026-05-27T18:43:02Z",
  "priority": "low",
  "proof_required": "Use the next A-owned run or an explicitly approved A-owned proof window; do not run A015 ad hoc as proof.",
  "root_artifact": "project_control/EXPECTATIONS/A_cycle_expectations.md",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "A_proof_gap_project_control_EXPECTAT",
  "task_type": "proof_gap",
  "title": "Add or confirm A manager proof coverage"
}
```
