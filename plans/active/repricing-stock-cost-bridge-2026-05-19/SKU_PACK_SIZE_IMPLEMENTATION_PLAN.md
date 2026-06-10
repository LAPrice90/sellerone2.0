# SKU Pack Size Implementation Plan

Date: 2026-05-19

Scope:
- Add pack-size and special buying treatment to the O restocking stock-decider path before any real purchase-order approval.
- Keep normal products simple: most SKUs should continue to buy as needed.
- Treat the Sika glue SKUs as the first special profile because they have hazmat handling and carton-size logic.

## 1. Problem To Fix

The current O proof treated Sika supplier SKU `484651` / seller SKU `6V-EEC1-2S9Z` as a unit item.

That is wrong because:
- the Amazon listing is sold as a pack of 3 bottles
- the supplier purchase item is a bottle, bought in supplier boxes
- the supplier cost may be per bottle, not per Amazon pack
- the buying decision has a special carton preference because the goods are hazmat and should not be mixed with normal products

Plain English version:
- The stock decider currently sees "167 units at GBP 1.45".
- For this Sika SKU, it should understand "167 Amazon packs means 501 bottles".
- If GBP 1.45 is the bottle cost, the Amazon pack cost is GBP 4.35 before profit is checked.
- If we choose the nice hazmat carton order, 250 Amazon packs means 750 bottles.

## 2. Confirmed Business Rules From Operator

### Standard products

Default rule:
- buy as needed
- no special carton rounding
- no hazmat-only PO grouping
- existing MOQ and normal supplier pack rules can still apply when known

### Sika 20g bottles

Applies to:
- supplier: Sika
- supplier SKU: `484651`
- known active seller SKU example: `6V-EEC1-2S9Z`
- Amazon sale shape: pack of 3 bottles

Purchase and handling rule:
- supplier box contains 25 bottles
- preferred order block is 250 Amazon packs
- 250 Amazon packs equals 750 bottles
- 750 bottles equals 30 supplier boxes of 25
- this fills the preferred 23kg hazmat box
- do not mix this purchase with normal products

### Sika 50g bottles

Applies to:
- supplier: Sika
- supplier SKU: `484652`
- known pack-of-3 active seller SKU example: `A2-T2AC-TW3L`

Purchase and handling rule:
- supplier box contains 20 bottles
- preferred order block is 120 Amazon packs
- 120 Amazon packs equals 360 bottles
- 360 bottles equals 18 supplier boxes of 20
- this fills the preferred 23kg hazmat box
- do not mix this purchase with normal products

Important confirmation needed before implementation:
- `PE-G94Y-4PYO` is titled as a 2-pack 50g listing, so it must not automatically receive the 3-pack Sika rule unless the operator confirms it.
- Do not apply this special carton treatment to every Sika SKU by supplier name alone. Apply it to approved seller SKU/profile rows only.

## 3. Proposed Storage Model

Use two layers. This keeps product truth separate from buying preference.

### Layer A - SKU quantity profile

This describes what one Amazon sale unit means.

Suggested fields:
- `seller_sku`
- `asin`
- `supplier_name`
- `supplier_sku`
- `profile_status`
- `component_unit_label`
- `components_per_sell_pack`
- `amazon_pack_size`
- `order_qty_mode`
- `supplier_cost_basis`
- `pack_profile_source`
- `pack_profile_note`

Example for Sika 20g pack of 3:
- `component_unit_label`: `bottle`
- `components_per_sell_pack`: `3`
- `amazon_pack_size`: `3`
- `order_qty_mode`: `sell_packs`
- `supplier_cost_basis`: `component_unit`

### Layer B - special buying profile

This describes how we prefer to buy it from the supplier.

Suggested fields:
- `profile_id`
- `supplier_name`
- `supplier_sku`
- `seller_sku`
- `quantity_strategy`
- `supplier_box_components`
- `preferred_order_sell_packs`
- `preferred_order_components`
- `preferred_supplier_boxes`
- `target_carton_weight_kg`
- `hazmat_group`
- `isolate_from_normal_po`
- `profile_status`
- `profile_note`

Example for Sika 20g:
- `quantity_strategy`: `preferred_carton_multiple`
- `supplier_box_components`: `25`
- `preferred_order_sell_packs`: `250`
- `preferred_order_components`: `750`
- `preferred_supplier_boxes`: `30`
- `target_carton_weight_kg`: `23`
- `hazmat_group`: `sika_glue`
- `isolate_from_normal_po`: `1`

Example for Sika 50g pack of 3:
- `quantity_strategy`: `preferred_carton_multiple`
- `supplier_box_components`: `20`
- `preferred_order_sell_packs`: `120`
- `preferred_order_components`: `360`
- `preferred_supplier_boxes`: `18`
- `target_carton_weight_kg`: `23`
- `hazmat_group`: `sika_glue`
- `isolate_from_normal_po`: `1`

Storage recommendation for v1:
- Add a local O-owned profile file first, such as `out/systems/O/live/sku_quantity_profiles.csv`.
- Add a local O-owned special buying file, such as `out/systems/O/live/special_order_profiles.csv`.
- Feed these into O source/recommendation/PO outputs.
- Once proven, promote stable profile fields into the Product DB edit/profile event path.

Reason:
- Product pack truth belongs with the SKU profile.
- The hazmat carton preference is operational buying policy, so it should not be hidden in a free-text note.
- Keeping this local and O-owned first avoids changing Google Sheets or canonical DB state before the behavior is proven.

## 4. Stock-Decider Logic

The stock decider must treat demand, cost, and supplier purchase quantity as separate but connected numbers.

For every restock row:
- Amazon stock and sales velocity stay in Amazon sellable units.
- For Sika pack-of-3 rows, one Amazon sellable unit equals 3 bottles.
- Supplier price-list cost must be converted to the same unit used for profit checking.

Cost conversion rule:
- If supplier cost basis is `sell_pack`, use the cost as-is.
- If supplier cost basis is `component_unit`, multiply by `components_per_sell_pack`.
- If supplier cost basis is `supplier_box`, divide by supplier box quantity, then multiply by `components_per_sell_pack`.

Quantity conversion rule:
- Start with recommended Amazon sellable quantity.
- Convert to component count using `recommended_sell_packs * components_per_sell_pack`.
- For standard products, keep current as-needed behavior.
- For Sika special carton products, round to the preferred carton block when the row is being turned into a purchase order.

Example, Sika 20g:
- suggested stock need: 167 Amazon packs
- components per sell pack: 3 bottles
- raw component need: 501 bottles
- preferred block: 250 Amazon packs = 750 bottles = 30 supplier boxes
- draft PO should show 250 Amazon packs / 750 bottles / 30 supplier boxes if the special carton rule is chosen

## 5. PO Output Changes

Purchase orders need to show both sale units and supplier buying units.

Add or carry these fields into PO line output:
- `ordered_sell_packs`
- `components_per_sell_pack`
- `ordered_components`
- `supplier_box_components`
- `ordered_supplier_boxes`
- `quantity_strategy`
- `hazmat_group`
- `isolate_from_normal_po`
- `target_carton_weight_kg`
- `pack_profile_status`

For normal products:
- `ordered_sell_packs` can equal the normal ordered quantity
- `ordered_components` can equal ordered quantity
- supplier box fields can stay blank or 1
- no special PO grouping is needed

For Sika:
- the supplier order view should be clear enough for a human to read:
  - "Buy 30 boxes of 25 bottles = 750 bottles = 250 Amazon packs of 3"

## 6. Readiness Blocks

Before a row can become action-ready, O should block if:
- pack profile is missing for a SKU known to need special treatment
- supplier cost basis is missing
- component-to-sell-pack conversion is invalid
- preferred carton math does not land exactly on full supplier boxes
- a SKU looks like a 2-pack but the saved profile says 3-pack
- Sika special profile is missing `hazmat_group` or `isolate_from_normal_po`

Suggested blocker codes:
- `missing_pack_profile`
- `unconfirmed_pack_profile`
- `missing_supplier_cost_basis`
- `invalid_component_conversion`
- `invalid_supplier_box_alignment`
- `special_order_profile_required`
- `pack_title_profile_mismatch`

## 7. Phased Build Plan

### Phase 1 - Data model and fixture

Goal:
- Add local O profile contracts and test fixtures.

Files likely touched:
- `scripts/flows/O/_schemas.py`
- new local profile fixture under `tests/fixtures/o_phase1/`
- O source contract tests

Proof:
- schema tests confirm profile files require the new columns
- no live data changed

### Phase 2 - Source view cost and pack conversion

Goal:
- Make `O001_build_restock_source_view.py` join SKU pack profile and special buying profile.
- Add sell-pack cost fields and component conversion fields.

Expected output fields:
- `components_per_sell_pack`
- `supplier_cost_basis`
- `expected_sell_pack_cost_gbp`
- `expected_component_cost_gbp`
- `quantity_strategy`
- `preferred_order_sell_packs`
- `preferred_order_components`
- `preferred_supplier_boxes`

Proof:
- Sika 20g converts component cost to sell-pack cost.
- Normal SKU remains unchanged.

### Phase 3 - Recommendation and readiness blocker

Goal:
- Make `O002` and `O020` block or round correctly.

Behavior:
- normal products remain as-needed
- Sika rows cannot become action-ready without confirmed profile
- Sika rows use the converted sell-pack cost for ROI and max purchase price

Proof:
- Sika with missing profile is blocked
- Sika with profile passes only if cost and carton math are valid
- normal product recommendation counts do not change unexpectedly

### Phase 4 - Purchase-order line conversion

Goal:
- Update `O100_build_purchase_orders.py` so supplier buying units are visible.

Proof:
- Sika 20g current example should no longer draft `167 units`.
- It should either:
  - block until the operator confirms the special carton order, or
  - draft a clear line for `250 packs / 750 bottles / 30 supplier boxes`

### Phase 5 - Small real-data proof

Goal:
- Rebuild the existing 6-line PO proof with pack-size gates active.

Success criteria:
- Sika 20g is no longer treated as one unit per Amazon pack.
- ROI uses the converted pack cost.
- PO line shows Amazon packs, bottles, supplier boxes, and hazmat separation.
- PE-G94Y-4PYO is not silently treated as a 3-pack.
- no Google Sheets write
- no supplier order placed

## 8. Tests To Add

Focused tests:
- Sika 20g pack-of-3 converts 250 packs to 750 bottles and 30 supplier boxes.
- Sika 50g pack-of-3 converts 120 packs to 360 bottles and 18 supplier boxes.
- supplier component cost is multiplied by 3 before ROI.
- standard product keeps current as-needed behavior.
- missing pack profile blocks action-ready status.
- 2-pack title with 3-pack profile blocks for review.

## 9. Current Decision Before Build

The operator should approve these assumptions before implementation:
- Sika 20g pack-of-3 rule applies to `6V-EEC1-2S9Z`.
- Sika 50g pack-of-3 rule applies to `A2-T2AC-TW3L`.
- `PE-G94Y-4PYO` should be reviewed separately because it appears to be a 2-pack listing.
- Supplier price-list cost for Sika is treated as per bottle unless proven otherwise.
- Preferred Sika PO output should round to the carton block, not the raw calculated need, when a real buying decision is made.

## 10. Implementation Status

Status at 2026-05-19T15:30:00Z:
- Phase 1 complete: O-owned `sku_quantity_profiles` and `special_order_profiles` contracts exist.
- Phase 2 complete: O001 joins confirmed profiles, converts component cost to sell-pack cost, and labels converted cost sources.
- Phase 3 complete: O002 now blocks unsafe pack profiles before a buy recommendation is created; O020 keeps the action-ready gate blocked for missing, unconfirmed, invalid, or mismatched pack profiles.
- Phase 4 complete: O100 now rounds confirmed special carton orders and holds approved decisions if the pack profile is missing, unconfirmed, invalid, or missing required carton fields.
- Phase 5 complete as isolated proof only: no Google Sheets write and no supplier order placed.

Verification:
- `python -m pytest tests/test_o001_restock_source_view.py tests/test_o002_restock_recommendations.py tests/test_o020_reorder_input_coverage.py tests/test_o100_build_purchase_orders.py -q`
- Result: 29 passed.
- `python -m pytest <all tests/test_o*.py> -q`
- Result: 158 passed.

Proof artifact:
- `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/pack_size_o_proof_20260519T154000Z/proof_summary.md`

Proof result:
- `6V-EEC1-2S9Z` has confirmed pack profile, 3 bottles per Amazon pack, sell-pack cost GBP 4.35, and PO output of 250 packs / 750 bottles / 30 supplier boxes.
- `PE-G94Y-4PYO` remains blocked with `missing_pack_profile` and `special_order_profile_required`.
- `SU-5LQH-2DVN` remains blocked with `missing_pack_profile` and `special_order_profile_required`, proving Sika/Everbuild glue multi-packs outside `484651`/`484652` do not fall through as normal products.
- `A2-T2AC-TW3L` has a confirmed pack profile but is still waiting for usable cost evidence before buying.

Live O refresh:
- Rollback snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_pack_profiles_20260519T155000Z`.
- Seeded live O-owned profile files:
  - `out/systems/O/live/sku_quantity_profiles.csv`
  - `out/systems/O/live/special_order_profiles.csv`
- Refreshed live O stock-decider outputs through O001, O002, O003, O004, and O020 only.
- Did not run live O100 purchase-order drafting, did not write Google Sheets, and did not place a supplier order.
- Live output rows after refresh:
  - source rows: 608
  - recommendation rows: 608
  - coverage rows: 608
  - action-ready rows: 6
- Live row check:
  - `6V-EEC1-2S9Z`: `confirmed`, 3 components, cost GBP 4.35, `full_restock`, action-ready 1.
  - `PE-G94Y-4PYO`: `missing_pack_profile`, `wait`, action-ready 0.
  - `A2-T2AC-TW3L`: `confirmed`, `wait` because usable cost evidence is still missing, action-ready 0.
  - `SU-5LQH-2DVN`: `missing_pack_profile`, `wait`, action-ready 0.
