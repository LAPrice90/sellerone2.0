# F MOT: f_email_price_list_source_proof needs repair

## Manager Authority
- task_id: MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF
- job_ref: F-EMAIL-SOURCE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Email price-list proof only; metadata/read-status checks only; no Gmail fetch, no attachment download, no Gmail deletion, no local file deletion, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_email_price_list_source_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\test_mode\source_acquisition_status.csv

## Exact Source Row
```json
{
  "allowed_scope": "Email price-list proof only; metadata/read-status checks only; no Gmail fetch, no attachment download, no Gmail deletion, no local file deletion, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.",
  "check": "f_email_price_list_source_proof",
  "created_utc": "2026-06-02T10:30:40Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-EMAIL-SOURCE",
  "last_seen_utc": "2026-06-04T13:02:51Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded FPM016 manager-proof task. Do not download attachments, delete Gmail, run F061, or edit queues.",
  "notes": "fail=1",
  "observed_utc": "2026-06-04T13:02:51Z",
  "priority": "high",
  "producer": "FPM016_fetch_gmail_email_sources.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_email_price_list_source_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "FPM016 has not left enough outside proof that the active Gmail label and attachment are visible and imported.",
  "safe_repair_boundary": "Email price-list proof only; metadata/read-status checks only; no Gmail fetch, no attachment download, no Gmail deletion, no local file deletion, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.",
  "seen_count": "245",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\test_mode\\source_acquisition_status.csv",
  "status": "new",
  "title": "F MOT: f_email_price_list_source_proof needs repair",
  "updated_utc": "2026-06-04T13:02:51Z",
  "work_item_id": "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"
}
```
