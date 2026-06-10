# H MOT: h_manager_readiness needs repair

## Manager Authority
- task_id: MOT_H_H_MANAGER_READINESS
- job_ref: H-READINESS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_manager_readiness` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_MANAGER_READINESS
- source_path: 

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_manager_readiness",
  "created_utc": "2026-05-27T21:06:44Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "last_seen_utc": "2026-05-30T21:00:16Z",
  "luke_action_required": "0",
  "manager_action": "If fail, keep H parked and create bounded proof tasks. First build the H manager/MOT layer, then repairs become controlled.",
  "notes": "not_ready;failed_checks=1",
  "observed_utc": "2026-05-30T21:00:16Z",
  "priority": "high",
  "producer": "sellerone_manager.hourly_mot",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_manager_readiness` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "H is not independently manager-proven from outside evidence.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "93",
  "source_path": "",
  "status": "new",
  "title": "H MOT: h_manager_readiness needs repair",
  "updated_utc": "2026-05-30T21:00:16Z",
  "work_item_id": "MOT_H_H_MANAGER_READINESS"
}
```
