# B MOT: b_sellerboard_email_attachment_arrived needs repair

## Manager Authority
- task_id: MOT_B_B_SELLERBOARD_EMAIL_ATTACHMENT_ARRIVED
- job_ref: B-SELLERBOARD-EMAIL-ATTACHMENT
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Sellerboard email intake connection and report only; no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, or queue edit.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_email_attachment_arrived` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_SELLERBOARD_EMAIL_ATTACHMENT_ARRIVED
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\sellerboard_email_intake\b_sellerboard_email_intake_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "Sellerboard email intake connection and report only; no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, or queue edit.",
  "check": "b_sellerboard_email_attachment_arrived",
  "created_utc": "2026-05-27T11:51:12Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T12:03:08Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded B email-intake task to connect or save the Sellerboard attachment. Do not delete email or local files from MOT.",
  "notes": "latest_attachment_present=0",
  "observed_utc": "2026-05-27T12:03:08Z",
  "priority": "high",
  "producer": "sellerone_manager.sellerboard_email_intake",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_email_attachment_arrived` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "No Sellerboard OrderList attachment has been saved into the manager intake area.",
  "safe_repair_boundary": "Sellerboard email intake connection and report only; no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, or queue edit.",
  "seen_count": "3",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\sellerboard_email_intake\\b_sellerboard_email_intake_summary.csv",
  "status": "new",
  "title": "B MOT: b_sellerboard_email_attachment_arrived needs repair",
  "updated_utc": "2026-05-27T12:03:08Z",
  "work_item_id": "MOT_B_B_SELLERBOARD_EMAIL_ATTACHMENT_ARRIVED"
}
```
