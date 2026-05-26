# O Reorder Input Rules

These rules define how reorder input rows are constructed and when rows are actionable.

## Core Design
- Supplier-first workflow: rows are grouped by supplier.
- SKU-first operator view: `seller_sku` is primary identity, `asin` secondary.
- Operator confirms only two buy inputs for send path:
- `order_qty`
- `confirmed_price`

## Field Rules
| field | definition | source priority | allowed blank | confidence marker | send-blocking |
| --- | --- | --- | --- | --- | --- |
| supplier_name | Supplier label for batch ordering | `restock_source_view.supplier_name` -> `restock_review_queue.supplier_name` | no | n/a | yes |
| seller_sku | SKU identity key | `restock_source_view.seller_sku` -> `restock_review_queue.seller_sku` | no | n/a | yes |
| title | Product title for operator readability | `restock_source_view.title` -> `product_db_preview.title` | yes | row block reason includes `missing_title` | no |
| main_image | Product image URL | `restock_source_view.main_image` -> `product_db_preview.main_image` | yes | row block reason includes `missing_main_image` | no |
| suggested_action | Action proposal (`full_restock`, `test_restock`, `wait`) | `restock_recommendations_live.recommendation_status` -> `restock_review_queue.recommendation_status` | no | n/a | yes |
| suggested_qty | Proposed units to order | `restock_recommendations_live.recommended_qty_rounded` -> `restock_review_queue.suggested_qty` | no for auto-ready | n/a | yes |
| suggested_unit_cost_gbp | Cost prefill used for confirmation | `restock_recommendations_live.current_supplier_buy_cost_gbp` -> `restock_source_view.current_supplier_buy_cost_gbp` | yes | derived block reason `missing_cost_truth` or `missing_suggested_unit_cost` | yes |
| suggested_market_price_gbp | Market reference price | `restock_recommendations_live.market_price_gbp` -> `restock_source_view.market_price_gbp` | yes | derived block reason `missing_market_truth` | no (for manual review), yes (for auto-ready) |
| expected_forward_roi_pct | Forward ROI at current inputs | `restock_recommendations_live.forward_roi_pct` -> `restock_review_queue.expected_forward_roi_pct` | yes | low confidence if missing | no (for manual review), yes (for auto-ready) |
| profit_verdict | Plain-English profit proof result | `restock_profit_checks_live.profit_verdict` | yes | `missing_profit_inputs`, `needs_price_check`, or `temporary_market_risk` | no (visible for review), yes for clean auto-ready |
| profit_proof_source | Whether proof is native or Sheet-derived | `restock_profit_checks_live.profit_proof_source` | yes | `legacy_sheet_profit_hint` means Sheet hint only | no |
| profit_check_message | Operator-facing profit explanation | `restock_profit_checks_live.profit_check_message` | yes | shown on Reorder row | no |
| recommendation_reason | Human-readable reason code summary | `restock_recommendations_live.reason_codes` -> `restock_review_queue.reason_codes` | yes | row block reason includes `missing_recommendation_reason` | no |
| cost_mode | `live` or `test` | `restock_recommendations_live.cost_mode` -> `restock_source_view.cost_mode` -> default `live` | no | n/a | no |
| recommendation_basis | lineage of recommendation context | `restock_recommendations_live.recommendation_basis` -> `restock_review_queue.recommendation_basis` | no | n/a | no |
| queue_status | operator queue state including snooze | `restock_review_queue.queue_status` | yes | n/a | yes when `snoozed` |

## Action Readiness Rules
A row is `action_ready_now=1` only when all are true:
- `suggested_action` is `full_restock` or `test_restock`
- active candidate (`is_active_candidate=1`)
- `has_current_cost_input=1`
- `has_current_market_price_input=1`
- `has_demand_input=1`
- `supplier_name` present
- `seller_sku` present
- `suggested_qty` numeric and > 0
- `suggested_unit_cost_gbp` numeric and > 0

## Blocking Reason Rules
- Reasons are explicit in `block_reason_codes` as pipe-separated values.
- State blockers:
- `wait_or_non_action_suggestion`
- `snoozed`
- `inactive_or_unknown_status`
- Truth blockers:
- `missing_cost_truth`
- `missing_market_truth`
- `missing_demand_truth`
- Input/presentation blockers:
- `missing_supplier_name`
- `missing_seller_sku`
- `missing_suggested_qty`
- `missing_suggested_unit_cost`
- `missing_title`
- `missing_main_image`

## Manual Confirmation Rule
- Even when cost is prefilled, operator confirmation is mandatory before send event creation.
- Send event path stays append-only via:
- `out/systems/O/inbox/restock_decision_events.csv`

## Profit Check Guardrails
- `restock_profit_checks_live.csv` is the operator proof layer for "will this make money now?"
- `restock_profit_check_health.csv` records counts by verdict, supplier, proof source, and missing input reason.
- `restock_profit_check_history.csv` keeps repeated bad-economics evidence so a one-day bad market price cannot become a drop review by itself.
- A single low current market price can produce `temporary_market_risk` or `do_not_buy_now`, but not automatic product drop.
- `drop_review_only` from current economics requires at least 3 bad-economics snapshots across at least 7 days.
- `legacy_sheet_profit_hint` is allowed as a bridge warning only; it is not native current-profit proof.
- `legacy_purchase_list_no_data` can be `test_only` only when supplier cost is positive. CPU 0 stays blocked as `missing_profit_inputs`.
