# B MOT: b_marketplace_shared_cursor_risk needs repair

## Manager Authority
- task_id: MOT_B_B_MARKETPLACE_SHARED_CURSOR_RISK
- job_ref: B-MARKETPLACE-SHARED-CURSOR
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B marketplace cursor-risk proof only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_shared_cursor_risk` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_MARKETPLACE_SHARED_CURSOR_RISK
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_marketplace_coverage\b_marketplace_coverage_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B marketplace cursor-risk proof only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "check": "b_marketplace_shared_cursor_risk",
  "created_utc": "2026-05-27T11:20:00Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T13:44:20Z",
  "luke_action_required": "0",
  "manager_action": "Design per-marketplace coverage proof before any recovery. Do not edit markers from MOT.",
  "notes": "shared_cursor_risk_rows=1",
  "observed_utc": "2026-05-27T13:44:20Z",
  "priority": "high",
  "producer": "sellerone_manager.b_marketplace_coverage",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_marketplace_shared_cursor_risk` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "The shared B order cursor may have advanced past missing non-UK marketplace activity.",
  "safe_repair_boundary": "B marketplace cursor-risk proof only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
  "seen_count": "27",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_marketplace_coverage\\b_marketplace_coverage_summary.csv",
  "status": "new",
  "title": "B MOT: b_marketplace_shared_cursor_risk needs repair",
  "updated_utc": "2026-05-27T13:44:20Z",
  "work_item_id": "MOT_B_B_MARKETPLACE_SHARED_CURSOR_RISK"
}
```
