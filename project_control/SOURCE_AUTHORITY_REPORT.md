# Source Authority Report

## SOURCE AUTHORITY CLASSIFICATION

### 1) Token ledger live dataset

- source path or name: `out/systems/B/live/token_ledger_live.csv`
- likely role: live B-owned token ledger used by token allocation, token COGS, H pricing floor inputs, and diagnostics
- likely authority category: canonical live
- writer scripts: `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/B/B024_build_tokens_november_anchor.py`, compat-aware writers via `scripts/core/out_paths.py`
- reader scripts: compat-aware readers inside `B007`, plus many direct readers that still target legacy `out/token_ledger_live.csv`
- risk note: `scripts/core/out_paths.py` maps this file to B-owned live storage, so the intent is clear, but many writers and readers still use the legacy path directly. `scripts/flows/B/B016_export_token_ledger_snapshot.py` explicitly says it is a sheet export "used to keep local snapshot in sync for tests", which makes the sheet-derived write non-canonical by intent.

### 2) Token ledger legacy mirror

- source path or name: `out/token_ledger_live.csv`
- likely role: backward-compatibility copy of the B token ledger
- likely authority category: mirror
- writer scripts: compat mirroring via `scripts/core/out_paths.py`; direct legacy-path writers include `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`, `scripts/flows/B/B010_apply_researching_delta.py`, `scripts/one_off/T002_B015_fix_duplicate_token_ids.py`, `scripts/one_off/T009_B031_backfill_tokens_from_orders_sheet.py`, `scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py`, `scripts/one_off/T028_backdate_tokens_from_live_stock.py`
- reader scripts: `scripts/cycles/run_H_pricing_cycle.py`, `scripts/h/h_floor_truth.py`, `scripts/flows/H/H110_run_phase1_h_pilot.py`, `scripts/flows/A/A015_build_system_health_check.py`, `scripts/flows/B/B010_build_token_ops_outputs.py`, `scripts/flows/B/B020_build_adjustment_partials_action.py`, `scripts/flows/B/B021_build_token_proof_pack.py`, `scripts/flows/B/B023_build_token_system_report.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, `scripts/tools/process_stock_receipts_sheet.py`, several one-off scripts
- risk note: most reads still hit this mirror directly, so in practice many scripts treat the mirror as canonical even though the path helper says otherwise.

### 3) Token allocations live dataset

- source path or name: `out/systems/B/live/token_allocations_live.csv`
- likely role: live B-owned allocation truth for token-to-order assignment
- likely authority category: canonical live
- writer scripts: `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/B/B024_build_tokens_november_anchor.py`, `scripts/flows/B/B030_sync_token_allocations_from_sheet.py`
- reader scripts: mostly legacy-path readers via `scripts/flows/B/B023_build_token_system_report.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, `scripts/flows/B/B021_build_token_proof_pack.py`, `scripts/one_off/T023_rebuild_level1_from_archive.py`
- risk note: `scripts/flows/B/B030_sync_token_allocations_from_sheet.py` explicitly says "Local CSV is the live source of truth." That is the strongest authority statement in this area. The problem is path split, not intent.

### 4) Token allocations legacy mirror

- source path or name: `out/token_allocations_live.csv`
- likely role: backward-compatibility copy of live allocations
- likely authority category: mirror
- writer scripts: compat mirroring via `scripts/core/out_paths.py`; direct legacy-path writers include `scripts/one_off/T002_B015_fix_duplicate_token_ids.py`, `scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py`, `scripts/one_off/T028_backdate_tokens_from_live_stock.py`
- reader scripts: `scripts/flows/B/B023_build_token_system_report.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, `scripts/flows/B/B021_build_token_proof_pack.py`, `scripts/one_off/T023_rebuild_level1_from_archive.py`
- risk note: same logical truth as the live B path, but many scripts still consume the mirror directly.

### 5) Product DB local dump

- source path or name: `out/product_db_preview.csv`
- likely role: local dump of the `Product_DB` Google Sheet for downstream use
- likely authority category: preview/debug
- writer scripts: `scripts/flows/A/A001_run_listings_to_sheet.py`, `scripts/flows/A/A002_run_catalog_items_to_sheet.py`, `scripts/flows/A/A003_run_inventory_to_sheet.py`, `scripts/flows/A/A004_run_fees_to_sheet.py`, `scripts/flows/B/B001_run_orders_to_sheet.py`, `scripts/flows/B/B002_run_pending_orders_to_sheet.py`, `scripts/flows/B/B003_run_financial_events_level3.py`
- reader scripts: `scripts/h/h_floor_truth.py`, `scripts/phase1/phase1_sku_scope.py`, `scripts/flows/H/H110_run_phase1_h_pilot.py`, `scripts/cycles/run_H_pricing_cycle.py`, `scripts/flows/H/H130_build_phase1_observation_sheet.py`, `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, `scripts/flows/D/D001_build_pnl_daily.py`, `scripts/flows/D/D015_enrich_fee_detail_ledger.py`, rebuild and scan one-offs
- risk note: the code repeatedly calls this a "preview", "dump", or "local copy". The likely canonical truth is the Google Sheet, not this CSV. Downstream scripts treating it as authoritative are reading a non-canonical convenience layer.

### 6) Inventory summaries local snapshot

- source path or name: `out/inventory_summaries.csv`
- likely role: local operational inventory snapshot used across B, D, E, and H
- likely authority category: derived operational
- writer scripts: `run_api_collection.py`, `scripts/api/get_inventory_summaries.py`, `scripts/flows/A/A003_run_inventory_to_sheet.py`
- reader scripts: `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/B/B010_apply_researching_delta.py`, `scripts/flows/D/D009_backdate_tokens_all.py`, `scripts/flows/E/E001_build_sales_velocity.py`, `scripts/flows/E/E003_build_restock_signals.py`, `scripts/phase1/phase1_phase_engine.py`, `scripts/flows/H/H110_run_phase1_h_pilot.py`, `scripts/one_off/H150_publish_pricing_dashboard.py`
- risk note: comments describe it as a saved CSV snapshot. It looks operationally canonical inside the repo, but not as a business source of truth. Write ownership is unclear because both `run_api_collection.py` and `A003` produce it.

### 7) Orders master input set

- source path or name: `out/orders_all.csv` and `out/order_items_all.csv`
- likely role: compiled local order history used as the primary local order base for B and D flows
- likely authority category: derived operational
- writer scripts: `scripts/flows/B/B001_run_orders_to_sheet.py`, `scripts/one_off/T019_D020_backfill_missing_orders_from_sellerboard.py`
- reader scripts: `scripts/flows/B/B002_run_pending_orders_to_sheet.py`, `scripts/flows/B/B003_run_financial_events_level3.py`, `scripts/flows/B/B004_build_order_master.py`, `scripts/flows/D/D008_build_settlement_order_scope_report.py`, `scripts/flows/D/D009_build_settlement_scoped_pnl.py`, archive rebuild one-offs
- risk note: `B002` explicitly calls these the "Primary source" for its flow, so they are locally authoritative for downstream processing. They are still derived from Amazon APIs and can be mutated by one-off backfill scripts, which weakens ownership clarity.

### 8) Order master

- source path or name: `out/order_master.csv`
- likely role: consolidated derived order truth for token, FX, and D-flow finance logic
- likely authority category: derived operational
- writer scripts: `scripts/flows/B/B004_build_order_master.py`, `scripts/one_off/T018_D014_fix_order_master_cogs_cancelled.py`
- reader scripts: `scripts/flows/B/B006_build_fx_ledgers.py`, `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/D/D019_build_missing_orders_vs_sellerboard.py`, multiple one-offs and diagnostics
- risk note: this is clearly derived from orders, items, level files, and token COGS. It is probably canonical for downstream finance in practice, but not root truth.

### 9) Inbound shipment contents

- source path or name: `out/inbound_shipment_contents.csv`
- likely role: local inbound shipment-to-SKU map used by C and D flows
- likely authority category: derived operational
- writer scripts: `scripts/flows/B/B030_run_inbound_shipment_contents_report.py`, `scripts/flows/B/B031_run_inbound_shipment_items.py`, `scripts/flows/C/C009_run_inbound_shipment_contents.py`
- reader scripts: `scripts/flows/C/C001_build_inbound_delivery_status.py`, `scripts/flows/C/C002_build_inbound_missing_units.py`, `scripts/flows/C/C006_build_token_maturity_window.py`, `scripts/flows/D/D004_allocate_transaction_expenses.py`
- risk note: ownership is unclear. `C009` is explicitly a wrapper/fallback around `B030`, which suggests `B030` is the intended primary writer. But `B031` independently writes the same file from a different API path, so there are multiple plausible canonical candidates.

### 10) FX rates cache

- source path or name: `out/fx_rates_daily.csv`
- likely role: locally persisted FX lookup table used for order and financial conversions
- likely authority category: cache
- writer scripts: `scripts/flows/B/B002_run_pending_orders_to_sheet.py`, `scripts/flows/B/B006_build_fx_ledgers.py`
- reader scripts: `scripts/flows/B/B001_run_orders_to_sheet.py`, `scripts/flows/B/B002_run_pending_orders_to_sheet.py`, `scripts/flows/B/B006_build_fx_ledgers.py`, `scripts/flows/E/E002_build_roi_snapshot.py`, `scripts/one_off/T023_rebuild_level1_from_archive.py`
- risk note: external FX APIs are the real authority. This CSV is just a shared cache, but it has two writers with different execution contexts.

### 11) Listing offer history live dataset

- source path or name: `out/systems/H/live/listing_offer_history.csv`
- likely role: H-owned live history of listing offer observations
- likely authority category: canonical live
- writer scripts: compat-aware history writes in `run_api_collection.py`; H-owned live-writer migration via `scripts/core/out_paths.py`
- reader scripts: readers should ideally use compat/live resolution, but most current readers still point at legacy `out/listing_offer_history.csv`
- risk note: `run_api_collection.py` reads the live file first when present, then legacy as fallback. That is a strong signal that the live H path is the intended canonical location.

### 12) Listing offer history legacy mirror

- source path or name: `out/listing_offer_history.csv`
- likely role: mirror for backward compatibility during H live-writer migration
- likely authority category: mirror
- writer scripts: mirrored by compat writes from `run_api_collection.py` and H helper utilities
- reader scripts: `scripts/flows/H/H002_build_phase1_seller_history.py`, `scripts/flows/H/H004_build_daily_market_snapshot.py`, `scripts/flows/E/E004_build_performance_summary.py`, `scripts/flows/A/A015_build_system_health_check.py`
- risk note: current readers mostly use the mirror directly, so they can bypass the intended live path.

### 13) H probe logs

- source path or name: `out/systems/H/live/h_worker_probe_event_log.csv` and `out/systems/H/live/h_worker_probe_response_log.csv`
- likely role: H-owned live probe logs
- likely authority category: canonical live
- writer scripts: `scripts/h/h_probe_logs.py`, `scripts/flows/H/H006_seed_worker_probe_logs.py`
- reader scripts: `scripts/h/h_probe_logs.py` and H monitoring helpers; health check still reads legacy path names
- risk note: these files are clearly live-path-first in `scripts/h/h_probe_logs.py`, but health and legacy tooling still point at `out/...`.

### 14) Listing snapshots and seller snapshots

- source path or name: `out/listing_offer_snapshot_YYYY-MM-DD.csv`, `out/listing_offer_seller_snapshot_YYYY-MM-DD.csv`, `out/inventory_snapshot_YYYY-MM-DD.csv`
- likely role: dated snapshots for observation, replay, and latest-file selection
- likely authority category: cache
- writer scripts: `run_api_collection.py`, `scripts/flows/H/H001_capture_offer_snapshot.py`
- reader scripts: several H flows, `scripts/flows/A/A018_build_phase1_floor_table.py`, `scripts/one_off/H150_publish_pricing_dashboard.py`
- risk note: these are explicitly snapshots and are selected with "latest file" logic in several places. They should not be treated as canonical truth.

### 15) Phase1 runtime floor snapshot

- source path or name: `out/phase1_runtime_floor_snapshot_latest.csv`
- likely role: most recent H runtime floor output used for observation and dashboard publishing
- likely authority category: derived operational
- writer scripts: `scripts/flows/H/H110_run_phase1_h_pilot.py`
- reader scripts: `scripts/flows/H/H130_build_phase1_observation_sheet.py`, `scripts/one_off/H150_publish_pricing_dashboard.py`, H cycle orchestration
- risk note: likely canonical within the H floor-runtime layer, but still derived from Product DB preview, token ledger, inventory, and offer snapshots.

## DUPLICATE-TRUTH GROUPS

### Token ledger

- logical dataset name: token ledger live
- all file/path variants involved: `out/systems/B/live/token_ledger_live.csv`, `out/token_ledger_live.csv`, Token_Ledger Google Sheet
- likely canonical candidate: `out/systems/B/live/token_ledger_live.csv`
- why the group is risky: one script (`B016`) treats the sheet as a test-sync source, while other scripts write the local CSV directly. Readers mostly consume the legacy mirror, not the declared live path.

### Token allocations

- logical dataset name: token allocations live
- all file/path variants involved: `out/systems/B/live/token_allocations_live.csv`, `out/token_allocations_live.csv`, Token_Allocations Google Sheet
- likely canonical candidate: `out/systems/B/live/token_allocations_live.csv`
- why the group is risky: `B030_sync_token_allocations_from_sheet.py` says the local CSV is authoritative, but many scripts still read the legacy mirror and some one-offs still write directly to it.

### Product DB

- logical dataset name: product database
- all file/path variants involved: Product_DB Google Sheet, `out/product_db_preview.csv`
- likely canonical candidate: Product_DB Google Sheet
- why the group is risky: the local file is repeatedly labeled "preview", "dump", or "local copy", yet many downstream calculations treat it like live truth.

### Listing offer history

- logical dataset name: listing offer history
- all file/path variants involved: `out/systems/H/live/listing_offer_history.csv`, `out/listing_offer_history.csv`
- likely canonical candidate: `out/systems/H/live/listing_offer_history.csv`
- why the group is risky: compat migration says H live path is owned, but most readers still point to the legacy mirror.

### H probe logs

- logical dataset name: H worker probe logs
- all file/path variants involved: `out/systems/H/live/h_worker_probe_event_log.csv`, `out/h_worker_probe_event_log.csv`, `out/systems/H/live/h_worker_probe_response_log.csv`, `out/h_worker_probe_response_log.csv`
- likely canonical candidate: the `out/systems/H/live/...` files
- why the group is risky: `h_probe_logs.py` writes live-first and mirrors conditionally, but A health tooling reads the legacy paths.

### Inbound shipment contents

- logical dataset name: inbound shipment contents
- all file/path variants involved: `out/inbound_shipment_contents.csv`, `out/inbound_shipment_contents_raw.csv`
- likely canonical candidate: unresolved between `B030` output and `B031` output; `C009` appears to be fallback only
- why the group is risky: the same final file can be generated from three different logic paths, two of which use different Amazon APIs and one of which reconstructs from inventory ledger receipts.

### Inventory summaries

- logical dataset name: current inventory summary
- all file/path variants involved: SP-API inventory endpoint, `out/inventory_summaries.csv`, `out/inventory_snapshot_YYYY-MM-DD.csv`
- likely canonical candidate: `out/inventory_summaries.csv` for local runtime, SP-API upstream for root truth
- why the group is risky: there are multiple local representations of the same inventory state and more than one writer for the non-dated summary file.

## NON-CANONICAL READ RISKS

- `scripts/cycles/run_H_pricing_cycle.py` reads `out/token_ledger_live.csv` directly instead of the B live path.
- `scripts/h/h_floor_truth.py` reads `out/token_ledger_live.csv` directly instead of the B live path.
- `scripts/flows/H/H110_run_phase1_h_pilot.py` reads `out/token_ledger_live.csv` and `out/product_db_preview.csv`, both of which are non-canonical relative to their likely owning sources.
- `scripts/flows/A/A015_build_system_health_check.py` reads `out/token_ledger_live.csv`, `out/h_worker_probe_event_log.csv`, `out/h_worker_probe_response_log.csv`, and `out/listing_offer_history.csv` from legacy paths even though H/B live paths exist for some of them.
- `scripts/flows/H/H002_build_phase1_seller_history.py`, `scripts/flows/H/H004_build_daily_market_snapshot.py`, and `scripts/flows/E/E004_build_performance_summary.py` read `out/listing_offer_history.csv` directly instead of resolving the H live path.
- `scripts/flows/B/B023_build_token_system_report.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, and `scripts/flows/B/B021_build_token_proof_pack.py` read legacy `out/token_ledger_live.csv` and/or `out/token_allocations_live.csv` rather than the B live paths.
- Many B, D, H, and one-off scripts read `out/product_db_preview.csv`, which appears to be a non-canonical preview of the Product_DB sheet.
- `scripts/flows/C/C001_build_inbound_delivery_status.py`, `scripts/flows/C/C002_build_inbound_missing_units.py`, `scripts/flows/C/C006_build_token_maturity_window.py`, and `scripts/flows/D/D004_allocate_transaction_expenses.py` all read `out/inbound_shipment_contents.csv` even though writer ownership for that file is not clearly singular.

## Escalation notes

- Canonical ownership is still ambiguous for `out/inbound_shipment_contents.csv`. `B030` looks like the intended primary writer, `C009` is fallback, and `B031` is an alternate full writer. Choosing one as canonical would be a product/architecture decision.
- `out/inventory_summaries.csv` behaves like the local operational authority, but ownership is split between API collection and A flow. That should be resolved before rewiring.
- `out/orders_all.csv` and `out/order_items_all.csv` are treated as primary local inputs downstream, but one-off appenders mean write ownership is not fully clean.

## Files created

- `project_control/SOURCE_AUTHORITY_REPORT.md`
