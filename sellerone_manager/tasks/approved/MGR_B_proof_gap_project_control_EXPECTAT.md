# Add or confirm B manager proof coverage

## Manager Authority
- task_id: MGR_B_proof_gap_project_control_EXPECTAT
- job_ref: B-ADD-OR-CONFIRM
- status: proved
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
- source_id: B_proof_gap_project_control_EXPECTAT
- source_path: project_control/EXPECTATIONS/B_cycle_expectations.md

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, B expectation mapping, B proof planning, and scoped Codex repair task creation",
  "flow": "B",
  "forbidden_actions": "no overlapping B run; no worker restart; no legacy Sheet write; no token/data correction without approved task",
  "needs_luke_decision": "0",
  "notes": "5 expectations are not yet manager-verified.",
  "observed_utc": "2026-05-31T06:05:58Z",
  "priority": "low",
  "proof_required": "Use B independent MOT proof first. Use B maintenance handoff and a boundary-safe B_RUN_ONCE proof only when a manual B proof is approved.",
  "root_artifact": "project_control/EXPECTATIONS/B_cycle_expectations.md",
  "status": "proposed",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "B_proof_gap_project_control_EXPECTAT",
  "task_type": "proof_gap",
  "title": "Add or confirm B manager proof coverage"
}
```
