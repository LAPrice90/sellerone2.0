# F Repair Package - Login Controller Rewrite V1 - 2026-06-06

## Manager Authority
- task_id: MGR_F_LOGIN_CONTROLLER_REWRITE_V1
- job_ref: F-LOGIN-CONTROLLER-REWRITE
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `scripts/flows/F/login_controller.py` - `scripts/flows/F/seller_central_login_recovery.py` - `scripts/flows/F/bbp_login_recovery.py` - `scripts/flows/F/_scanner_state.py` - `scripts/flows/F/F061_run_legacy_first_checks_local.py` - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py` - narrow FPM130 login coordination in `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` - focused F login/scanner tests under `tests/` - read-only manager/MOT proof wording if needed
- forbidden_actions: - Do not run F061 live during code repair. - Do not edit F061 queue state. - Do not delete or rewrite scanner outputs. - Do not switch suppliers. - Do not change prices. - Do not write Google Sheets. - Do not align local DB facts. - Do not open a separate Chrome login window as the normal fix. - Do not make the UI login button own scanner login. - Do not restart FPM/F061 without a separate approved proof window. - Do not mark login proved unless Dashboard Yes/No is visible afterward and row-clearance proof exists.
- proof_required: - Unit tests prove attempted credentials are not login proof. - Unit tests prove Dashboard Yes/No `YES`, `NO`, or `LIKELY` is the Seller Central proof condition. - Unit tests prove missing code parks cleanly without looping. - Unit tests prove manual challenge becomes manual fallback only. - Regression tests prove auto-capable login evidence does not create the old visible/manual loop. - Retest the manager layer with `python -m sellerone_manager.app --hourly-mot --mot-flow F`. - Live proof can happen only after code tests pass and the current F pause is cleared through the controlled F-only path.
- retest_command: python -m pytest tests/test_f_login_controller.py tests/test_fpm130_live_cycle.py tests/test_f_legacy_webscrape_money_input.py -q; python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: - Use git diff for code rollback. - Remove or ignore the new redacted controller proof files if they were written only by tests. - Do not edit live queues or scanner outputs during rollback. - Rerun the read-only F MOT after rollback.
- stop_condition: Stop immediately if the repair needs queue edits, output deletion, supplier switching, price changes, Sheet writes, local DB alignment, a separate Chrome login window, or a live F061 run before code proof. Stop successfully when one scanner-owned login controller owns the BBP and Seller Central attempt trail, tests pass, and F MOT can show the login-controller state without hiding the paused live scanner truth.

## Source
- source_type: luke_approved_plan
- source_id: F_LOGIN_CONTROLLER_REWRITE_V1_20260606
- source_path: sellerone_manager/tasks/approved/MGR_F_LOGIN_CONTROLLER_REWRITE_V1.md

## Manager Handoff - 2026-06-06 17:50 UK
- F owns this job. The main manager only intervened because the live scanner was looping on weak login evidence.
- Focused login tests now pass: `python -m pytest tests/test_f_login_controller.py tests/test_f_legacy_webscrape_money_input.py -q` returned 40 passed.
- Live scanner proof moved forward:
  - Seller Central credentials were submitted in the scanner-owned browser.
  - Seller Central verification was detected.
  - The latest redacted page pull says: `Two-Step Verification Enter the code`.
  - Latest blocker is `no_fresh_code`, not BBP login and not generic page-detection failure.
- F next work:
  - prove whether Amazon is sending no code, the monitored Gmail label/filter is missing it, or the code is being marked stale/used incorrectly.
  - improve page-pull proof so hidden-browser screenshots are captured when possible.
  - keep Dashboard Yes/No as the only success proof.
- F must not ask Luke unless a fresh code must be forwarded, a real manual Amazon challenge appears, or a protected boundary is reached.

## Weekend Hometime Handoff - 2026-06-06
- Weekend plan: `sellerone_manager/HOMETIME_PLAN_20260606_WEEKEND.md`.
- F is the first priority for Saturday night and Sunday because Monday ordering work needs the scanner to recover from Seller Central login without Luke managing it.
- Current live proof:
  - Scanner-owned browser reached Seller Central Two-Step Verification.
  - Latest page pull says `Two-Step Verification Enter the code`.
  - Latest blocker is `no_fresh_code`.
  - Dashboard Yes/No is not proved yet for the current challenge.
- F child monitoring cadence:
  - every 10 minutes while Seller Central login is unresolved.
  - drop to every 30 minutes after Dashboard Yes/No proof and scanner progress.
- Success means Dashboard Yes/No becomes `YES`, `NO`, or `LIKELY` and the scanner continues or the remaining affected rows have exact blocker reasons.
- Credentials submitted alone is not proof.
- If the same blocker repeats twice with no new evidence, F must change tactic inside this packet or park with an exact blocker.
- Do not ask Luke unless Amazon presents a real human code/passkey/captcha/manual challenge that F cannot safely complete.

## Exact Source Row
```json
{
  "source_id": "F_LOGIN_CONTROLLER_REWRITE_V1_20260606",
  "source_path": "sellerone_manager/tasks/approved/MGR_F_LOGIN_CONTROLLER_REWRITE_V1.md"
}
```
