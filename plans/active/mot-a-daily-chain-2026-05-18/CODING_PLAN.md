# MOT A Daily Chain - 2026-05-18

## Current Phase
- Status: parked pending next proof window.
- Started UTC: 2026-05-18T10:45:00Z.
- Owner: Codex.

## Problem
- Full MOT found A partial on 2026-05-17 and 2026-05-18.
- 2026-05-18 A run `20260518T050129Z` stopped at `A003_run_inventory_to_sheet.py`.
- A003 returned rc 0 but `out/inventory_snapshot_latest.csv` and `out/inventory_history.csv` did not refresh, so the A manifest correctly marked `failed_stale_outputs`.
- E did not run after A on 2026-05-17 or 2026-05-18, so E evidence is stale at `20260516T050451540342Z`.
- Stock receipts also hit a duplicate-batch guardrail, but this is non-fatal and requires a sheet/data decision before changing the intake rows.

## Scope
- Allowed files:
  - `scripts/cycles/run_A_all.py`
  - `tests/test_a_split_health_modes.py`
  - this plan file
- Do not edit Google Sheets.
- Do not align local DB to Sheets.
- Do not run standalone A015 as proof for the A-owned change.

## Implementation Plan
- Add a narrow retry for successful A producer steps whose required outputs remain stale.
- Apply it only to `A003_run_inventory_to_sheet.py` and `A016_refresh_phase1_daily_intel.py`.
- Retry the producer once and require real refreshed output mtimes before continuing.
- Treat Windows `tasklist` access-denied evidence as "process may be alive" so A uses the B maintenance handoff instead of assuming B is stopped.

## Test Plan
- Run focused A runner tests:
  - `python -m pytest tests/test_a_split_health_modes.py -q`
- Compile the A runner:
  - `python -m py_compile scripts/cycles/run_A_all.py`
- Result at 2026-05-18T11:04:00Z: passed, 5 tests. Pytest cache warning only.

## Forced Proof Plan
- Use A-owned proof, not a standalone health script.
- If B is active, use maintenance handoff first.
- Run `run_A_all.bat` from the repo root with sheet-writing safeguards preserved.
- Success condition:
  - latest A manifest final_state is `completed`
  - A recorded all configured steps
  - `out/cycle_alerts/checklist_A_split.csv` is current-cycle with 0 FAIL
  - E follow-on run evidence is current or explicitly recorded if cadence/guard blocks it
  - B maintenance flags are cleared and B ownership is restored or still healthy
- Attempted proof runs:
  - `20260518T110846Z`: B maintenance handoff succeeded and B was restored; A proof stopped because this Codex session could not read protected `secrets/.env`.
  - `20260518T111149Z`: same result after folder and file read permissions were requested; `Test-Path secrets/.env` still returned access denied.
- Current proof status: code fix applied and isolated tests passed; live A proof is not yet proven.

## Monitoring
- Artifact: `out/manifests/A/2026-05-18/*.json`.
- Success threshold: one completed A-owned proof run with current A split health and E follow-on evidence.
- Timeout rule: if B maintenance handoff is not obtained inside the A runner timeout, park as `parked pending next proof window` with the active B lock evidence.
- Durable follow-up: `project_control/DUE_CHECK_REGISTER.csv` row `A_MOT_DAILY_CHAIN_20260518_LIVE_PROOF`.
