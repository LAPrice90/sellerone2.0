# Data Contracts

## Source hierarchy

### Level 3 - finalized financial truth
| File | Owner | Role | Allowed use |
|---|---|---|---|
| `out/financial_events_level3_official.csv` | B | posted financial truth | finalized economics reference |
| `out/order_ledger_fx.csv` | B | GBP-normalized finalized ledger | finalized revenue and profit basis when fresh |
| `out/sku_daily_sales_truth_latest.csv` with `source_state=finalized_ledger` | E | finalized daily truth | canonical learning actuals |

Rule:
- use Level 3 for final profit and revenue learning truth

### Level 2 - fallback support
| File | Owner | Role | Allowed use |
|---|---|---|---|
| `out/financial_events_level2.csv` | B | intermediate event support | fallback inside B only unless explicitly promoted later |

Rule:
- do not make Level 2 the primary learning truth layer

### Level 1 - earliest operational signal
| File | Owner | Role | Allowed use |
|---|---|---|---|
| `out/financial_events_level1.csv` | B | earliest order visibility | operational timing and provisional support only |
| `out/order_master.csv` | B | merged operational order mart | bridge and provisional support |
| `out/sku_daily_sales_truth_latest.csv` with `source_state=provisional_order_master` | E | provisional recent daily truth | recent, not final, learning state |

Rule:
- Level 1 is allowed for early visibility
- Level 1 is not allowed as final profit truth

## Current operational outputs
| File | Contract role | Trust status | Freshness rule |
|---|---|---|---|
| `out/order_master.csv` | current operational order mart | high operational trust | must be newest source in daytime B activity |
| `out/order_ledger_fx.csv` | finalized normalized ledger | high truth when fresh | warn if older than `order_master.csv` by more than `90` minutes; fail if older by more than `240` minutes |
| `out/sku_roi_snapshot.csv` | 30-day economics view | derived truth | not safe for feedback if ledger freshness rule fails |
| `out/sales_truth_sku_30d_latest.csv` | reconciliation B-side 30d truth | reconciliation artifact | not safe as sole learning input if older than current `order_master.csv` window |
| `out/sales_truth_reconciliation_latest.csv` | mismatch report | validation artifact | use to prove math alignment, not to supply actuals alone |
| `out/sku_daily_sales_truth_latest.csv` | daily finalized/provisional truth | canonical actuals base | must preserve source-state split |
| `out/sku_performance_summary.csv` | operator summary | derived operational summary | reference only for ranking and context |

## F-side learning outputs
| File | Current role | Future role |
|---|---|---|
| `out/systems/F/live/feeder_backtest_summary_live.csv` | decision snapshot | expected-side source |
| `out/analysis_reports/f_sales_history_learning_actuals_latest.csv` | manual or external actuals shape | automated actuals output after Phase 1 |
| `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv` | manual fill helper | fallback only after Phase 1 |
| `out/systems/F/live/feeder_sales_history_learning_live.csv` | learning log | final joined learning output |

## Join rules
- Forbidden join:
  - `F seller_sku -> B/E sku`
- Required join path:
  - `F asin -> operational bridge -> operational sku -> daily truth`
- Every bridge row must carry one of:
  - `resolved`
  - `ambiguous`
  - `unresolved`

## Trust-state rules
- `finalized_ledger`
  - safe for final learning actuals
- `provisional_order_master`
  - safe for recent visibility only
- stale truth outputs
  - must be flagged, not silently used

## Promotion rule
- No builder from this plan is promoted into a daily loop until:
  - freshness health exists
  - bridge health exists
  - automated actuals fill is proven
