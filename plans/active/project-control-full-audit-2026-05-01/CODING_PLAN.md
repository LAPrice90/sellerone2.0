# Coding Plan - Project Control Full Audit

## Current Phase

- Status: documentation and proof finalization
- Started: 2026-05-01
- Scope: build/update the project control audit layer and create read-only proof exports from current runtime artifacts.

## Allowed Files For This Phase

- `project_control/ARCHITECTURE.md`
- `project_control/CURRENT_STATE.md`
- `project_control/TASK_QUEUE.md`
- `project_control/WORK_LOG.md`
- `project_control/TEST_CHECKLIST.md`
- `project_control/GOVERNANCE_AUDIT.md`
- `project_control/OUTPUT_SCHEMA_CHECKS.md`
- `out/scanner_latest.csv`
- `out/db_snapshot.csv`
- `out/link_check.csv`
- `out/pricing_output.csv`
- existing proof outputs touched by safe local proof runs:
  - `out/sku_roi_snapshot.csv`
  - `out/systems/O/live/product_db_operator_view.csv`

## Execution Rules

- Do not start overlapping A, B, H, or F owner loops.
- Do not run A015 directly.
- Do not write Google Sheets.
- Do not change Product DB or local DB to force a match.
- Proof exports must preserve source behavior and expose schema issues.

## Proof Already Collected

- E002 local ROI script passed in CSV-only mode and wrote `out/sku_roi_snapshot.csv` with 58 rows.
- O030 direct script path failed due package import path, then module execution passed and wrote `out/systems/O/live/product_db_operator_view.csv` with 608 rows.
- Proof exports created:
  - `out/scanner_latest.csv` - 51 rows
  - `out/db_snapshot.csv` - 608 rows
  - `out/link_check.csv` - 50 rows
  - `out/pricing_output.csv` - 89 rows
- Focused tests passed: 28 passed.

## Live Monitoring Target

- No passive monitoring window is required after this audit because no runtime owner code was changed.
- If runtime confirmation is needed later, use existing owner artifacts:
  - F: `out/systems/F/price_list_manager/live/live_cycle_status.csv`
  - B: `out/systems/B/live/B_cycle.lock`
  - H: `out/systems/H/live/H_cycle_last_terminal_info.txt`
  - E: `out/systems/E/live/e_run_log.jsonl`

## Success Threshold

- Project control files created or updated with evidence-backed status.
- Four requested visibility CSVs exist in `out/`.
- At least three systems have real proof artifacts and row counts.
- Known schema and health gaps are recorded instead of hidden.

## Timeout Rule

- If a required proof path would need an overlapping owner run or a Google Sheets write, mark it `NOT VERIFIED` and record the blocker.
