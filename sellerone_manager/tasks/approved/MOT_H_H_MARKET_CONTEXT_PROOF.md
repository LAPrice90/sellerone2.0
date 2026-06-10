# H MOT: h_market_context_proof needs repair

## Manager Authority
- task_id: MOT_H_H_MARKET_CONTEXT_PROOF
- job_ref: H-MARKET-CONTEXT
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_market_context_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_MARKET_CONTEXT_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\phase1_sku_scope.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\phase1_runtime_floor_snapshot_latest.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\listing_offer_history.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\listing_offer_seller_observation_history.csv

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_market_context_proof",
  "created_utc": "2026-05-27T21:06:44Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-MARKET-CONTEXT",
  "last_seen_utc": "2026-06-05T01:38:00Z",
  "luke_action_required": "0",
  "manager_action": "If fail, package a bounded H market-context proof task. Do not run H from MOT.",
  "notes": "priced_rows_missing_market_context=9",
  "observed_utc": "2026-06-05T01:38:00Z",
  "priority": "high",
  "producer": "H004/H offer collection",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_market_context_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "H attempted or recorded current-cycle decisions without market context proof.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "96",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\phase1_sku_scope.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\phase1_runtime_floor_snapshot_latest.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\listing_offer_history.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\listing_offer_seller_observation_history.csv",
  "status": "new",
  "title": "H MOT: h_market_context_proof needs repair",
  "updated_utc": "2026-06-05T01:38:00Z",
  "work_item_id": "MOT_H_H_MARKET_CONTEXT_PROOF"
}
```
