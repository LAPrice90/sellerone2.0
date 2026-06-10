# B MOT: b_pnl_daily needs Luke decision

## Manager Authority
- task_id: MOT_B_B_PNL_DAILY
- job_ref: B-PNL-DAILY
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Decision proof only; no B run, D001 run, token correction, stock correction, Sheet write, local DB alignment, output deletion, price change, queue edit, or downstream masking without Luke approval.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_pnl_daily` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_PNL_DAILY
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\pnl_daily.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\B\2026-06-04\B_20260604T133454Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\token_shortages_by_sku.csv

## Exact Source Row
```json
{
  "allowed_scope": "Decision proof only; no B run, D001 run, token correction, stock correction, Sheet write, local DB alignment, output deletion, price change, queue edit, or downstream masking without Luke approval.",
  "check": "b_pnl_daily",
  "created_utc": "2026-05-30T01:00:17Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-PNL-DAILY",
  "last_seen_utc": "2026-06-04T13:55:10Z",
  "luke_action_required": "1",
  "manager_action": "Stop B P and L repair work. Luke must choose whether to wait for receipt evidence or approve a bounded stock/token correction. Do not run D001, run B, write Sheets, align local DB data, or correct stock/token data from MOT.",
  "notes": "blocked_by_protected_token_shortage",
  "observed_utc": "2026-06-04T13:55:10Z",
  "priority": "high",
  "producer": "D001_build_pnl_daily.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_pnl_daily` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Latest B run skipped P and L because B found a true live token or stock shortage. That is a stock decision, not a safe code repair.",
  "safe_repair_boundary": "Decision proof only; no B run, D001 run, token correction, stock correction, Sheet write, local DB alignment, output deletion, price change, queue edit, or downstream masking without Luke approval.",
  "seen_count": "180",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\pnl_daily.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\B\\2026-06-04\\B_20260604T133454Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\token_shortages_by_sku.csv",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_pnl_daily needs Luke decision",
  "updated_utc": "2026-06-04T13:55:10Z",
  "work_item_id": "MOT_B_B_PNL_DAILY"
}
```
