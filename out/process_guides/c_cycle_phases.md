# C Cycle Phases Tracker

Use this file to track progress. Add notes under each phase as you go.

## Phase 0 - Preconditions
- Goal: A015 FAIL = 0 before any C work.
- Status: completed
- Notes:

## Phase 1 - Contracts and tests only
- Goal: schema contracts for inputs/outputs, C015 checks, no sheet writes.
- Status: completed
- Notes:

## Phase 2 - C001 and C002 (shipments + missing units)
- Goal: shipment status and missing units detector with CLOSED + 14 day guardrail.
- Status: completed
- Notes:

## Phase 3 - C003 and C004 (costs and linkage)
- Goal: cost events link only when shipmentId exists, otherwise unallocated.
- Status: completed
- Notes:
  - C003 output: out/inbound_cost_events.csv
  - C004 outputs: out/inbound_costs_allocated.csv, out/inbound_costs_unallocated.csv

## Phase 4 - C005 (allocation to SKU)
- Goal: allocate shipment-level costs down to SKUs with sum-to-total guardrails.
- Status: completed
- Notes:
  - C005 outputs: out/inbound_costs_allocated_sku.csv, out/inbound_costs_unallocated_sku.csv, out/inbound_costs_allocation_summary.csv

## Phase 5 - C006 (token maturity window)
- Goal: build in-flight buffer dataset for token tests.
- Status: completed
- Notes:
  - C006 outputs: out/token_maturity_window.csv, out/token_maturity_window_sku.csv

## Phase 6 - Staged publish and scheduling
- Goal: local outputs first, publish only if C015 passes, run lock, daily schedule.
- Status: completed
- Notes:
  - Run script: scripts/run_C_cycle.py
  - Publish stub: scripts/C010_publish_c_outputs.py (no sheet writes unless enabled)
  - Storage fee pull: scripts/C007_run_storage_fee_report.py (monthly, after the 10th)
