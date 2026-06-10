# Review unresolved Entertainment Trading dashboard Yes/No backtrack row

## Manager Authority
- task_id: MGR_F_user_decision_out_systems_F_live_f_log
- job_ref: F-REVIEW-UNRESOLVED-ENTERTAINMENT
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
- source_id: F_user_decision_out_systems_F_live_f_log
- source_path: out/systems/F/live/f_login_backtrack_evidence_live.csv

## Exact Source Row
```json
{
  "allowed_scope": "manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
  "flow": "F",
  "forbidden_actions": "no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
  "needs_luke_decision": "1",
  "notes": "Still unresolved for supplier_sku 1243976 / ASIN B0000DC4EL: latest attempt 5 is dashboard_yes_no_unresolved, merged_into_candidate_flag=0. Do not publish ET row until targeted authenticated backtrack succeeds or manual-review exception is approved.",
  "observed_utc": "2026-05-27T18:28:51Z",
  "priority": "high",
  "proof_required": "Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
  "root_artifact": "out/systems/F/live/f_login_backtrack_evidence_live.csv",
  "status": "blocked_needs_user_decision",
  "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
  "task_id": "F_user_decision_out_systems_F_live_f_log",
  "task_type": "user_decision",
  "title": "Review unresolved Entertainment Trading dashboard Yes/No backtrack row"
}
```
