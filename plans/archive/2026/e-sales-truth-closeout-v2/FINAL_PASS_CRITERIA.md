# FINAL PASS CRITERIA

This closeout plan is complete only when every line below is true.

## Operator Report Gates

1. `out/e_study_report.csv` is newer than or equal to the upstream summary it depends on for the same proof run
2. `out/e_study_report.csv` truth economics match `out/sku_performance_summary.csv`
3. `out/e_study_report.csv` exposes:
   - `units_sold_truth_30d`
   - `units_sold_velocity_30d`
   - `units_sold_source`
   - latest daily truth fields

## Publish Contract Gates

1. publish code includes `E_Study_Report`
2. publish code includes `E_Sales_Truth_Reconciliation`
3. publish code includes `E_Daily_Sales_Truth`

## Health Guard Gates

1. A015 has a stale-study-report check
2. A015 has a study-report truth-alignment check
3. targeted A015 tests pass for those checks

## Proof Gates

1. full isolated E cycle run completes cleanly with publish disabled
2. reconciliation mismatch rows remain `0`
3. provisional daily rows remain explicit and structurally clean
4. sample SKU `0G-JB6S-PN34` matches between study report and performance summary
5. sample SKU `A2-T2AC-TW3L` shows:
   - finalized `2026-04-16`
   - provisional `2026-04-17`
   - no duplicate-order explanation required on current local data

## Live Verification Gate

The ticket is only fully closed when the next scheduled post-change health window confirms the updated E outputs after implementation time.

## Result

All closeout gates above are now met for the E flow based on the post-change real `run_E_cycle.py` proof and fresh `checklist_E_split.csv`.
