# Canonical Enforcement Plan

## CANONICAL ENFORCEMENT PLAN

This plan is based on:

- `project_control/DATA_LINEAGE_REPORT.md`
- `project_control/SOURCE_AUTHORITY_REPORT.md`
- `scripts/core/out_paths.py`
- spot checks of the highest-risk reader and writer scripts

Key planning assumption:

- For B/H live-writer datasets already declared in `scripts/core/out_paths.py`, the `out/systems/<owner>/live/...` path is the intended canonical live location.
- For `out/product_db_preview.csv`, the Google Sheet is the likely canonical truth and the CSV is not.
- For `out/inbound_shipment_contents.csv`, canonical ownership is still unresolved.

## PHASE 1 - SAFE ENFORCEMENT TASKS

### Task 1: Enforce compat-path reads for B live token files

- task title: Move token ledger and token allocation reads onto compat resolution
- objective: Make all runtime readers resolve `token_ledger_live.csv` and `token_allocations_live.csv` through `scripts/core/out_paths.py` instead of hardcoding legacy `out/...`
- why safe now: canonical intent is already declared in `LIVE_WRITER_COMPAT_MAP`, and current writers already support mirrored output
- likely files/scripts affected: `scripts/cycles/run_H_pricing_cycle.py`, `scripts/h/h_floor_truth.py`, `scripts/flows/H/H110_run_phase1_h_pilot.py`, `scripts/flows/A/A015_build_system_health_check.py`, `scripts/flows/B/B021_build_token_proof_pack.py`, `scripts/flows/B/B023_build_token_system_report.py`, `scripts/flows/B/B025_build_token_cogs_ledger.py`, `scripts/tools/process_stock_receipts_sheet.py`, relevant one-offs
- expected risk reduction: removes silent divergence between live and legacy B token paths and makes future B live-writer migration real instead of nominal

### Task 2: Enforce compat-path reads for H live mirrored files

- task title: Move listing history and H probe log reads onto compat resolution
- objective: Make readers of `listing_offer_history.csv`, `h_worker_probe_event_log.csv`, and `h_worker_probe_response_log.csv` use canonical H live paths first
- why safe now: `out_paths.py` already declares these files as H-owned live datasets, and H helper code already writes/reads live-first
- likely files/scripts affected: `scripts/flows/A/A015_build_system_health_check.py`, `scripts/flows/H/H002_build_phase1_seller_history.py`, `scripts/flows/H/H004_build_daily_market_snapshot.py`, `scripts/flows/E/E004_build_performance_summary.py`, any H analysis utilities still using `out/...`
- expected risk reduction: removes a second live-vs-legacy split and makes H observability/history reads consistent with writer intent

### Task 3: Demote test-only sheet snapshot writers from runtime authority

- task title: Mark sheet-export snapshots as non-authoritative and keep them out of runtime decisions
- objective: Keep scripts like `B016_export_token_ledger_snapshot.py` and Product_DB dump helpers from being treated as live authority producers
- why safe now: the repo already documents `B016` as test sync and repeatedly labels Product_DB CSV as preview/local copy
- likely files/scripts affected: `scripts/flows/B/B016_export_token_ledger_snapshot.py`, references to this flow in cycle docs or control docs, any runtime readers that assume the sheet export refresh is authoritative
- expected risk reduction: lowers the risk of engineers using convenience exports as the reason a runtime file should stay on a legacy path

### Task 4: Replace preview-file reads where a canonical local live file already exists

- task title: Remove runtime dependence on preview or mirror files when a canonical local runtime file is available
- objective: prioritize rewiring runtime logic away from `out/product_db_preview.csv` where a stable local canonical substitute exists, and away from legacy mirrors where compat live exists
- why safe now: for mirror-path cases the canonical replacement already exists; for preview cases, safe work is limited to cataloging and blocking new usage before changing behavior
- likely files/scripts affected: immediate mirror cases in B/H readers; planning hooks in H and B flows that currently read preview plus canonical local token data together
- expected risk reduction: stops expansion of non-canonical reads and narrows the next implementation phase to true behavior changes only

### Task 5: Add detection checks for non-canonical runtime reads

- task title: Add static or contract checks that fail on hardcoded non-canonical reads for already-declared live files
- objective: prevent reintroduction of `out/token_ledger_live.csv`, `out/token_allocations_live.csv`, `out/listing_offer_history.csv`, and legacy H probe log paths in runtime code
- why safe now: this is enforcement around already declared path ownership, not a business logic change
- likely files/scripts affected: `scripts/tests/`, `scripts/core/`, and any flow-owned test profile for B/H
- expected risk reduction: prevents rollback into stale-path reads after the rewires land

## PHASE 2 - DECISION-REQUIRED TASKS

### Task 1: Resolve canonical ownership for inbound shipment contents

- task title: Pick the single canonical writer for inbound shipment contents
- unresolved issue: `B030`, `B031`, and fallback wrapper `C009` all produce `out/inbound_shipment_contents.csv`
- decision needed: which acquisition path is the official runtime truth for inbound shipment contents
- candidate options if visible from repo:
- `B030_run_inbound_shipment_contents_report.py` as canonical because `C009` explicitly wraps/falls back to it
- `B031_run_inbound_shipment_items.py` as canonical if the direct inbound items API is preferred over reports API
- retain `C009` only as fallback or recovery path, never as peer canonical writer

### Task 2: Resolve ownership for `out/inventory_summaries.csv`

- task title: Choose the single owner of the operational inventory summary file
- unresolved issue: `run_api_collection.py`, `scripts/api/get_inventory_summaries.py`, and `A003_run_inventory_to_sheet.py` all participate in producing `out/inventory_summaries.csv`
- decision needed: whether A flow or API collection owns the current runtime summary file
- candidate options if visible from repo:
- A flow owns `out/inventory_summaries.csv` and API collection only writes dated snapshots/history
- API collection owns `out/inventory_summaries.csv` and A003 becomes a consumer/publisher only
- split by purpose, but only if filenames are made distinct enough to remove hidden overlap

### Task 3: Resolve ownership for `out/orders_all.csv` and `out/order_items_all.csv`

- task title: Decide whether one-off order backfill scripts may continue writing compiled order bases
- unresolved issue: downstream B flows treat these files as primary local source, but `T019` also appends to them
- decision needed: whether one-off repair/backfill scripts may write the same compiled operational files as daily B flows
- candidate options if visible from repo:
- B001 remains sole canonical writer and one-offs write staged/reconciliation outputs only
- one-offs may append, but only through a shared canonical writer helper
- separate "repair import" files are introduced later and merged by the canonical flow

### Task 4: Resolve runtime policy for Product DB usage

- task title: Decide how runtime logic should obtain Product DB truth
- unresolved issue: many runtime scripts use `out/product_db_preview.csv`, but the report classifies it as preview/local copy of a sheet
- decision needed: whether runtime should continue to depend on a sheet-derived local dump, or whether a distinct canonical local product dataset is required
- candidate options if visible from repo:
- continue using the sheet as canonical and formalize `out/product_db_preview.csv` as a controlled cache with freshness checks
- create a separate canonical local product dataset later and demote preview usage completely
- limit Product_DB preview usage to observation/reporting only and move core runtime decisions elsewhere

### Task 5: Resolve H use of `data/...` versus `out/...`

- task title: Clarify authority split between H data files and H out files
- unresolved issue: H phase1 combines `data/offer_snapshot_facts.csv`, `data/sku_daily_intel.csv`, `data/execution_log.csv`, and multiple `out/phase1_*`/snapshot files
- decision needed: which directory family is canonical for runtime H decisions versus reporting history
- candidate options if visible from repo:
- `out/...` is runtime and `data/...` is historical/supporting only
- `data/...` holds canonical truth inputs and `out/...` is purely derived
- mixed ownership, but only with explicit per-file authority rules documented in control docs

## PHASE 3 - PREVENTION / GUARDRAIL TASKS

### Task 1: Ban direct legacy-path reads for compat-mapped live files

- rule to enforce: any runtime script reading a file listed in `LIVE_WRITER_COMPAT_MAP` must resolve it through `resolve_compat_path()` or a single approved wrapper
- where it should live: `project_control/GUARDRAILS.md`, plus test enforcement under `scripts/tests/`
- what future mistake it prevents: adding new readers that bypass the canonical live path and reintroduce live-vs-legacy drift

### Task 2: Ban runtime reads from `*_preview.csv` unless explicitly approved

- rule to enforce: preview files are not allowed as runtime inputs unless the file is explicitly classified as canonical cache in project control
- where it should live: `project_control/GUARDRAILS.md`
- what future mistake it prevents: convenience sheet dumps becoming hidden sources of truth

### Task 3: Require single-owner declaration for every operational file

- rule to enforce: every operational CSV/JSON used by a cycle must have one named owning writer flow; any additional writer must be labeled fallback, test-only, or one-off recovery
- where it should live: `project_control/GUARDRAILS.md` and later `ARCHITECTURE.md`
- what future mistake it prevents: multi-writer files like `inbound_shipment_contents.csv` and `inventory_summaries.csv`

### Task 4: Require flow-owned read profiles

- rule to enforce: each flow test profile must include a check that its runtime reads come only from allowed authority categories for that flow
- where it should live: `project_control/GUARDRAILS.md` and `scripts/tests/`
- what future mistake it prevents: a flow quietly depending on preview, mirror, or fallback artifacts from another flow

### Task 5: Require explicit fallback labeling in code and docs

- rule to enforce: any fallback path or wrapper writer must say "fallback" in code comments/docstrings and must not write the same final file as a peer canonical writer without a documented decision
- where it should live: `project_control/GUARDRAILS.md`
- what future mistake it prevents: wrappers like `C009` being mistaken for canonical peers

### Task 6: Add non-canonical read inventory to health or contract checks

- rule to enforce: maintain a checked list of banned non-canonical reads for the known high-risk files
- where it should live: later in flow-scoped tests, and summarized in `project_control/GUARDRAILS.md`
- what future mistake it prevents: regressions after cleanup where old legacy-path reads are reintroduced

## PRIORITY ORDER

- 1. Enforce compat-path reads for B token ledger and token allocations first. This is the largest stale-risk area and the canonical intent is already explicit.
- 2. Enforce compat-path reads for H listing history and probe logs second. The same live/mirror pattern exists and is similarly safe to fix.
- 3. Add guardrail tests for compat-mapped live files immediately after the first two rewires. That locks the safe gains in place.
- 4. Resolve `inbound_shipment_contents.csv` ownership before changing any C/D readers there. Writer ambiguity is still real.
- 5. Resolve `inventory_summaries.csv` ownership next. Too many runtime flows depend on it to safely rewire before ownership is explicit.
- 6. Resolve `orders_all.csv` and `order_items_all.csv` write policy after inventory. They are important, but current downstream usage is clearer than the writer policy.
- 7. Resolve Product DB runtime policy after the file-owner decisions above. It likely needs a product/architecture choice, not just a path rewrite.
- 8. Clarify H `data/...` versus `out/...` authority last. It matters, but it is broader and more architectural than the earlier high-value cleanup steps.

## FILES CREATED

- `project_control/CANONICAL_ENFORCEMENT_PLAN.md`
