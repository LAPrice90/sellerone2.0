# Phase 2-5 O Cost Bridge Proof

Proof timestamp UTC: 2026-05-19T12:39:03Z

## Commands Run

- `python -m py_compile scripts\flows\O\O007_build_supplier_buy_cost_truth.py` -> passed after parser cleanup
- `python -m pytest tests\test_o007_supplier_buy_cost_truth.py tests\test_o008_supplier_cost_confirmation_queue.py tests\test_o001_restock_source_view.py tests\test_o002_restock_recommendations.py tests\test_o020_reorder_input_coverage.py -q` -> 21 passed after parser cleanup
- Full O test pack after parser cleanup: 147 passed
- Prior F source-shape regression pack: 76 passed
- Focused O module proof after parser cleanup: O007, O008, O001, O002, O003, O004, O020 -> completed

## Rollback Snapshot

- Before-write snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_phase2_20260519T122526Z`

## Output Counts

| Metric | Rows |
|---|---:|
| supplier_buy_cost_truth rows | 608 |
| truth rows with price-list match | 87 |
| truth rows with expected cost | 196 |
| truth rows requiring user price check | 538 |
| supplier_cost_confirmation_queue rows | 538 |
| restock_source_view rows | 608 |
| source rows requiring user price check | 538 |
| restock_recommendations_live rows | 608 |
| recommendations requiring user price check | 538 |
| reorder_input_coverage_report rows | 608 |
| coverage action_ready_now rows | 6 |
| coverage rows requiring user price check | 538 |

### Cost Confidence Counts

| Value | Rows |
|---|---:|
| none | 412 |
| actual_paid_without_list_reference | 109 |
| price_list_only | 64 |
| discount_assumption_needs_confirmation | 12 |
| price_list_actual_match | 6 |
| actual_paid_above_list_needs_review | 5 |

### Expected Cost Source Counts

| Value | Rows |
|---|---:|
| missing_cost | 412 |
| last_purchase_price | 109 |
| supplier_price_list | 64 |
| discount_assumption_from_actual_paid | 12 |
| supplier_price_list_no_discount | 6 |
| actual_paid_above_list_review | 5 |

### Recommendation Status Counts

| Value | Rows |
|---|---:|
| wait | 602 |
| full_restock | 6 |

### Purchase Safety Status Counts

| Value | Rows |
|---|---:|
| missing_market_price | 301 |
| missing_expected_cost | 244 |
| within_target_roi_max | 62 |
| above_break_even_max | 1 |

## Action-Ready Guard Check

- Action-ready rows: 6
- Action-ready rows still requiring user price check: 0

## Top Block Reasons

| Block reason | Rows | Type |
|---|---:|---|
| missing_suggested_qty | 602 | missing_input |
| wait_or_non_action_suggestion | 602 | state_or_policy |
| missing_demand_truth | 557 | missing_input |
| missing_expected_forward_roi | 545 | missing_input |
| supplier_cost_confirmation_required | 538 | other |
| inactive_or_unknown_status | 464 | state_or_policy |
| missing_cost_truth | 412 | missing_input |
| missing_suggested_unit_cost | 412 | missing_input |
| coverage_block::inactive_status | 411 | missing_input |
| missing_market_truth | 301 | missing_input |
| missing_suggested_market_price | 301 | missing_input |
| coverage_block::missing_cost_and_demand | 78 | missing_input |
| missing_supplier_name | 54 | missing_input |
| coverage_block::inactive_or_unknown_status | 53 | missing_input |
| coverage_block::missing_cost_only | 32 | missing_input |
