# Study Report - 2026-04-20

## Scope
- study the existing 30-day sales truth path in B and E
- assess how reliable it is for F learning
- define the next automation phase so the loop becomes self-feeding

## Evidence snapshot

### Current file state
| File | Last write | Key fact |
|---|---|---|
| `out/order_master.csv` | 2026-04-20 14:50:56 BST | current operational order mart |
| `out/order_ledger_fx.csv` | 2026-04-20 06:03:29 BST | GBP-normalized ledger still older than current order master |
| `out/sales_truth_sku_30d_latest.csv` | 2026-04-20 06:01:11 BST | 58 rows, stale versus later B activity |
| `out/sku_daily_sales_truth_latest.csv` | 2026-04-20 06:01:12 BST | 439 rows, `426` finalized and `13` provisional |
| `out/sku_performance_summary.csv` | 2026-04-20 06:01:08 BST | 159 SKU rows, no ASIN column |
| `out/systems/F/live/feeder_backtest_summary_live.csv` | 2026-04-20 16:23:00 BST | 2358 rows, current F decision universe |
| `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv` | 2026-04-20 14:02:31 BST | still a manual fill shape |

### Freshness facts
- `order_master` max order timestamp:
  - `2026-04-20T13:02:54Z`
- `order_ledger_fx` max ledger timestamp:
  - `2026-04-20T00:00:00Z`
- lag from `order_master` to `order_ledger_fx`:
  - about `13.05` hours
- `sales_truth_sku_30d_latest.csv` current `asof_date`:
  - `2026-04-18`
- `sku_daily_sales_truth_latest.csv` current max `date`:
  - `2026-04-20`

### Identity facts
- F backtest summary unique `seller_sku` count:
  - `2307`
- E performance summary unique `sku` count:
  - `159`
- direct `seller_sku -> sku` overlap:
  - `0`
- F backtest summary unique ASIN count:
  - `2339`
- overlap with current operational listing history ASIN set:
  - `0`

## What is right already

### 1. The source layering is sensible
- B already follows the right business idea:
  - L1 = fastest operational order visibility
  - L3 = best posted financial truth
- `order_master.csv` already acts as the merged operational mart with level precedence.
- `sku_daily_sales_truth_latest.csv` already separates finalized rows from provisional rows.

### 2. The economics truth direction is right
- For feedback and learning, final profit truth should come from:
  - L3-backed rows
  - GBP-normalized ledger outputs
- Same-day provisional rows should be allowed, but clearly labeled as provisional.

### 3. The BBP demand-cleanup work has value
- F already learned to ignore future predicted month bars and use completed months.
- That means the market-estimate side is cleaner than before.

## What is wrong or incomplete

### 1. Freshness is not flow-safe yet
- The structure is good, but the handoff is weak.
- B can keep updating `order_master.csv` while:
  - `order_ledger_fx.csv`
  - `sales_truth_sku_30d_latest.csv`
  - `sku_performance_summary.csv`
  stay on an older run
- That makes the truth chain mathematically right but operationally stale.

### 2. F actual learning is not automated yet
- `F012_build_sales_history_learning_pack.py` still expects an external actuals file shape.
- It can infer outcomes after actuals exist, but it does not own the actuals acquisition.

### 3. There is no valid direct bridge from F to B/E
- F `seller_sku` is not the same thing as operational B/E `sku`.
- The current supplier-scan universe is not the same as the current catalog sales universe.
- So a self-feeding loop cannot be built on a naive join.

### 4. The current 30-day truth output is too narrow for the learning job
- `sales_truth_sku_30d_latest.csv` is useful as a reconciliation snapshot.
- It is not enough on its own for learning because it lacks:
  - bridge status
  - provisional versus finalized split per day
  - freshness truth
  - explicit operational ASIN mapping

## Reliability decision

### Source reliability by level
- Level 3:
  - use for finalized profit and revenue truth
  - this is the correct basis for learning sign-off
- Level 2:
  - fallback support only
  - not the preferred learning truth layer
- Level 1:
  - use only for early operational visibility and provisional unit timing
  - do not use as final profit truth

### Practical reliability score
- sales source design:
  - `7/10`
- economics truth:
  - `8/10`
- freshness handoff:
  - `4/10`
- F to B/E bridge:
  - `2/10`
- operator automation:
  - `3/10`

## Design decisions for the next phase

### Canonical actuals rule
- Canonical finalized actuals for learning must come from:
  - `sku_daily_sales_truth_latest.csv` rows where `source_state=finalized_ledger`
- Canonical provisional actuals for very recent dates may come from:
  - `sku_daily_sales_truth_latest.csv` rows where `source_state=provisional_order_master`
- `sales_truth_sku_30d_latest.csv` should remain a reconciliation artifact, not the only learning source.

### Canonical join rule
- The bridge must be:
  - `operational asin -> operational sku -> daily truth`
- It must not assume:
  - `F seller_sku == B/E sku`

### Canonical replay rule
- To validate F against real sales, we need a deliberate operational replay set built from:
  - currently sold products
  - current catalog ASINs
  - recent operational universe
- Reusing only the live supplier-scan universe is not enough.

### User-role rule
- The user should only review:
  - logic decision examples
  - misclassified examples
  - borderline examples
- The user should not fill actual sales figures manually in normal operation.

## Next phase summary

### Batch 000
- build sales-truth freshness foundation
- build operational ASIN bridge
- emit health and unresolved counts

### Batch 001
- auto-build F actuals from B/E truth
- replace manual actuals template as the normal path

### Batch 002
- build operator example pack
- show expected vs actual and why

### Batch 003
- promote to scheduled one-off automation with health gates
