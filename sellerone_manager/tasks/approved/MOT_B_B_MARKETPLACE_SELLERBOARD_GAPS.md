# B MOT: b_marketplace_sellerboard_gaps needs repair

## Manager Authority
- task_id: MOT_B_B_MARKETPLACE_SELLERBOARD_GAPS
- job_ref: B-MARKETPLACE-SELLERBOARD-GAPS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B marketplace coverage diagnosis only; no B run, no backfill, no marker edit, no Sheet write, no local DB alignment, no output deletion, and no data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_sellerboard_gaps` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_MARKETPLACE_SELLERBOARD_GAPS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_marketplace_coverage\b_marketplace_coverage_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B marketplace coverage diagnosis only; no B run, no backfill, no marker edit, no Sheet write, no local DB alignment, no output deletion, and no data correction.",
  "check": "b_marketplace_sellerboard_gaps",
  "created_utc": "2026-05-27T11:20:00Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T13:44:20Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B marketplace-coverage task. Do not recover or backfill orders without Luke approval.",
  "notes": "sellerboard_missing_shipped_orders=1;marketplace_fail_rows=1",
  "observed_utc": "2026-05-27T13:44:20Z",
  "priority": "high",
  "producer": "sellerone_manager.b_marketplace_coverage",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_sellerboard_gaps` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Sellerboard has marketplace activity that local B proof does not cover.",
  "safe_repair_boundary": "B marketplace coverage diagnosis only; no B run, no backfill, no marker edit, no Sheet write, no local DB alignment, no output deletion, and no data correction.",
  "seen_count": "27",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_marketplace_coverage\\b_marketplace_coverage_summary.csv",
  "status": "new",
  "title": "B MOT: b_marketplace_sellerboard_gaps needs repair",
  "updated_utc": "2026-05-27T13:44:20Z",
  "work_item_id": "MOT_B_B_MARKETPLACE_SELLERBOARD_GAPS"
}
```
