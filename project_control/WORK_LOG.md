# Project Control Work Log

This log is for the 2026-05-01 project control audit. It is not the canonical repo memory for normal work.

## Backfilled Evidence From Current Artifacts

| UTC time | Action / evidence | Result |
|---|---|---|
| 2026-05-01T05:06:31Z | E cycle latest success in `out/systems/E/live/e_run_log.jsonl` | run `20260501T050606331514Z`, status `success`, output asof `2026-05-01` |
| 2026-05-01T05:10:08Z | Latest aggregate health snapshot in `out/system_health_checklist.csv` | 197 rows; 182 ok, 9 warn, 6 fail |
| 2026-05-01T14:17:00Z | F scanner latest first-check output | `out/systems/F/live/feeder_legacy_first_checks_live.csv`, 51 rows |
| 2026-05-01T14:17:38Z | F price-list manager live status | `state=running`, `pending_rows=18168`, `active_supplier_id=entertainment_trading` |
| 2026-05-01T14:18:23Z | H runtime floor snapshot | `out/phase1_runtime_floor_snapshot_latest.csv`, 89 rows |
| 2026-05-01T14:20:10Z | H publish marker | `out/systems/H/live/H_cycle_last_publish_info.txt`, rows 49, status ok |
| 2026-05-01T14:20:11Z | H terminal marker | `out/systems/H/live/H_cycle_last_terminal_info.txt`, state finalized, publish_status ok |

## Audit Actions Performed

| UTC time | Action | Result |
|---|---|---|
| 2026-05-01T14:21:01Z | Ran `python scripts/flows/E/E002_build_roi_snapshot.py` with `SELLERONE_STORAGE_MODE=csv` | Passed; wrote `out/sku_roi_snapshot.csv` with 58 rows |
| 2026-05-01T14:21:06Z | Ran `python -m scripts.flows.O.O030_build_product_db_operator_view` | Passed; wrote `out/systems/O/live/product_db_operator_view.csv` with 608 rows |
| 2026-05-01T14:21:46Z | Created proof exports from current artifacts | `out/scanner_latest.csv` 51 rows; `out/db_snapshot.csv` 608 rows; `out/link_check.csv` 50 rows; `out/pricing_output.csv` 89 rows |
| 2026-05-01T14:22Z | Ran focused pytest profile | Passed; 28 tests passed |
| 2026-05-01T14:22Z | Generated source inventory | `project_control/SCRIPT_INVENTORY.csv` with 675 rows |

## Errors Captured

- Direct execution of `scripts/flows/O/O030_build_product_db_operator_view.py` failed with `ModuleNotFoundError: No module named 'scripts.flows'`.
- Rerunning O030 as a module from repo root succeeded.
- Pytest returned success, but Windows raised an ignored temp-folder cleanup `PermissionError` after completion.

## Ongoing Log

- 2026-05-01T14:22Z - Project control audit docs updated from actual files, outputs, and logs.
