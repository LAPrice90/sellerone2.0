# O Net Fee Restock Bridge Coding Plan

Created UTC: 2026-05-19T15:08:02Z
Owner flow: O with A/MOT visibility
Status: in_progress

## Plain-English Goal

The restock decision should use the same real selling-cost truth that the scripts database already has. B records the actual Amazon fee breakdown while orders are processed. E turns that into SKU-level break-even and net ROI. O currently receives only part of that, then calculates future restock ROI with a gross shortcut.

The bridge is the missing pipe between E and O. O must carry the E net cost truth into the restock source view, use it in the buy/no-buy maths, and block buying when that truth is missing, invalid, or stale.

## Root Cause Found

- B writes real fee fields into `out/order_master.csv` and `out/financial_events_level3_official.csv`.
- E uses those fields to calculate `current_token_cost_gbp`, `break_even_price_gbp`, refund cost, and net ROI in `out/sku_performance_summary.csv`.
- O001 reads E performance but only carries refund cost and ROI context into `restock_source_view.csv`.
- O002 then calculates forward profit as market price minus supplier cost minus refund drag. It does not subtract Amazon fee drag and does not convert the VAT-inclusive market price onto the same net basis.

## Scope

Allowed implementation files:
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O002_build_restock_recommendations.py`
- `scripts/flows/O/O003_build_restock_review_queue.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- focused O/A tests under `tests/`
- `project_control/DUE_CHECK_REGISTER.csv`

No Google Sheets writes are approved. No local database alignment change is approved. No B scripts should be run for this work.

## Design

1. O001 will add a net-fee context to every restock source row:
   - `market_price_ex_vat_gbp`
   - `market_price_vat_rate_pct`
   - `current_token_cost_gbp`
   - `break_even_price_gbp`
   - `net_fee_drag_per_unit_gbp`
   - `net_fee_model_status`
   - `net_fee_model_asof`
   - `net_fee_model_age_hours`
   - `net_fee_model_source`
   - `net_fee_model_notes`

2. O002 will calculate restock ROI on the net basis:
   - net market price = `market_price_ex_vat_gbp`
   - net fee drag = `break_even_price_gbp - current_token_cost_gbp - expected_refund_cost_per_unit_gbp`
   - net profit = net market price minus supplier sell-pack cost minus fee drag minus refund drag
   - net ROI = net profit divided by supplier sell-pack cost

3. O002 will keep gross ROI fields for audit only:
   - `gross_forward_profit_per_unit_gbp`
   - `gross_forward_roi_pct`

4. O002 will block active buy recommendations if the net-fee model is not safe:
   - `BLOCKED_MISSING_NET_FEE_INPUT`
   - `BLOCKED_STALE_NET_FEE_INPUT`
   - `BLOCKED_INVALID_NET_FEE_INPUT`

5. O020 will carry the net-fee status into the coverage report and prevent `action_ready_now=1` unless the net-fee model is fresh.

6. A015/MOT will gain an O-owned check that proves the bridge is live:
   - action-ready rows must have `net_fee_model_status=fresh`
   - action-ready rows must have net fee fields populated
   - rows with fee drag must not have net ROI silently equal to gross ROI
   - the bridge age must stay inside the freshness limit

## Freshness Rule

Fresh limit: 48 hours from the E performance `asof_date` to the O source `asof_utc`.

Reason: E performance is a daily SKU-level summary. O should tolerate the normal daily cycle gap but should not keep creating buy decisions from old fee truth.

Failure behavior:
- missing E row: block buying for that SKU
- missing required economics field: block buying for that SKU
- missing VAT rate: use the same conservative UK 20 percent default basis and leave a visible `NET_FEE_VAT_RATE_DEFAULTED_20` note
- invalid VAT or negative fee drag: block buying for that SKU
- stale E performance: block buying for that SKU

## Test Plan

Focused tests:
- O001 carries break-even, token cost, VAT, net fee drag, status, age, and source.
- O001 marks stale/missing/invalid net fee context.
- O002 uses net ROI, not gross ROI, for restock status and max purchase price.
- O002 blocks stale/missing/invalid net fee context.
- O003 carries net-fee audit fields into review queue.
- O020 blocks `action_ready_now` when net-fee truth is missing or stale.
- A015 reports O net-fee bridge status for MOT.
- Due-check register status still parses the new two-week MOT follow-up.

Runtime proof:
- Run focused pytest profile for O/A changes.
- Run O001/O002/O003/O020/O health proof against current local data only after tests pass and after making a rollback snapshot of affected O outputs.
- Do not run A015 ad hoc unless explicitly required for a narrow test; unit tests are the proof path for A015 code.

## Live Monitoring Target

For every morning MOT from 2026-05-20 through 2026-06-02 inclusive:
- inspect `out/systems/O/live/restock_source_view.csv`
- inspect `out/systems/O/live/restock_recommendations_live.csv`
- inspect `out/systems/O/live/reorder_input_coverage_report.csv`
- inspect `out/cycle_alerts/checklist_all.csv` or the O checklist if generated

Success condition:
- O net-fee bridge check is ok
- no action-ready row has missing, stale, or invalid net-fee status
- any SKU with stale fee truth is blocked rather than buyable

Failure action:
- classify as `fix now`
- inspect O001 net-fee context first
- then inspect E `out/sku_performance_summary.csv`
- do not patch O output downstream to hide the issue

## Phase Status

- Phase 1 research: completed
- Phase 2 coding plan: completed
- Phase 3 O bridge implementation: completed
- Phase 4 A/MOT health and due check: completed for A/MOT
- Phase 5 tests and current-data proof: completed
- Phase 6 two-week MOT monitoring setup: completed

## A/MOT Evidence

- 2026-05-19T15:13:15Z: Added A015 `o_net_fee_bridge_health` to inspect O live restock source, recommendation, and reorder coverage outputs.
- 2026-05-19T15:13:15Z: Added O split alert routing so `o_...` checks write under `out/cycle_alerts/checklist_O.csv` during global A015 output splitting.
- 2026-05-19T15:13:15Z: Added due-check register row `O_NET_FEE_RESTOCK_BRIDGE_MOT_20260520_20260602` for every morning MOT from 2026-05-20 through 2026-06-02 inclusive.
- Validation passed: `python -m py_compile scripts/flows/A/A015_build_system_health_check.py`.
- Validation passed: `python -m pytest tests/test_a015_health_check_runtime.py -k "o_net_fee_bridge or routes_o_checks or profile_filter_mask"` with 6 passed.
- Validation passed: `python -m pytest tests/test_due_check_register.py` with 6 passed.
- Validation passed: parsed `project_control/DUE_CHECK_REGISTER.csv` with `due_check_register.build_due_check_status(...)`; new row count was 1 and the new row became due/warn at 2026-05-20T09:00:00Z.
- A015 was not run ad hoc; this phase used focused unit/helper tests only.

## O Implementation Evidence

- 2026-05-19T15:17:47Z: Created rollback snapshot at `project_control/backups/o_net_fee_bridge_before_refresh_20260519T151747Z`.
- Validation passed: `python -m py_compile scripts/flows/O/O001_build_restock_source_view.py scripts/flows/O/O002_build_restock_recommendations.py scripts/flows/O/O003_build_restock_review_queue.py scripts/flows/O/O020_build_reorder_input_coverage_report.py scripts/flows/O/_schemas.py scripts/flows/A/A015_build_system_health_check.py tests/test_o001_restock_source_view.py tests/test_o002_restock_recommendations.py tests/test_o020_reorder_input_coverage.py tests/test_a015_health_check_runtime.py`.
- Validation passed: `python -m pytest tests/test_o001_restock_source_view.py tests/test_o002_restock_recommendations.py tests/test_o003_restock_review_queue.py tests/test_o020_reorder_input_coverage.py tests/test_o000_paths_and_schemas.py -q` with 37 passed.
- Validation passed: `python -m pytest tests/test_a015_health_check_runtime.py -k "o_net_fee_bridge or routes_o_checks or profile_filter_mask" -q` with 6 passed.
- Validation passed: `python -m pytest tests/test_due_check_register.py -q` with 6 passed.
- Current O refresh passed using module entrypoints for O001, O002, O003, and O020. Output row counts: restock source 608, recommendations 608, coverage 608, supplier coverage 426, block reasons 23.
- Current live bridge counts: `net_fee_model_status=fresh` 160 rows, `missing` 448 rows, `stale` 0 rows, `invalid` 0 rows.
- Current action-ready safety count: 0 action-ready rows and 0 action-ready rows with non-fresh net-fee status.
- DC-K5WH-R7F5 proof: E `current_token_cost_gbp=0.631786`, E `break_even_price_gbp=2.617652`, O `net_fee_drag_per_unit_gbp=1.985866`, O `forward_roi_pct=-20.968594`, O `gross_forward_roi_pct=367.1875`, O status `wait` with `COST_ABOVE_BREAK_EVEN_MAX_PURCHASE_PRICE`.

## Monitoring Evidence

- Durable due check: `project_control/DUE_CHECK_REGISTER.csv` row `O_NET_FEE_RESTOCK_BRIDGE_MOT_20260520_20260602`.
- App automation: `o-net-fee-restock-mot-check`, active daily for 14 runs at the morning MOT window.
