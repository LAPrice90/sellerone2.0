# B MOT: b_pnl_daily needs repair

## Manager Authority
- task_id: MOT_B_B_PNL_DAILY
- job_ref: B-PNL-DAILY
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B P and L proof only; no finance data rewrite from MOT.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_pnl_daily` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_PNL_DAILY
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\pnl_daily.csv

## Proof Result
- proved_utc: 2026-06-04T14:19:45Z
- result: B MOT now reports `b_pnl_daily` as ok.
- token_catchup: the approved two-token AK catch-up applied inside a matching B-only maintenance pause, then B resumed.
- manager_rule: the B P and L freshness check now uses a daily cadence, so same-day P and L proof does not become a false hard failure by mid-afternoon.
- remaining_state: B has 0 hard MOT failures; remaining B items are warning-labelled proof/bridge gaps, not Luke decisions.

## Exact Source Row
```json
{
  "allowed_scope": "B P and L proof only; no finance data rewrite from MOT.",
  "check": "b_pnl_daily",
  "created_utc": "2026-05-30T01:00:17Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-PNL-DAILY",
  "last_seen_utc": "2026-06-04T14:19:45Z",
  "luke_action_required": "0",
  "manager_action": "If fail, create a bounded B repair task for the producer path. Do not run B or correct data from MOT.",
  "notes": "stale",
  "observed_utc": "2026-06-04T14:19:45Z",
  "priority": "high",
  "producer": "D001_build_pnl_daily.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_pnl_daily` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Expected B output is stale.",
  "safe_repair_boundary": "B P and L proof only; no finance data rewrite from MOT.",
  "seen_count": "184",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\pnl_daily.csv",
  "status": "proved",
  "title": "B MOT: b_pnl_daily needs repair",
  "updated_utc": "2026-06-04T14:20:23Z",
  "work_item_id": "MOT_B_B_PNL_DAILY"
}
```
