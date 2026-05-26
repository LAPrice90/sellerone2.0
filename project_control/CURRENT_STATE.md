# Current State

Snapshot timestamp: 2026-05-01T22:09Z

## Status Legend

- CONFIRMED: verified from a real script run, live owner marker, output file, row count, or log.
- NOT VERIFIED: inspected, but no safe proof run was performed.
- BROKEN: output exists or script is present, but evidence shows a failed check, schema break, duplicate key, stale gate, or execution error.
- UNKNOWN: not enough evidence found.

## System Status

| System | Status | Evidence | Notes |
|---|---|---|---|
| Scanner / F price-list manager | CONFIRMED | `out/systems/F/price_list_manager/live/live_cycle_status.csv` shows `state=running`, `active_supplier_id=entertainment_trading`, `pending_rows=18168`; `out/scanner_latest.csv` has 51 rows | Owner was already active, so no overlapping scanner run was started. |
| Scanner identity quality | CONFIRMED | `python -m scripts.one_off.P012_scanner_identity_check --format json` reported 51 scanner rows, 51 unique `asin + supplier_sku` keys, and 0 exact duplicate keys | Same ASIN `B0DPMGDZLZ` appears with 2 different supplier SKUs and is treated as separate products under the recorded user decision. |
| Database / Product DB SQL authority | CONFIRMED | `out/sql/sellerone_dev.sqlite3:product_db_products` has 659 rows and 659 unique `seller_sku`; P018 reports SQL 659 rows, O view 659 rows, and CSV mirror 608 rows | Legacy `out/product_db_preview.csv` is stale mirror/export evidence, not Product DB authority. P021 marks Phase 2 `complete_locally_pending_explicit_cutover_approvals`. |
| Scanner to DB insert | CONFIRMED | `python -m scripts.one_off.P011_apply_scanner_product_db_inserts --apply --confirm-scanner-product-db-insert --format json` inserted 51 scanner products | SQL table `out/sql/sellerone_dev.sqlite3:product_db_products` has 659 rows, 659 unique `seller_sku`, and 9 rows with duplicate-ASIN reason. No Google Sheets write was performed. |
| Product DB review pack | CONFIRMED | `python -m scripts.one_off.P010_product_db_review_pack --format json` wrote 4 classified duplicate-ASIN review rows and 51 scanner-link review rows | Duplicate ASIN suggestion count is now `different_sku_separate_product_not_sold_together=4`. Scanner review now has 49 `WOULD UPDATE`, 2 `REVIEW`, 0 `BLOCKED`. |
| E ROI analytics | CONFIRMED | `python scripts/flows/E/E002_build_roi_snapshot.py` ran in CSV-only mode and wrote `out/sku_roi_snapshot.csv` with 58 rows | This was a local output proof only, not a Sheet write. |
| H repricing / pricing decisions | CONFIRMED | P013 at `2026-05-01T22:08:58Z` saw terminal run `20260501T215343Z`, terminal state `finalized`, publish `ok`, runtime blank write-status rows `0`, and invalid write-status rows `0` | Stale compact `out/pricing_output.csv` remains an audit-only warning because it is older than the runtime source and missing latest runtime run rows. |
| A cycle | NOT VERIFIED | `run_A_all.bat` and `scripts/cycles/run_A_all.py` inspected; `out/system_health_checklist.csv` exists with 197 rows | No A script or A015 ad-hoc health run was executed because the repo rules forbid Codex-initiated A runs unless explicitly requested. |
| B cycle | BROKEN | `out/systems/B/live/B_cycle.lock` heartbeat present; `out/cycle_alerts/checklist_B.csv` has 30 ok, 1 warn, 1 fail | B owner is running, but `token_shortages_by_sku` is FAIL with value 6. No overlapping B proof run was started. |
| E cycle | CONFIRMED | `out/systems/E/live/e_run_log.jsonl` latest success: run `20260501T050606331514Z`, status `success`, output asof `2026-05-01` | E scoped checklist has 23 ok and 0 fail/warn. |
| H cycle | CONFIRMED | Latest completed terminal evidence in P013/P016 shows run `20260501T215343Z`, state `finalized`, publish `ok`; local staged publish status `ok` | Run `20260501T193132Z` exposed a local staged-publish `PermissionError`; a retry patch was added and isolated tests passed. Later finalized H evidence did not show recurrence, but due register still tracks fresh-owner live-load proof because the observed owner PID was already running before the patch. |
| O Product DB operator view | CONFIRMED | `python -m scripts.flows.O.O030_build_product_db_operator_view` ran and wrote `out/systems/O/live/product_db_operator_view.csv` with 659 rows from SQL authority | O030 now prefers local SQL Product DB when `product_db_products` exists, so stale CSV mirror rewrites do not reduce the O view back to 608 rows. |
| External integrations | NOT VERIFIED | API/Sheet owner scripts inspected; no live external call was forced | Google Sheets changes were avoided. Existing H publish happened under active H owner, not from a new audit run. |

## Health Snapshot Position

- `out/system_health_checklist.csv` mtime: 2026-05-01T05:10:08Z.
- Current aggregate health counts: 182 ok, 9 warn, 6 fail.
- Current H scoped checklist counts from that same health snapshot: 94 ok, 8 warn, 5 fail.
- Newer H runtime evidence from terminal run `20260501T215343Z` at 2026-05-01T22:08:47Z makes the H freshness FAIL rows stale for runtime status, but they still remain real health output until the next owner health pass updates them.

## Real Test Results

| Proof | Result | Evidence |
|---|---|---|
| E002 ROI script | Passed | output printed `status=success`, `rows=58`, `snapshot=out\\sku_roi_snapshot.csv` |
| O030 Product DB operator view direct script path | Failed then rerun correctly | direct run failed with `ModuleNotFoundError: No module named 'scripts.flows'` |
| O030 Product DB operator view module run | Passed | output printed `status=success`, `rows=659` after SQL-authority read change |
| Focused pytest profile | Passed | 28 passed in 3.51s |
| P009 Product DB link simulation tests | Passed | 9 passed in 1.10s for P009 plus Product DB contract tests |
| Product DB duplicate-header repair tests | Passed | 12 passed in 2.17s for Product DB contract, preview storage, P008, and P009 tests |
| P010 Product DB review pack tests | Passed | 11 passed in 1.01s for P010, P009, and Product DB contract tests |
| P011 scanner Product DB insert tests | Passed | 14 passed in 1.35s for P011, P010, P009, and Product DB contract tests |
| P012 scanner identity tests | Passed | 12 passed in 2.27s for P012, P009, P010, and P011 tests |
| P013 repricer write-status proof tests | Passed | 5 passed in 0.97s for P013 and O050 repricer tracker tests |
| H blank write-status source tests | Passed | 25 passed in 4.52s for H split health, P013, O050, P012, and P011 tests |
| H item_offers timeout-budget tests | Passed | `python -m pytest tests/test_h_item_offers_retry_queue.py tests/test_h_split_health_gate.py tests/test_p013_repricing_write_status_proof.py tests/test_o050_repricing_tracker_view.py -q` passed 41 tests with 1 warning |
| P013/O050/P013-count focused tests | Passed | elevated rerun passed `29` tests for P013, O050, and H item-offers retry queue after sandbox temp permission errors blocked the non-elevated run |
| H item_offers live proof | Passed | H run `20260501T183549Z` logged retry-aware item-offers watchdog `effective_seconds=609` and item-offers completed in `190.70` seconds |
| P013 repricer live proof after finalized H run | Passed with stale-audit warning | P013 returned `status=warn` because stale `out/pricing_output.csv` is older than runtime and missing latest run rows; latest runtime source has 0 blank and 0 invalid write statuses |
| O050 repricer tracker rebuild after finalized H run | Passed with stale-audit warnings | O050 rebuilt 89 tracker rows; health has 9 ok checks and 2 warnings only for stale compact `out/pricing_output.csv` |
| P014 Product DB edit-event apply tests | Passed | `python -m pytest tests/test_p014_apply_product_db_edit_events.py tests/test_o420_product_database_edit_ui.py -q` passed 12 tests |
| P015 Product DB SQL authority rehearsal | Passed with warnings | P015 reported SQL 659 rows, O view 659 rows, CSV mirror 608 rows, 0 fail, 3 warn |
| Product DB / O / repricer focused verification | Passed | `python -m pytest tests/test_product_db_sql_contract.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o050_repricing_tracker_view.py tests/test_o030_build_product_db_operator_view.py -q` passed 24 tests |
| P016 repricer tracker UI cutover check | Passed with stale-audit warning | P016 at `2026-05-01T22:08:59Z` reported `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=1`, tracker rows `89`, terminal run `20260501T215343Z`, terminal state `finalized`, publish `ok`, and Sheet remains temporary fallback until explicit operator cutover |
| P017 repricer tracker UI parity proof | Passed with stale-audit warning | P017 at `2026-05-01T22:09:00Z` reported `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=0`, tracker rows `89`, missing critical fields `0`, missing dashboard reference fields `0`, and terminal run `20260501T215343Z` |
| P018 Product DB mirror drift guard | Passed with stale-mirror warning | P018 reported SQL rows `659`, SQL unique `seller_sku` `659`, O view rows `659`, CSV mirror rows `608`, `fail_count=0`, and CSV mirror status `mirror_stale_not_authority` |
| P019 Product DB reader dependency map | Passed with approval blockers recorded | P019 mapped `298` Product DB references across `87` files, with `0` unknown owners and `58` changes blocked without explicit approval |
| P020 PostgreSQL promotion rehearsal | Passed offline | P020 reported `status=ok`, `fail_count=0`, and production promotion `not_run_requires_explicit_approval` |
| P021 Phase 2 sign-off bundle | Passed local sign-off | P021 at `2026-05-01T22:09:01Z` reported `complete_locally_pending_explicit_cutover_approvals`, `fail_count=0`, and `warn_count=0`; completion report is `plans/active/sql-product-db-ui-authority-phase2-2026-05-01/COMPLETION_REPORT.md` |
| SQL/Product DB Phase 2 final focused verification | Passed | `python -m py_compile ...` passed for P017-P021, P014-P016, O030, and O050; focused pytest passed `26` tests in `5.84s` |

Test cleanup note: pytest returned exit code 0, but Windows raised an ignored temp-folder cleanup `PermissionError` for `pytest-current` after the tests completed.
