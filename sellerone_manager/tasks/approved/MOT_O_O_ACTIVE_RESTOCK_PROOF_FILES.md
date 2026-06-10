# O MOT: o_active_restock_proof_files needs repair

## Manager Authority
- task_id: MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES
- job_ref: O-ACTIVE-RESTOCK-FILES
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: O proof-file mapping only; no worker run, no H pause, no Sheet write, no purchase action.
- forbidden_actions: no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_active_restock_proof_files` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_source_view.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_recommendations_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_review_queue.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\reorder_input_coverage_report.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\legacy_purchase_list_bridge.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\legacy_purchase_list_bridge_health.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_profit_checks_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_profit_check_health.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_market_refresh_candidates_live.csv

## Exact Source Row
```json
{
  "allowed_scope": "O proof-file mapping only; no worker run, no H pause, no Sheet write, no purchase action.",
  "check": "o_active_restock_proof_files",
  "created_utc": "2026-06-05T10:00:25Z",
  "flow": "O",
  "forbidden_actions": "no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening",
  "job_ref": "O-ACTIVE-RESTOCK-FILES",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded O manager-proof repair task. Do not run O worker actions or patch outputs to hide the gap.",
  "notes": "missing=0;short=0;unreadable=0;stale_warn=0;stale_fail=2",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "O manager proof map",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_active_restock_proof_files` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow O",
  "root_cause_guess": "One or more built O proof files are missing, unreadable, too short, or stale.",
  "safe_repair_boundary": "O proof-file mapping only; no worker run, no H pause, no Sheet write, no purchase action.",
  "seen_count": "380",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_source_view.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_recommendations_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_review_queue.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\reorder_input_coverage_report.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\legacy_purchase_list_bridge.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\legacy_purchase_list_bridge_health.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_profit_checks_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_profit_check_health.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_market_refresh_candidates_live.csv",
  "status": "assigned",
  "title": "O MOT: o_active_restock_proof_files needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES"
}
```
