# O Reorder Input Data Source Map

This map defines where each reorder input field comes from for O flow.

## Field Mapping
| field_name | required_for_reorder_input | primary_source_file | primary_source_columns | fallback_source_file | fallback_source_columns | flow_owner | truth_type | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| supplier_name | yes | `out/systems/O/live/restock_source_view.csv` | `supplier_name` | `out/systems/O/live/restock_review_queue.csv` | `supplier_name` | O (derived from A/B snapshot) | current_state | Supplier-first grouping key in UI. |
| supplier_code | yes | `out/systems/O/live/restock_source_view.csv` | `supplier_code` | `out/systems/O/live/restock_review_queue.csv` | `supplier_code` | O | current_state | Used for grouping and downstream PO traceability. |
| seller_sku | yes | `out/systems/O/live/restock_source_view.csv` | `seller_sku` | `out/systems/O/live/restock_review_queue.csv` | `seller_sku` | O | current_state | Primary operator identity key. |
| asin | optional | `out/systems/O/live/restock_source_view.csv` | `asin` | `out/systems/O/live/restock_review_queue.csv` | `asin` | O | current_state | Secondary identity only. |
| title | yes | `out/systems/O/live/restock_source_view.csv` | `title` | `out/product_db_preview.csv` | `title` | O + A/B integration snapshot | current_state | Display clarity field. |
| main_image | yes | `out/systems/O/live/restock_source_view.csv` | `main_image` | `out/product_db_preview.csv` | `main_image` | O + A/B integration snapshot | current_state | Product visual in reorder input. |
| suggested_action | yes | `out/systems/O/live/restock_recommendations_live.csv` | `recommendation_status` | `out/systems/O/live/restock_review_queue.csv` | `recommendation_status` | O | current_state | Must be `full_restock` / `test_restock` for buy candidates. |
| suggested_qty | yes | `out/systems/O/live/restock_recommendations_live.csv` | `recommended_qty_rounded` | `out/systems/O/live/restock_review_queue.csv` | `suggested_qty` | O | current_state | Prefill for operator order qty confirmation. |
| suggested_unit_cost_gbp | yes | `out/systems/O/live/restock_recommendations_live.csv` | `current_supplier_buy_cost_gbp` | `out/systems/O/live/restock_source_view.csv` | `current_supplier_buy_cost_gbp` | O | current_state | Price prefill, operator must confirm before send. |
| suggested_market_price_gbp | yes | `out/systems/O/live/restock_recommendations_live.csv` | `market_price_gbp` | `out/systems/O/live/restock_source_view.csv` | `market_price_gbp` | O (derived from H/perf fallback) | current_state | Forward ROI context input. |
| expected_forward_roi_pct | yes | `out/systems/O/live/restock_recommendations_live.csv` | `forward_roi_pct` | `out/systems/O/live/restock_review_queue.csv` | `expected_forward_roi_pct` | O | current_state | Decision quality signal. |
| recommendation_reason | yes | `out/systems/O/live/restock_recommendations_live.csv` | `reason_codes` | `out/systems/O/live/restock_review_queue.csv` | `reason_codes` | O | current_state | Human-readable explanation for operator. |
| queue_status | yes | `out/systems/O/live/restock_review_queue.csv` | `queue_status` | none | none | O | current_state | Snooze and review state. |
| cost_mode | yes | `out/systems/O/live/restock_recommendations_live.csv` | `cost_mode` | `out/systems/O/live/restock_source_view.csv` | `cost_mode` | O | current_state | Distinguishes `live` vs `test` cost context. |
| recommendation_basis | yes | `out/systems/O/live/restock_recommendations_live.csv` | `recommendation_basis` | `out/systems/O/live/restock_review_queue.csv` | `recommendation_basis` | O | current_state | Lineage of recommendation context. |
| is_active_candidate | yes | `out/systems/O/live/restock_source_view.csv` | `is_active_candidate` | none | none | O | derived | Active/inactive gating for reorder readiness. |
| has_current_cost_input | yes | `out/systems/O/live/restock_source_view.csv` | `has_current_cost_input` | none | none | O | derived | Core blocker when missing. |
| has_current_market_price_input | yes | `out/systems/O/live/restock_source_view.csv` | `has_current_market_price_input` | none | none | O | derived | Core blocker when missing. |
| has_demand_input | yes | `out/systems/O/live/restock_source_view.csv` | `has_demand_input` | none | none | O | derived | Core blocker when missing. |
| coverage_block_reason | yes | `out/systems/O/live/restock_source_view.csv` | `coverage_block_reason` | none | none | O | derived | Explicit reason for non-actionable state. |

## Upstream Source Presence Checks (for proof)
| upstream_source | file | owner_flow | key_columns_used |
| --- | --- | --- | --- |
| product identity + supplier baseline | `out/product_db_preview.csv` | A/B integration snapshot | `seller_sku`, `supplier_code`, `supplier_name`, `title`, `main_image`, `supplier_catalog_price`, `last_purchase_price` |
| demand context | `out/sku_sales_velocity.csv` | E | `sku`, `v30`, `v7`, `v90` |
| economics context | `out/sku_performance_summary.csv` | E | `sku`, `expected_refund_cost_per_unit_gbp` |
| market context | `out/listing_offer_snapshot_latest.csv` | H | `sku`, `buy_box_price`, `lowest_fba_price`, `our_price` |

