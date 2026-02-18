# E Cycle Runbook

Status: Active
Last updated: 2026-02-07

## Purpose

Run E as a compute-only cycle on top of collected datasets, with cadence enforcement and health visibility.

## Inputs (read-only)

- `out/order_master.csv`
- `out/inventory_summaries.csv`
- `out/fx_rates_daily.csv`
- API-owner history datasets for freshness checks:
  - `out/listing_offer_history.csv`
  - `out/inventory_history.csv`
  - `out/inbound_history.csv`
  - `out/refund_adjustment_history.csv`

## Outputs

- `out/sku_sales_velocity.csv`
- `out/sku_roi_snapshot.csv`
- `out/sku_roi_snapshot_uk.csv`
- `out/sku_roi_snapshot_non_uk.csv`
- `out/sku_roi_snapshot_by_country.csv`
- `out/sku_restock_signals.csv`
- `out/sku_performance_summary.csv`
- `out/e_study_report.csv`
- `out/e_run_log.jsonl`
- `out/e_decision_log.csv`

## Cadence rules

- Default cadence is 24 hours between successful E runs.
- Controlled by:
  - `E_ENFORCE_CADENCE` (default `1`)
  - `E_CADENCE_HOURS` (default `24`)
- If run too early, `scripts/run_E_cycle.py` writes a log line with `status=skipped_cadence` and exits without running E tasks.

## E split health gate

- `E_SPLIT_HEALTH_MODE=legacy|shadow|split` (rollout default `shadow`)
- `E_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_E_split.csv`
- `E_HEALTH_FAIL_CLOSED=1` (default)

Mode behavior:
- `legacy`: no E-scoped health gate; keep current behavior.
- `shadow`: run `A015 --profile e` before publish as candidate decision only; do not block publish.
- `split`: run `A015 --profile e` before `E010_publish_e_outputs.py`; if E FAIL (or unreadable checklist when fail-closed), skip publish and mark run `status=gated_fail`.

Shared rollout tracker files (A/B/E):
- `out/cycle_alerts/flow_selftest_compare.csv`
- `out/cycle_alerts/flow_selftest_state.json`

## Standard command

```powershell
python scripts/run_E_cycle.py
```

## Validation command

```powershell
python scripts/A015_build_system_health_check.py
```

Required Phase 7 checks:

- `h_e_cadence_enforced=ok`
- `h_e_inputs_fresh=ok`
- `h_e_outputs_latest_asof=ok`

## Recovery steps

1. If `h_e_cadence_enforced` is not `ok`, inspect latest rows in `out/e_run_log.jsonl`.
2. If `h_e_inputs_fresh` is not `ok`, run API collection first, then rerun E.
3. If `h_e_outputs_latest_asof` is not `ok`, rerun E after input freshness is restored.
4. Re-run A015 and confirm all three E checks return `ok`.
