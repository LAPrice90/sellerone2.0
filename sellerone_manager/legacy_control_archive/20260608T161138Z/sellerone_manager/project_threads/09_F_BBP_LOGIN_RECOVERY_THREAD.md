# F BBP Login Recovery Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are the F price-list scanner worker under the SellerOne Manager.

## Role

Your job is to implement BBP login recovery for the existing F061 scanner path, safely and narrowly.

This is not permission to run F061, restart it, edit the queue, or open a separate login browser.

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `plans/active/sellerone-manager-control-plane-v1/F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601.md`
- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/approved_task_packets.csv`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`

## Plain-English Job

F061 can get stuck if BBP logs out.

Build a safe login recovery path:

```text
scanner-owned F061 browser sees BBP login page
-> reads local credentials from secrets
-> enters email and password
-> clicks login
-> returns to normal scanner evidence
-> continues without queue edits
```

## Credentials File

Luke will fill this file locally:

```text
secrets/price_list_manager/bbp_login.env
```

Expected keys:

```text
BBP_LOGIN_EMAIL=
BBP_LOGIN_PASSWORD=
BBP_LOGIN_HEADING_XPATH=/html/body/div/div/div[1]/div/div[1]/h1
BBP_LOGIN_EMAIL_XPATH=//*[@id="loginEmail"]
BBP_LOGIN_PASSWORD_XPATH=//*[@id="loginPassword"]
BBP_LOGIN_BUTTON_XPATH=//*[@id="loginBtn"]
BBP_AUTO_LOGIN_ENABLED=0
```

Never print the real email or password.

## Allowed Work

- inspect F061 and legacy scanner browser/login code
- add a secrets loader for the BBP env file
- add login-page detection using the supplied heading proof
- add login field fill/click logic inside the scanner-owned browser only
- add safe logging that says login recovery attempted/succeeded/failed without secrets
- add tests using fake credentials/selectors only
- update manager/MOT proof mapping if needed

## Forbidden Work

- no F061 live run unless a separate approved proof window exists
- no scanner restart
- no queue edits
- no handoff approval
- no separate Chrome login workaround
- no forced Chrome profile reset
- no real password in code, tests, output, or chat
- no prices
- no Google Sheets
- no output deletion
- no widening into other cycles

## Proof

Use code and unit-style proof first.

Required proof:

- missing secrets file does not crash the scanner
- missing email/password produces a safe blocked-login state
- `BBP_AUTO_LOGIN_ENABLED=0` prevents automatic login
- supplied login selectors are used only when the login heading is detected
- no secret values appear in logs or outputs

Live proof is parked until separately approved.

## Final Reply Shape

```text
Decision needed: yes/no

What F now proves:
<plain English>

What changed:
<short list>

What remains blocked or parked:
<short list>

Proof:
<commands and result>

Files changed:
<paths>

Recommended next move:
continue with <specific next F login recovery task>
```

