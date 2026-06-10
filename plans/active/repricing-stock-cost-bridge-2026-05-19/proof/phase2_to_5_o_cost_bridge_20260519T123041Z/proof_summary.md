# Phase 2-5 O Cost Bridge Proof

Proof timestamp UTC: 2026-05-19T12:30:41Z

## Commands Run

- `python -m py_compile scripts\flows\O\_schemas.py scripts\flows\O\_source_contracts.py scripts\flows\O\O001_build_restock_source_view.py scripts\flows\O\O002_build_restock_recommendations.py scripts\flows\O\O003_build_restock_review_queue.py scripts\flows\O\O007_build_supplier_buy_cost_truth.py scripts\flows\O\O008_build_supplier_cost_confirmation_queue.py scripts\flows\O\O020_build_reorder_input_coverage_report.py scripts\cycles\run_O_cycle.py`
- `python -m pytest tests\test_o000_paths_and_schemas.py tests\test_o000_source_contracts.py tests\test_o007_supplier_buy_cost_truth.py tests\test_o008_supplier_cost_confirmation_queue.py tests\test_o_cycle_runner.py -q` -> 15 passed
- `python -m pytest tests\test_o001_restock_source_view.py tests\test_o002_restock_recommendations.py tests\test_o003_restock_review_queue.py tests\test_o020_reorder_input_coverage.py -q` -> 22 passed
- `python -m pytest tests\test_fpm070_stage_f061_handoff.py tests\test_fpm100_apply_f061_handoff.py tests\test_fpm130_live_cycle.py -q` -> 76 passed
- O test pack -> 147 passed
- Focused O module proof: O007, O008, O001, O002, O003, O004, O020 -> completed

## Rollback Snapshot

- Before-write snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_phase2_20260519T122526Z`

## Output Counts

| Metric | Rows |
|---|---:|
| supplier_buy_cost_truth rows | 608 |
| truth rows with price-list match | 90 |
| truth rows with expected cost | 199 |
| truth rows requiring user price check | 535 |
| supplier_cost_confirmation_queue rows | 535 |
| restock_source_view rows | 608 |
| source rows requiring user price check | 535 |
| restock_recommendations_live rows | 608 |
| recommendations requiring user price check | 535 |
| reorder_input_coverage_report rows | 608 |
| coverage action_ready_now rows | 6 |
| coverage rows requiring user price check | 535 |

### Cost Confidence Counts

| Value | Rows |
|---|---:|
| none | 409 |
| actual_paid_without_list_reference | 109 |
| price_list_only | 67 |
| discount_assumption_needs_confirmation | 12 |
| price_list_actual_match | 6 |
| actual_paid_above_list_needs_review | 5 |

### Expected Cost Source Counts

| Value | Rows |
|---|---:|
| missing_cost | 409 |
| last_purchase_price | 109 |
| supplier_price_list | 67 |
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
| missing_expected_cost | 241 |
| within_target_roi_max | 65 |
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
| missing_expected_forward_roi | 542 | missing_input |
| supplier_cost_confirmation_required | 535 | other |
| inactive_or_unknown_status | 464 | state_or_policy |
| coverage_block::inactive_status | 411 | missing_input |
| missing_cost_truth | 409 | missing_input |
| missing_suggested_unit_cost | 409 | missing_input |
| missing_market_truth | 301 | missing_input |
| missing_suggested_market_price | 301 | missing_input |
| coverage_block::missing_cost_and_demand | 75 | missing_input |
| missing_supplier_name | 54 | missing_input |
| coverage_block::inactive_or_unknown_status | 53 | missing_input |
| coverage_block::missing_cost_only | 32 | missing_input |
