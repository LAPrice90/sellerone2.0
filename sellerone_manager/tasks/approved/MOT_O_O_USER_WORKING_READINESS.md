# O MOT: o_user_working_readiness needs repair

## Manager Authority
- task_id: MOT_O_O_USER_WORKING_READINESS
- job_ref: O-USER-WORKING-READINESS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: User walkthrough and manager proof only; no purchase commitment, PO creation, receiving action, send-to-Amazon action, Sheet write, price change, queue edit, DB alignment, output deletion, H pause, or market scan.
- forbidden_actions: no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_user_working_readiness` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_O_O_USER_WORKING_READINESS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\scripts\flows\O\O400_operator_ui.py;C:\Users\Luke\Desktop\SellerOne 2.0\scripts\flows\O\O410_product_database_ui.py;C:\Users\Luke\Desktop\SellerOne 2.0\scripts\flows\O\O420_product_database_edit_ui.py;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\product_db_operator_view.csv

## Exact Source Row
```json
{
  "allowed_scope": "User walkthrough and manager proof only; no purchase commitment, PO creation, receiving action, send-to-Amazon action, Sheet write, price change, queue edit, DB alignment, output deletion, H pause, or market scan.",
  "check": "o_user_working_readiness",
  "created_utc": "2026-05-29T10:00:15Z",
  "flow": "O",
  "forbidden_actions": "no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening",
  "job_ref": "O-USER-WORKING-READINESS",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded O user-working repair packet. Do not run H pause, market scans, PO, receiving, send-to-Amazon, Sheets, prices, queues, DB alignment, or output deletion.",
  "notes": "not_ready;safety_blockers=1;tolerated_warnings=5",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "O manager readiness gate",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_user_working_readiness` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow O",
  "root_cause_guess": "O is not safe enough for a user walkthrough because a built safety or UI proof is missing or failing.",
  "safe_repair_boundary": "User walkthrough and manager proof only; no purchase commitment, PO creation, receiving action, send-to-Amazon action, Sheet write, price change, queue edit, DB alignment, output deletion, H pause, or market scan.",
  "seen_count": "417",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\scripts\\flows\\O\\O400_operator_ui.py;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\scripts\\flows\\O\\O410_product_database_ui.py;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\scripts\\flows\\O\\O420_product_database_edit_ui.py;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\product_db_operator_view.csv",
  "status": "new",
  "title": "O MOT: o_user_working_readiness needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_O_O_USER_WORKING_READINESS"
}
```
