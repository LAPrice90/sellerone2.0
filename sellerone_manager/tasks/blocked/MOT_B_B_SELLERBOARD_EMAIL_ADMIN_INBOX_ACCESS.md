# B MOT: b_sellerboard_email_admin_inbox_access needs Luke decision

## Manager Authority
- task_id: MOT_B_B_SELLERBOARD_EMAIL_ADMIN_INBOX_ACCESS
- job_ref: B-SELLERBOARD-EMAIL-ADMIN
- status: blocked_needs_luke
- authority: needs_luke_decision
- luke_action_required: 1

## Boundary
- allowed_scope: Sellerboard email source proof only; Gmail source authorization decision if OAuth is missing; no attachment download, no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, queue edit, or ROI use.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_email_admin_inbox_access` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_SELLERBOARD_EMAIL_ADMIN_INBOX_ACCESS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\sellerboard_email_intake\b_sellerboard_email_intake_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "Sellerboard email source proof only; Gmail source authorization decision if OAuth is missing; no attachment download, no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, queue edit, or ROI use.",
  "check": "b_sellerboard_email_admin_inbox_access",
  "created_utc": "2026-05-27T12:23:28Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "last_seen_utc": "2026-05-27T13:31:40Z",
  "luke_action_required": "1",
  "manager_action": "Luke must connect or re-authorize local Gmail access for admin@drjselect.co.uk before this email intake can be manager-proven.",
  "notes": "method=local_gmail_oauth;expected_mailbox=admin@drjselect.co.uk;local_oauth_present=1;auth_status=oauth_not_valid;source_mailbox_visible=0;source_status=fail",
  "observed_utc": "2026-05-27T13:31:40Z",
  "priority": "high",
  "producer": "sellerone_manager.sellerboard_email_intake",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_sellerboard_email_admin_inbox_access` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Local Gmail OAuth is missing or invalid for the admin Sellerboard inbox.",
  "safe_repair_boundary": "Sellerboard email source proof only; Gmail source authorization decision if OAuth is missing; no attachment download, no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, queue edit, or ROI use.",
  "seen_count": "17",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\sellerboard_email_intake\\b_sellerboard_email_intake_summary.csv",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_sellerboard_email_admin_inbox_access needs Luke decision",
  "updated_utc": "2026-05-27T13:31:40Z",
  "work_item_id": "MOT_B_B_SELLERBOARD_EMAIL_ADMIN_INBOX_ACCESS"
}
```
