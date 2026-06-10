# O Profit Input Blocker Breakdown v1

## Manager Authority
- task_id: MGR_O_PROFIT_INPUT_BLOCKER_BREAKDOWN_V1
- job_ref: O-PROFIT-INPUT-BLOCKERS
- flow: O
- task_type: manager_read_only_proof
- priority: high
- status: proved
- authority: o_cycle_sub_manager_from_mot_o_refund_restock_confidence_fields_remaining_warn
- luke_action_required: 0

## Plain-English Purpose
O still has a profit-input warning because some rows look close enough to review, but the expected profit is not clean yet.

This job is to show exactly which rows are blocked, why they are blocked, and what the next safe action is. It must not guess inbound/FBA cost, use weak values as clean profit, or move any row toward buying.

## Boundary
- allowed_scope: read-only O profit-input blocker breakdown, O schema contract, local O proof builder, Restock Session display, O manager/MOT proof wording, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite; no guessed inbound/FBA cost allocation.
- proof_required: the blocker breakdown must identify the weak-profit rows, separate refund-ok from inbound-missing proof, keep every affected row blocked from clean buy, and retest O MOT with 0 failures.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. A pre-refresh snapshot should be kept under O history before live proof refresh.
- stop_condition: Stop if clearing the warning requires guessing cost, choosing a different source of inbound/FBA cost truth, fetching new Amazon data, writing Sheets, changing queues/prices, creating POs, receiving stock, sending to Amazon, or pretending missing profit proof is clean.

## Source Evidence
- MOT check: `o_refund_restock_confidence_fields`
- Current MOT state: `warn`
- Current proof clue: `minimum_input_rows_with_weak_profit_inputs=8;refund=0;inbound=8;profit=8`
- Related MOT check: `o_inbound_fba_cost_allocation_proof`
- Related proof clue: `safe_rows=0;missing_rows=608;event_rows=51;event_linked_rows=0;sku_cost_rows=0`

## Allowed Files
- `scripts/flows/O/O023_build_profit_input_blocker_breakdown.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- focused O/MOT tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- A read-only O output lists the weak-profit rows and the exact blocker reason.
- The output shows refund proof is not the current issue for the 8 minimum-input rows.
- The output shows inbound/FBA SKU-level cost proof is the current issue for those rows.
- Restock Session can show the blocker breakdown without writing any events.
- O MOT keeps 0 failures and keeps real PO readiness closed.
- O buy-ready rows remain 0 unless all required proof is actually safe.

## Expected End State
Luke can see why O is still blocking profit-ready restocking without being asked to supply data unless the system cannot prove a supplier/cost source or Luke chooses a new protected inbound-cost proof source.
