# O Inbound FBA Source Options Review v1

## Manager Authority
- task_id: MGR_O_INBOUND_FBA_SOURCE_OPTIONS_REVIEW_V1
- job_ref: O-INBOUND-FBA-SOURCE-OPTIONS
- flow: O
- task_type: manager_read_only_proof
- priority: high
- status: proved
- authority: o_cycle_sub_manager_from_o_profit_input_blocker_breakdown
- luke_action_required: 0

## Plain-English Purpose
O now shows 8 rows where refund proof is okay but inbound/FBA cost proof is still missing.

This job is to inspect existing local files and classify every possible inbound/FBA cost proof route as safe, missing, blocked, or protected. It must not guess costs or choose a business policy.

## Boundary
- allowed_scope: read-only local inbound/FBA source-route review, O schema contract, local O proof builder, Restock Session maintenance display, O manager/MOT proof wording, focused tests, and active O plan notes.
- forbidden_actions: no Amazon API fetch; no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no source fact rewrite; no estimated/averaged inbound cost policy without Luke.
- proof_required: output must classify whether a safe direct route exists from current local files; if not, it must keep O blocked and clearly label any estimate/fetch/policy route as protected.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if clearing the inbound/FBA blocker requires a protected policy choice, live Amazon fetch, source rewrite, cost estimate, PO, receiving, send-to-Amazon, Sheet write, queue/price change, DB alignment, or output deletion.

## Source Evidence
- MOT check: `o_inbound_fba_cost_allocation_proof`
- Current MOT state: `warn`
- Current proof clue: `safe_rows=0;missing_rows=608;event_rows=51;event_linked_rows=0;sku_cost_rows=0`
- Related O023 proof: 8 minimum-input rows are blocked by `inbound_fba_cost_missing`.

## Allowed Files
- `scripts/flows/O/O024_build_inbound_fba_source_options.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- focused O/MOT tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- A read-only O output lists the possible inbound/FBA cost source routes.
- Direct safe routes are marked safe only when shipment/SKU proof exists.
- Estimate, average-cost, live-fetch, or policy routes are marked protected, not automatic.
- O MOT keeps 0 failures and keeps buying/PO closed.
- If no direct safe route exists, the board shows the gap as parked/protected rather than pretending O can complete profit proof.

## Expected End State
O can explain whether Codex can continue fixing inbound/FBA cost proof locally, or whether Luke must choose a protected cost-proof policy before real restocking can move further.
