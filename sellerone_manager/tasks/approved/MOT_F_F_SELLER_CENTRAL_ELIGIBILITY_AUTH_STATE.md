# F MOT: f_seller_central_eligibility_auth_state needs repair

## Manager Authority
- task_id: MOT_F_F_SELLER_CENTRAL_ELIGIBILITY_AUTH_STATE
- job_ref: F-SELLER-CENTRAL-ELIGIBILITY
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Seller Central eligibility proof only; no F061 run without approved proof window, no separate Chrome login, no queue edit, no price change, no Sheets, no local DB alignment, no output deletion, and no worker restart.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_seller_central_eligibility_auth_state` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_SELLER_CENTRAL_ELIGIBILITY_AUTH_STATE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\seller_central_login_recovery_proof.csv

## Exact Source Row
```json
{
  "allowed_scope": "Seller Central eligibility proof only; no F061 run without approved proof window, no separate Chrome login, no queue edit, no price change, no Sheets, no local DB alignment, no output deletion, and no worker restart.",
  "check": "f_seller_central_eligibility_auth_state",
  "created_utc": "2026-06-01T15:00:17Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-SELLER-CENTRAL-ELIGIBILITY",
  "last_seen_utc": "2026-06-08T09:52:53Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded worker repair packet; do not edit queues or rerun F061 outside approval.",
  "notes": "email_continue_not_advanced",
  "observed_utc": "2026-06-08T09:52:53Z",
  "priority": "high",
  "producer": "seller_central_login_recovery.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_seller_central_eligibility_auth_state` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "Seller Central eligibility login proof failed or timed out.",
  "safe_repair_boundary": "Seller Central eligibility proof only; no F061 run without approved proof window, no separate Chrome login, no queue edit, no price change, no Sheets, no local DB alignment, no output deletion, and no worker restart.",
  "seen_count": "277",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\seller_central_login_recovery_proof.csv",
  "status": "new",
  "title": "F MOT: f_seller_central_eligibility_auth_state needs repair",
  "updated_utc": "2026-06-08T09:52:53Z",
  "work_item_id": "MOT_F_F_SELLER_CENTRAL_ELIGIBILITY_AUTH_STATE"
}
```
