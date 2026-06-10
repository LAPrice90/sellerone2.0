# F Repair Package - Login Attempt Cooldown Switch V1 - 2026-06-08

## Manager Authority
- task_id: MGR_F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_V1
- job_ref: F-LOGIN-COOLDOWN-SWITCH
- flow: F
- task_type: manual_approved_task
- status: proved
- priority: high
- authority: luke_approved_safe_code_repair
- luke_action_required: 0

## Plain-English Goal
F should stop trying phone/SMS Seller Central login repeatedly when Amazon shows a security/cooldown message.

The scanner still needs to keep normal non-login work moving where it safely can. Login attempts should become a controlled mode, not something F keeps hammering whenever a page asks for Seller Central.

## Current Evidence
- Amazon has shown: `For added security, we need to verify your phone number. We are unable to send an SMS to the phone number ending with 598 at this time.`
- Recent proof shows SMS/code/MFA can sometimes work, but F has been oscillating between:
  - email Continue page not advancing
  - OTP/code wait with no fresh code
  - SMS option not available/clickable
  - short-lived Dashboard Yes/No proof
- Current Seller Central auto-login was paused on 2026-06-08 by setting `SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0` with a timestamped backup of the login env file.

## Allowed Work
- Add a safe F login-attempt control switch with at least these states:
  - `normal_scan_only`
  - `login_attempt_mode`
  - `login_cooldown`
  - `manual_challenge`
- Ensure `normal_scan_only` lets F continue safe scanner work where possible without attempting Seller Central phone/SMS login.
- Ensure `login_attempt_mode` is explicit and bounded.
- If Amazon shows the phone/SMS security message or `sms_option_not_clickable`, automatically switch to `login_cooldown` and stop further phone/SMS attempts.
- Add a cooldown timestamp and clear reason label such as `amazon_phone_sms_cooldown`.
- Keep Dashboard Yes/No as the only Seller Central success proof.
- Keep all proof files redacted: no credentials, cookies, tokens, OTPs, or raw secrets.
- Update focused F tests for the switch and cooldown behavior.
- Retest with focused F tests and read-only F MOT.

## Forbidden Work
- Do not bypass Amazon security.
- Do not disable MFA.
- Do not store OTPs, cookies, tokens, credentials, or raw browser secrets.
- Do not open a separate Chrome login workaround.
- Do not run F061 live during code repair.
- Do not restart FPM or F061 without a separate approved proof window.
- Do not edit F061 queue state.
- Do not delete or rewrite scanner outputs.
- Do not switch suppliers.
- Do not change prices.
- Do not write Google Sheets.
- Do not align Product DB or local DB facts.
- Do not widen into A, B, E, H, or O work.

## Acceptance Proof
- Focused tests prove F does not attempt Seller Central phone/SMS login while `normal_scan_only` or `login_cooldown` is active.
- Focused tests prove the Amazon phone/SMS security message switches F into `login_cooldown`.
- Focused tests prove the cooldown reason and until-time are written to redacted proof/state files.
- Focused tests prove `login_attempt_mode` can be intentionally enabled later without exposing secrets.
- Read-only F MOT still reports truthful status and does not hide protected RESCAN or scanner-progress blockers.

## Retest Command
python -m pytest tests/test_f_login_controller.py tests/test_f_legacy_webscrape_money_input.py -q; python -m sellerone_manager.app --hourly-mot --mot-flow F

## Rollback Path
Use git diff for code rollback. Restore the timestamped backup of `secrets/price_list_manager/seller_central_login.env` only if the auto-login flag needs to be returned to its previous value. Do not edit live queues, scanner outputs, cookies, credentials, or OTP files during rollback.

## Stop Condition
Stop immediately if the work requires bypassing Amazon security, changing credentials, editing cookies directly, opening a separate browser workaround, queue edits, output deletion, scanner restart, supplier switch, Sheet write, price change, local DB alignment, or business judgement.

Stop successfully when F has a safe login-attempt mode switch, phone/SMS cooldown detection, redacted proof, focused tests passing, and F MOT retested read-only.

## Source
- source_type: luke_approved_chat_request
- source_id: F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_20260608
- source_path: sellerone_manager/tasks/approved/MGR_F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_V1.md

## Exact Source Row
```json
{
  "task_id": "MGR_F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_V1",
  "job_ref": "F-LOGIN-COOLDOWN-SWITCH",
  "source_id": "F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_20260608",
  "source_path": "sellerone_manager/tasks/approved/MGR_F_LOGIN_ATTEMPT_COOLDOWN_SWITCH_V1.md"
}
```
