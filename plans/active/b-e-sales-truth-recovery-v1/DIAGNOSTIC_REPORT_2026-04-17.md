# B/E Sales Truth Diagnostic Report

Date: 2026-04-17
Scope: determine whether B already has usable sales truth, identify why current SKU sales outputs are wrong, and define the minimum fix path to accurate sales reporting.

## 1. Executive conclusion

Yes - B already has real sales truth.

The current problem is not "no sales data".
The current problem is that E is corrupting B-derived sales economics before they reach `sku_roi_snapshot.csv` and `sku_performance_summary.csv`.

There are 2 separate failure classes:

1. E002 is zeroing revenue during FX multiplication because the filtered order rows keep their old indexes while the FX-rate series is rebuilt with a fresh `0..N` index.
2. E002 is treating valid negative COGS and valid negative fees as if they were missing or positive costs, which makes both `missing_cogs_units` and profit math wrong.

There is also a secondary bridge gap inside B outputs that must be reconciled before final sign-off:

- `order_master.csv` and `order_ledger_fx.csv` are close, but not identical, in the same 30 day window.

## 2. What is working

### B scoped health

From `out/cycle_alerts/checklist_B.csv` during this diagnostic pass:

- no active warn/fail rows were present
- `order_master.csv` freshness was current
- `orders_all.csv` freshness was current
- token shortage check was `0`

### B source files contain real sales data

From `out/order_master.csv`:

- `9473` rows
- only `1` qty-positive row with zero price
- `0` blank `COGS_ExVAT` rows in level-1-plus scope

From `out/order_ledger_fx.csv` in the 30 day window anchored to `order_master` max date:

- window start: `2026-03-18T20:45:04+00:00`
- rows: `1620`
- units: `1871`
- revenue ex VAT GBP: `13707.40`
- COGS ex VAT: `-6560.58`
- fees ex VAT GBP: `-5624.87`
- profit contribution GBP: `1521.95`
- unique selling SKUs: `61`

From `out/pnl_daily.csv`:

- `Net_Profit_ExVAT` total is nonzero and current
- this supports the view that the B/D economic path is alive

## 3. What is broken

### E outputs are flatlined

From `out/sku_roi_snapshot.csv`:

- rows: `61`
- selling rows: `61`
- units sold: `1929`
- revenue ex VAT GBP: `0.00`
- profit ex VAT GBP: `0.00`
- selling rows with zero revenue: `61`
- selling rows with zero profit: `61`
- `missing_cogs_units`: `1929`

From `out/sku_performance_summary.csv`:

- selling rows: `61`
- units sold: `1913`
- revenue ex VAT GBP: `0.00`
- profit ex VAT GBP: `0.00`
- selling rows with zero revenue: `61`
- selling rows with zero profit: `61`
- `missing_cogs_units`: `1913`

This is not a "small drift" problem.
It is a total economics collapse in the E SKU layer.

### Concrete SKU example

SKU: `LV-425G-BY4X`

From `out/sku_performance_summary.csv`:

- units sold: `19`
- revenue ex VAT GBP: `0.00`
- COGS ex VAT GBP: `-311.22`
- profit ex VAT GBP: `0.00`
- missing COGS units: `19`

From `out/order_ledger_fx.csv` over the same 30 day scope:

- rows: `19`
- units: `19`
- revenue ex VAT GBP: `443.51`
- COGS ex VAT: `-311.22`
- fees ex VAT GBP: `-117.72`
- profit contribution GBP: `14.57`

The current published SKU output says:

- sold `19`
- made `0`

The B-derived truth says:

- sold `19`
- revenue about `GBP 443.51`
- profit about `GBP 14.57`

## 4. Root causes

### Root cause 1 - index alignment bug in E002

File: `scripts/flows/E/E002_build_roi_snapshot.py`

Relevant logic:

- filter orders to last 30 days
- build `rate_to_gbp` as `pd.Series(rate_to_gbp)`
- multiply `revenue_order * rate`

The filtered `orders` frame keeps original row indexes such as `7809..9473`.
The new FX series gets a fresh `0..1664` index.
Pandas aligns by index labels during multiplication.
That produces `NaN` for almost every row.
When grouped and summed, revenue collapses to `0`.

Proof from direct reproduction:

- window rows: `1665`
- nonzero price rows: `1665`
- revenue product sum with original index: `0.00`
- revenue product NaN rows with original index: `3330`
- revenue product sum after `reset_index(drop=True)`: `13809.60`

### Root cause 2 - wrong profit sign handling

In the same file, current logic does this:

- `cost_exvat = cogs + fee_gbp`
- `profit_exvat = revenue_exvat - cost_exvat`

But `COGS_ExVAT` and fee columns are already stored as negative expense values.
Subtracting a negative cost turns the expense back into added profit.

Proof using the live `LV-425G-BY4X` sample:

- revenue: `443.51`
- cogs: `-311.22`
- fee: `-117.72`
- current formula result if revenue were fixed: `872.45`
- correct contribution result: `14.57`

Proof using the 30 day ledger contribution totals:

- current formula result if revenue were fixed: `25892.85`
- correct contribution result: `1521.95`

### Root cause 3 - wrong missing COGS rule

Current logic:

- `missing_cogs = (cogs <= 0).astype(int)`

That flags all valid negative COGS rows as missing.
Negative COGS is the normal sign for an expense in this pipeline.

This is why every selling SKU is showing `missing_cogs_units == units_sold`.

### Root cause 4 - no sales-truth health gate

Current `checklist_E.csv` / `checklist_E_split.csv` shows schema checks only.
There is no truth check for:

- selling rows with zero revenue
- selling rows with zero profit while source revenue exists
- `missing_cogs_units == units_sold` for live selling SKUs
- B/E reconciliation drift

The system therefore lets a catastrophic economics failure pass as "healthy".

### Root cause 5 - B bridge delta still needs explaining

In the same 30 day window:

From `order_master.csv`:

- rows: `1665`
- units: `1928`

From `order_ledger_fx.csv`:

- rows: `1620`
- units: `1871`

By `Order ID + SKU` key:

- `46` keys exist in `order_master` but not in `order_ledger_fx`
- `1` key exists in `order_ledger_fx` but not in `order_master`
- the `order_master`-only side represents `58` units and about `308.89` in order-currency revenue

This does not explain the zero-revenue bug in E.
It is a separate reconciliation task that must be closed before sales truth can be called final.

## 5. Diagnostic boundary issue found during this pass

Running `scripts/flows/D/D004_build_order_master_audit.py` during diagnostics triggered a Google Sheets add-sheet attempt and failed with:

- `APIError: [400]: Invalid requests[0].addSheet: This action would increase the number of cells in the workbook above the limit of 10000000 cells.`

No sheet change succeeded.

However, this is still a boundary problem:

- a local diagnostic script should not attempt sheet writes by default when the task is investigation

## 6. Recovery direction

Recommended order:

1. Fix E002 math first.
2. Add focused tests that prove revenue, profit, and missing-COGS handling.
3. Rebuild E outputs and verify against B truth.
4. Add truth-based E health checks.
5. Build a B/E reconciliation output and close the `order_master` vs `order_ledger_fx` gap.
6. Only then sign off sales truth as accurate enough to feed repricer learning and new-product learning.
