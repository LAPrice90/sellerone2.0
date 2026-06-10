# H MOT: h_token_floor_source_guard needs repair

## Manager Authority
- task_id: MOT_H_H_TOKEN_FLOOR_SOURCE_GUARD
- job_ref: H-TOKEN-FLOOR-SOURCE
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_token_floor_source_guard` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_TOKEN_FLOOR_SOURCE_GUARD
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\phase1_runtime_floor_snapshot_latest.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\h_floor_truth_trace.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\token_ledger_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_fallback_token_cost_audit.csv

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_token_floor_source_guard",
  "created_utc": "2026-06-05T13:37:49Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-TOKEN-FLOOR-SOURCE-GUARD",
  "last_seen_utc": "2026-06-05T14:06:39Z",
  "luke_action_required": "0",
  "manager_action": "If warn, keep the H floor source visible and package the token-source fix separately. Do not change H prices, token rows, Sheets, or local DB facts from this guard.",
  "notes": "H token-floor source guard now uses B071 fallback reconciliation. Current H MOT labels 1 batch-link-proof-needed row and parks the warning as manager-visible truth; no H run, price change, token correction, Sheet write, DB alignment, output deletion, or restart.",
  "observed_utc": "2026-06-05T14:06:39Z",
  "priority": "normal",
  "producer": "H floor truth / B token ledger proof",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_token_floor_source_guard` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "H can calculate the floor, but at least one current floor uses fallback, weak, unproved, or unknown token cost proof.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "18",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\phase1_runtime_floor_snapshot_latest.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\h_floor_truth_trace.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\token_ledger_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_fallback_token_cost_audit.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_fallback_cost_proof_reconciliation.csv",
  "status": "proved",
  "title": "H MOT: h_token_floor_source_guard needs repair",
  "updated_utc": "2026-06-05T14:07:59Z",
  "work_item_id": "MOT_H_H_TOKEN_FLOOR_SOURCE_GUARD"
}
```
