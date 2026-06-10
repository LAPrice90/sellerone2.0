# B MOT: b_marketplace_coverage_report needs repair

## Manager Authority
- task_id: MOT_B_B_MARKETPLACE_COVERAGE_REPORT
- job_ref: B-MARKETPLACE-COVERAGE-REPORT
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B marketplace coverage reporting and proof design only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_coverage_report` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_MARKETPLACE_COVERAGE_REPORT
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_marketplace_coverage\b_marketplace_coverage_by_marketplace.csv

## Exact Source Row
```json
{
  "allowed_scope": "B marketplace coverage reporting and proof design only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or data correction.",
  "check": "b_marketplace_coverage_report",
  "created_utc": "2026-05-27T11:20:00Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-MARKETPLACE-COVERAGE-REPORT",
  "last_seen_utc": "2026-06-04T12:35:04Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B manager task for marketplace coverage proof. Do not run B, backfill, or correct data from MOT.",
  "notes": "participating=17;local_markets=5;sellerboard_markets=4;fail_rows=0;warn_rows=3",
  "observed_utc": "2026-06-04T12:35:04Z",
  "priority": "normal",
  "producer": "sellerone_manager.b_marketplace_coverage",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_coverage_report` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "",
  "safe_repair_boundary": "B marketplace coverage reporting and proof design only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or data correction.",
  "seen_count": "72",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_marketplace_coverage\\b_marketplace_coverage_by_marketplace.csv",
  "status": "new",
  "title": "B MOT: b_marketplace_coverage_report needs repair",
  "updated_utc": "2026-06-04T12:35:04Z",
  "work_item_id": "MOT_B_B_MARKETPLACE_COVERAGE_REPORT"
}
```
