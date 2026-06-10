# F Price List Process Manager v1 - Project Brief

Date: 2026-04-30
Owner: Codex planning task

## Purpose
Build a management layer that decides which supplier price list should be prepared and scanned next.

The manager sits upstream of the current F061 scanner. It must not replace, auto-start, or interrupt the live scanner until a separate safe handoff rule is built and proven.

## Plain-English Target
The system should be able to answer:
- Which suppliers do we track?
- How do we get each supplier price file?
- When was the latest price file received or downloaded?
- Has that exact file or those exact rows already been scanned?
- Which rows are worth scanning now?
- Which rows should wait because the same barcode recently failed for a reason that is unlikely to change?
- Which batch should be recommended next?
- Is F061 busy, and is it safe to hand anything over?

## First Build Target
Build a test-mode process manager with fake scanner results before touching live F061 handoff.

The first test should:
- create sample supplier price-list batches
- create 10 fake barcode scan outcomes
- show batch state movement from received to converted to scan-ready to result-recorded
- update barcode cooldown memory
- prove counts reconcile at every step
- produce the next recommended action without writing to live scanner files

## Non-Goals For v1
- Do not change Google Sheets.
- Do not change the local DB to match Sheets.
- Do not auto-start F061.
- Do not replace the active F061 queue while a scan is running.
- Do not mix suppliers in one active scanner batch unless a later handoff contract explicitly allows it.
- Do not build advanced learning before the simple batch queue and cooldown rules work.

## Boundary
This manager belongs between Supplier Discovery price-list acquisition and the F feeder scanner.

Upstream:
- manual supplier requests
- emailed price lists
- API or URL downloads
- local file imports

Downstream:
- supplier-specific conversion into the universal F price-list format
- F061 scanner execution
- feeder pass, near-miss, fail, review, and approval outputs

## Source Documents Reviewed
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/SUPPLIER_DISCOVERY_PLAN.md`
- `project_control/FEEDER_CYCLE_PLAN.md`
- `project_control/EXPECTATIONS/supplier_discovery_expectations.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `project_control/F_SCREENING_PIPELINE_SIMPLIFICATION_BLUEPRINT_2026-04-13.md`
- `scripts/flows/F/F005_build_supplier_price_list_universal.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_schemas.py`

## Definition Of This Planning Task Done
- Active plan folder exists.
- The queue architecture is written down.
- The fake 10-result proof path is written down.
- The cooldown policy starts simple and leaves room for later dynamic history rules.
- The live scanner boundary is explicit.
- The next move is clear.
