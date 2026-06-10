# F Repair Package - BBP Login Recovery Setup - 2026-06-01

## Plain-English Summary

The F price-list scanner can get stuck when BBP logs out.

The repair should let the normal script-owned F061 browser recognise the BBP login page, enter the saved email and password from the local secrets file, click login, and then continue scanning.

This is a setup package only. It does not run F061, edit the scanner queue, or prove the live login.

## Current Input From Luke

Login page proof:

```text
/html/body/div/div/div[1]/div/div[1]/h1 = Login
```

Selectors:

```text
//*[@id="loginEmail"]
//*[@id="loginPassword"]
//*[@id="loginBtn"]
```

Local credentials file created:

```text
secrets/price_list_manager/bbp_login.env
```

Luke must enter:

```text
BBP_LOGIN_EMAIL=
BBP_LOGIN_PASSWORD=
```

## Required Behaviour

When F061 is already running its normal script-owned browser:

1. Detect the BBP login page.
2. Read BBP credentials from the local secrets file.
3. Fill the email field.
4. Fill the password field.
5. Click the login button.
6. Wait for the scanner's normal BBP page to return.
7. Continue the current row without queue edits.
8. Write proof that login recovery was attempted and whether it succeeded.

## Important Boundary

Use the normal F061 browser path only.

Do not open a separate login Chrome window as the fix. The login recovery must happen inside the scanner-owned browser/session so BBP plugin/profile state stays consistent.

## Allowed Files For Future Worker

The future worker may inspect and edit only the narrow scanner login handling path after it identifies the exact files from evidence. Likely candidates include:

- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- files under `scripts/flows/F/legacy_scanner_2_1/` that own BBP/browser login detection
- focused F scanner/login tests under `tests/`
- manager/MOT proof mapping under `sellerone_manager/` if needed to report login-needed/login-recovered state
- this repair package and the active `CODING_PLAN.md` for proof notes

## Forbidden Actions

Do not:

- run F061 during setup
- restart F061
- edit F061 queue state
- approve scanner handoff
- change prices
- write Google Sheets
- delete outputs
- force-stop specialist Chrome
- use a separate standalone login browser as the fix
- change the BBP Chrome profile away from the scanner-owned profile
- widen into A, B, E, H, or O

## Proof Required For Future Worker

Code proof:

- secrets loader handles missing file, missing email, and missing password safely
- login detection only triggers on the supplied login page proof
- login recovery is disabled unless `BBP_AUTO_LOGIN_ENABLED=1`
- tests prove the selector flow without using real credentials

Live proof later, only if separately approved:

- F061 opens its normal script-owned browser
- BBP login page is detected
- credentials are entered from local secrets
- scanner returns to normal BBP evidence page
- current row continues without queue edits
- manager/MOT sees login recovery proof

## Rollback Path

- Disable `BBP_AUTO_LOGIN_ENABLED=0` in `secrets/price_list_manager/bbp_login.env`.
- Revert only the future worker's touched F login-handling code.
- Do not edit queue files or scanner output files to hide a failed login.

## Stop Condition

Stop immediately if the fix requires:

- queue edits
- scanner restart
- separate login browser
- Chrome profile reset
- output deletion
- real password in code
- price changes
- Google Sheets
- business judgement

## Manager Status

This job is ready for a future F worker thread to implement safely.

Luke input still needed before live login can work:

- enter `BBP_LOGIN_EMAIL`
- enter `BBP_LOGIN_PASSWORD`
- set `BBP_AUTO_LOGIN_ENABLED=1` only when ready for the worker-tested recovery path

