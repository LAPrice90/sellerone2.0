# SellerOne Endgame Result Check Register

Created: 2026-05-26
Purpose: track results that cannot be proven immediately.

## Simple Rule

Some coding jobs can be finished today, but the result only proves itself later.

Examples:

- tomorrow morning's cycle
- next H repricer run
- next F scanner safe boundary
- next morning MOT
- after a user/admin action

When that happens, do not leave the follow-up only in chat.

The goal runner must record the delayed check here and in the spreadsheet `Result Checks` tab.

If the check is operationally due on a real date/time, also add it to `project_control/DUE_CHECK_REGISTER.csv`.

## Status Values

- `Not scheduled`
- `Waiting for fix`
- `Waiting for proof window`
- `Waiting for user decision`
- `Only if needed`
- `Due now`
- `Done`
- `Failed`

## Current Result Checks

| Result check ID | Linked goal | Trigger or due time | Artifact to inspect | Success condition | If it fails | Status |
|---|---|---|---|---|---|---|
| RC-A-001 | A-001 | Only if A-001 decides a source fix is required; then next approved A-owned proof | `out/cycle_alerts/checklist_A.csv` and `out/stock_receipt_duplicate_batches.csv` | Warning clears or is recorded as an accepted non-blocking exception | Keep warning visible and inspect source receipt rows | Only if needed |
| RC-F-001 | F-001 | After storage drift repair is applied and the next FPM130 status refresh completes | `out/systems/F/price_list_manager/live/live_cycle_status.csv` | state is no longer `blocked_storage_drift` and no newer scanner evidence is lost | Stop scanner work and inspect `storage_drift_report.csv` again | Waiting for fix |
| RC-F-009 | F-009 | After Luke chooses an SMS/2FA path and a small pilot is approved | pilot artifact named by `GOAL_F-009_plan_seller_central_sms_2fa_path.md` | pilot proves OTP path works without repo-stored secrets, OTP logging, or loss of iPhone/manual fallback | park automated SMS and continue script-owned visible Login Mode | Waiting for user decision |
| RC-G-002 | G-002 | After storage rule or cleanup implementation plus next storage health output | `out/housekeeping/storage_health.latest.csv` | `unclassified_scan_items` is PASS or remaining families are explicitly allowed | Do not delete live data; classify remaining families first | Waiting for fix |
| RC-H-002 | H-002 | After next controlled H proof or next scheduled H owner run | `out/systems/H/live/H_cycle_last_terminal_info.txt` and `out/systems/H/live/H_cycle_last_publish_info.txt` | Fresh terminal finalized/succeeded and publish status is ok or an exact parked reason exists | Classify as H blocker before O market proof continues | Waiting for proof window |
| RC-H-003 | H-003 | After any approved H isolation pause and resume | H isolation status plus H live owner markers | H resumed correctly after O market scan and ownership is restored | Do not run more O/H market work until ownership is restored | Waiting for user decision |
| RC-O-003 | O-003 | After Luke approves elevated H isolation pause plus O candidate-only market scan, or another safe H proof window | `out/systems/O/history/` and `out/systems/O/live/restock_profit_checks_live.csv` | 59 candidates either receive native market proof or remain held with clear missing-data reasons; H ownership is restored after the scan | Keep O buy rows blocked and inspect H/O market ownership first; do not run the market scan while an H lock has a live heartbeat | Waiting for user decision |

## New Result Check Template

Copy this block when a goal needs delayed proof.

```text
Result check ID:
Linked goal:
Why it needs time:
Trigger or due time:
Artifact to inspect:
Success condition:
If it fails:
Owner:
Status:
Last checked:
Result notes:
Also added to project_control/DUE_CHECK_REGISTER.csv: yes/no/not needed
```
