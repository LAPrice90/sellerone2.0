# CODING PLAN

## Ticket

E sales-truth closeout after recovery v1.

## Execution Rule

This plan is phase -> test -> proof only.

No phase is complete until:

1. scoped code changes are finished
2. scoped tests pass
3. proof notes are written

## Phase 1 - Repair the operator report

Status: Complete

Goal:

Make `e_study_report.csv` reflect the corrected truth layer and expose the split between truth units and velocity units.

Allowed files:

- `scripts/flows/E/E005_build_study_report.py`
- `tests/test_e005_build_study_report.py`
- `plans/archive/2026/e-sales-truth-closeout-v2/REVIEW_FINDINGS.md`

Required output changes:

1. rebuild from current `sku_performance_summary.csv`
2. keep existing operator-friendly columns
3. add explicit truth fields:
   - `units_sold_truth_30d`
   - `units_sold_velocity_30d`
   - `units_sold_source`
4. add latest daily truth fields:
   - `latest_daily_truth_date`
   - `latest_daily_truth_state`
   - `latest_daily_truth_units`
   - `latest_daily_truth_profit_gbp`

Scoped tests:

1. fixture where truth units and velocity units differ
2. fixture where daily truth adds a provisional same-day row
3. assert study report matches performance summary truth fields exactly
4. assert study report surfaces latest daily truth state

Phase proof:

1. rerun `E005`
2. prove sample `0G-JB6S-PN34` now matches performance summary economics

Pass condition:

The operator report is fresh and truth-aligned.

## Phase 2 - Extend the publish contract

Status: Complete

Goal:

Make the publish path ready to carry the corrected operator/truth outputs.

Allowed files:

- `scripts/flows/E/E010_publish_e_outputs.py`
- `tests/test_e010_publish_e_outputs.py`

Required publish additions:

1. `E_Study_Report`
2. `E_Sales_Truth_Reconciliation`
3. `E_Daily_Sales_Truth`

Important rule:

Do not write to Sheets during proof. Only test the code path and tab contract.

Scoped tests:

1. assert the new tabs are present in the publish list
2. assert missing files are handled cleanly

Pass condition:

The publish code knows about every operator-facing truth artifact that now matters.

## Phase 3 - Add stale-output and alignment guards

Status: Complete

Goal:

Make it impossible for a stale operator report to pass unnoticed again.

Allowed files:

- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_a015_health_check_runtime.py`

Required checks:

1. `e_study_report_fresh_vs_summary`
2. `e_study_report_truth_alignment`

Suggested check logic:

1. fail if `e_study_report.csv` is older than `sku_performance_summary.csv`
2. fail if study report revenue/profit/units truth fields differ from performance summary for any truth-backed row

Scoped tests:

1. stale file-time case
2. aligned case
3. mismatched economics case

Pass condition:

The exact miss found in review would now trigger a visible FAIL.

## Phase 4 - Real E cycle proof

Status: Complete

Goal:

Prove the closeout using the real E cycle order, not a hand-picked subset.

Allowed files:

- `plans/archive/2026/e-sales-truth-closeout-v2/REVIEW_FINDINGS.md`
- `plans/archive/2026/e-sales-truth-closeout-v2/FINAL_PASS_CRITERIA.md`

Required run:

Run `run_E_cycle.py` in isolated mode with:

- publish disabled
- cadence bypass enabled if needed
- no sheet writes

Required proof checks:

1. `e_study_report.csv` mtime is at or after the upstream summary rebuild for the same proof run
2. study-report sample rows match performance-summary sample rows
3. daily-truth output still contains explicit provisional rows
4. reconciliation mismatch rows remain `0`

Sample proof rows:

1. `0G-JB6S-PN34`
2. `A2-T2AC-TW3L`

Pass condition:

The real E flow produces a fully aligned operator/truth stack.

## Phase 5 - Live verification closeout

Status: Complete for the E flow

Goal:

Move from isolated proof to live proof.

Allowed files:

- `plans/archive/2026/e-sales-truth-closeout-v2/FINAL_PASS_CRITERIA.md`

Required status language:

- `code fix applied`
- `isolated verification passed`
- `live loop verification pending next cycle check`
- later: `live loop verification confirmed`

Pass condition:

The next scheduled health snapshot after the implementation time confirms the E flow state with no contradictory evidence.

## Execution Proof

1. Scoped tests:
   - E closeout tests: `19 passed`
   - targeted A015 helpers: `6 passed`
2. Publish dry run:
   - `E010_publish_e_outputs.py` executed with `E_WRITE_SHEETS=0`
   - result: clean skip, no runtime error
3. Real E cycle proof:
   - `run_E_cycle.py` completed successfully after the code changes
   - task chain included `E005`, `E006`, `E007`, and `A015 profile=e`
   - latest run id: `20260417T220919386933Z`
4. Fresh E health:
   - `checklist_E_split.csv` mtime: `2026-04-17T22:09:38Z`
   - fail count: `0`
   - warn count: `0`
5. Operator report freshness:
   - `sku_performance_summary.csv` mtime: `2026-04-17T22:09:24Z`
   - `e_study_report.csv` mtime: `2026-04-17T22:09:25Z`
6. Sample proof:
   - `0G-JB6S-PN34` study report now matches performance summary economics
   - `A2-T2AC-TW3L` study report surfaces latest provisional daily truth: `2026-04-17`, `6` units, `4.98` profit
