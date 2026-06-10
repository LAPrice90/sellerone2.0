# Pack Size O Proof Summary

- proof_id: `pack_size_o_proof_20260519T153000Z`
- proof_root: `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\repricing-stock-cost-bridge-2026-05-19\proof\pack_size_o_proof_20260519T153000Z`
- generated_utc: `2026-05-19T15:30:00Z`
- source_rows: `608`
- recommendation_rows: `608`
- action_ready_rows: `6`
- po_headers: `6`
- po_lines: `6`
- po_holds: `0`

## Sika Source Proof
- `6V-EEC1-2S9Z` `484651`: status `active`, pack_status `confirmed`, components_per_sell_pack `3`, cost_basis `component_unit`, current_cost `4.35`, cost_source `supplier_buy_cost_truth_converted_to_sell_pack`, component_cost `1.45`, sell_pack_cost `4.35`, strategy `preferred_carton_multiple`, note `BLOCKED_MISSING_COST_INPUT|SOURCE_FILE_MISSING:f_price_list_manager_batch_rows|SOURCE_FILE_MISSING:f_price_list_manager_batches|SUPPLIER_BUY_COST_TRUTH_APPLIED|SUPPLIER_COST_CONVERTED_TO_SELL_PACK`
- `PE-G94Y-4PYO` `484652`: status `active`, pack_status `missing_pack_profile`, components_per_sell_pack `1`, cost_basis `sell_pack`, current_cost ``, cost_source `missing_cost`, component_cost ``, sell_pack_cost ``, strategy ``, note `BLOCKED_MISSING_COST_INPUT|REDUCED_CONFIDENCE_PRODUCT_DB_MARKET_CONTEXT|SOURCE_FILE_MISSING:f_price_list_manager_batch_rows|SOURCE_FILE_MISSING:f_price_list_manager_batches|SUPPLIER_BUY_COST_TRUTH_NO_USABLE_EXPECTED_COST|missing_pack_profile|special_order_profile_required`
- `A2-T2AC-TW3L` `484652`: status `active`, pack_status `confirmed`, components_per_sell_pack `3`, cost_basis `component_unit`, current_cost ``, cost_source `missing_cost`, component_cost ``, sell_pack_cost ``, strategy `preferred_carton_multiple`, note `BLOCKED_MISSING_COST_INPUT|SOURCE_FILE_MISSING:f_price_list_manager_batch_rows|SOURCE_FILE_MISSING:f_price_list_manager_batches|SUPPLIER_BUY_COST_TRUTH_NO_USABLE_EXPECTED_COST`

## Sika Recommendation Proof
- `6V-EEC1-2S9Z`: action `full_restock`, qty `172`, unit_cost `4.35`, ROI `60.45977`, reasons ``
- `PE-G94Y-4PYO`: action `wait`, qty `0`, unit_cost ``, ROI ``, reasons `SUPPLIER_COST_USER_CONFIRMATION_REQUIRED,LOW_CONFIDENCE_MARKET_CONTEXT,PACK_PROFILE_MISSING,SPECIAL_ORDER_PROFILE_REQUIRED`
- `A2-T2AC-TW3L`: action `wait`, qty `0`, unit_cost ``, ROI ``, reasons `SUPPLIER_COST_USER_CONFIRMATION_REQUIRED,BLOCKED_MISSING_COST_INPUT`

## Sika Coverage Proof
- `6V-EEC1-2S9Z`: action_ready `1`, blocks `coverage_block::ready_minimum_inputs`
- `PE-G94Y-4PYO`: action_ready `0`, blocks `wait_or_non_action_suggestion|missing_suggested_qty|missing_suggested_unit_cost|missing_expected_forward_roi|missing_cost_truth|missing_demand_truth|coverage_block::missing_cost_and_demand|supplier_cost_confirmation_required|missing_pack_profile|special_order_profile_required`
- `A2-T2AC-TW3L`: action_ready `0`, blocks `wait_or_non_action_suggestion|missing_suggested_qty|missing_suggested_unit_cost|missing_expected_forward_roi|missing_cost_truth|coverage_block::missing_cost_only|supplier_cost_confirmation_required`

## Sika PO Proof
- `6V-EEC1-2S9Z`: requested_sell_packs `172`, ordered_sell_packs `250`, components `750` bottle, supplier_boxes `30`, box_components `25`, hazmat `sika_glue`, isolated `1`, line_cost `4.35`
