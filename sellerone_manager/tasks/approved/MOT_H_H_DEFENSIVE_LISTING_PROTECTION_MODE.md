# H MOT: h_defensive_listing_protection_mode needs repair

## Manager Authority
- task_id: MOT_H_H_DEFENSIVE_LISTING_PROTECTION_MODE
- job_ref: H-DEFENSIVE-LISTING-PROTECTION
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_defensive_listing_protection_mode` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_DEFENSIVE_LISTING_PROTECTION_MODE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\config\h_defensive_listing_protection.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\h_defensive_listing_action_log.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\h_defensive_listing_campaign_memory.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\h_defensive_listing_daily.csv

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_defensive_listing_protection_mode",
  "created_utc": "2026-06-04T11:36:22Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-DEFENSIVE-LISTING-PROTECTION",
  "last_seen_utc": "2026-06-04T13:40:02Z",
  "luke_action_required": "0",
  "manager_action": "If warn or fail, package a bounded H defensive-listing proof task. Do not change prices or enable live writes from MOT.",
  "notes": "Read-only H MOT cleared h_defensive_listing_protection_mode. Latest B06 proof row is post-fix pressure_then_match normal_h_control with no write: current=6.97, rival=6.98. Old equal-rival applied write remains historical only.",
  "observed_utc": "2026-06-04T13:40:02Z",
  "priority": "high",
  "producer": "phase1_defensive_listing / H MOT",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_defensive_listing_protection_mode` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "A defensive listing proof row applied a write even though the rival was equal to or above us.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "36",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\config\\h_defensive_listing_protection.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\h_defensive_listing_action_log.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\h_defensive_listing_campaign_memory.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\h_defensive_listing_daily.csv",
  "status": "proved",
  "title": "H MOT: h_defensive_listing_protection_mode needs repair",
  "updated_utc": "2026-06-04T13:40:41Z",
  "work_item_id": "MOT_H_H_DEFENSIVE_LISTING_PROTECTION_MODE"
}
```
