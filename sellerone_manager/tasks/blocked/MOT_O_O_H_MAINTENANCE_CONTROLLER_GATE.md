# O MOT: o_h_maintenance_controller_gate needs Luke decision

## Manager Authority
- task_id: MOT_O_O_H_MAINTENANCE_CONTROLLER_GATE
- job_ref: O-MAINTENANCE-CONTROLLER-GATE-02
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Controller proof only; no H pause/resume unless an approved proof packet exists, and no market scan, purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.
- forbidden_actions: no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_h_maintenance_controller_gate` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_O_O_H_MAINTENANCE_CONTROLLER_GATE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\h_maintenance_controller_install_status.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\locks\h_maintenance_controller_last_result.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\h_maintenance_controller_status.json

## Exact Source Row
```json
{
  "allowed_scope": "Controller proof only; no H pause/resume unless an approved proof packet exists, and no market scan, purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.",
  "check": "o_h_maintenance_controller_gate",
  "created_utc": "2026-05-27T15:01:50Z",
  "flow": "O",
  "forbidden_actions": "no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening",
  "last_seen_utc": "2026-05-27T15:02:13Z",
  "luke_action_required": "1",
  "manager_action": "Luke must run the one-time H maintenance controller installer as Administrator before Codex can automate H pause/resume requests.",
  "notes": "admin_install_required",
  "observed_utc": "2026-05-27T15:02:13Z",
  "priority": "high",
  "producer": "H200_request_h_maintenance.py / h_maintenance_controller.ps1",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_h_maintenance_controller_gate` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow O",
  "root_cause_guess": "The controller installer was tested from a non-admin shell and correctly refused to install.",
  "safe_repair_boundary": "Controller proof only; no H pause/resume unless an approved proof packet exists, and no market scan, purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\h_maintenance_controller_install_status.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\locks\\h_maintenance_controller_last_result.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\H\\live\\h_maintenance_controller_status.json",
  "status": "blocked_needs_luke",
  "title": "O MOT: o_h_maintenance_controller_gate needs Luke decision",
  "updated_utc": "2026-05-27T15:02:13Z",
  "work_item_id": "MOT_O_O_H_MAINTENANCE_CONTROLLER_GATE"
}
```
