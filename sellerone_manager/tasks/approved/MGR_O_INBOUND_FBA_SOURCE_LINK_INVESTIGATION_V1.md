# O Inbound FBA Source Link Investigation v1

## Manager Authority
- task_id: MGR_O_INBOUND_FBA_SOURCE_LINK_INVESTIGATION_V1
- job_ref: O-INBOUND-FBA-SOURCE-LINK
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: o_cycle_sub_manager_from_o_inbound_fba_cost_allocation_proof
- luke_action_required: 0

## Plain-English Purpose
O now proves that inbound/FBA cost rows exist, but they are not linked to shipments or SKUs.

This job is to inspect the upstream local finance/inbound evidence and work out whether the missing shipment link is a parser gap, a source-data gap, or an expected Amazon limitation. If a parser gap is clear, Codex may prepare a bounded local repair. If the source data itself has no shipment link, O must keep the cost blocked and explain the missing proof instead of guessing.

## Boundary
- allowed_scope: inspect existing local financial event outputs, transaction expense outputs, inbound shipment files, B/C/D parser code, O inbound-cost proof map, focused tests, manager/MOT wording, and local proof-only diagnostics.
- forbidden_actions: no Amazon API fetch; no B run; no C publish; no live worker cycle; no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no guessing unlinked fees into SKU costs.
- proof_required: existing local source files must be inspected, the reason for missing shipment/SKU links must be classified, any code change must have focused tests, and O must still keep rows blocked unless real SKU-level cost proof exists.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O, B, C, or D outputs.
- stop_condition: Stop if proving the link requires a live Amazon fetch, B/C live run, Sheet write, DB alignment, protected business action, or estimating cost allocation without real source linkage.

## Source Evidence
- Current proof file: `out/systems/O/live/restock_inbound_fba_cost_proof_live.csv`
- Current proof clue: 32 inbound cost events, 0 shipment-linked events, 0 SKU-level cost rows, and 608 O restock rows missing SKU-level inbound/FBA cost proof.
- Current MOT check: `o_inbound_fba_cost_allocation_proof`

## Allowed Files
- `scripts/flows/O/O022_build_inbound_fba_cost_proof.py`
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `scripts/flows/B/B005_run_financial_transactions_v2024.py`
- `scripts/flows/C/C003_build_inbound_cost_events.py`
- `scripts/flows/C/C004_build_inbound_cost_allocations.py`
- `scripts/flows/C/C005_allocate_inbound_costs_to_sku.py`
- `scripts/flows/D/D004_allocate_transaction_expenses.py`
- focused O/B/C/D/MOT tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- The upstream reason is classified as parser gap, source-data gap, or expected unlinked-fee limitation.
- If the raw local source has shipment IDs that the parser missed, focused tests prove the parser captures them.
- If the raw local source has no shipment IDs, O keeps the cost warning and does not allocate by guesswork.
- O MOT retest keeps 0 fails and keeps any true inbound/FBA cost warning visible.
- No protected action is performed.

## Expected End State
The Manager Task Board shows the next real path to clearing inbound/FBA cost proof: either fix a local parser gap or confirm that Luke needs a different approved proof source later.
