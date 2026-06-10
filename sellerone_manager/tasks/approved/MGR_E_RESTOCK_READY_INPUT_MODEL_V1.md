# E Restock Ready Input Model v1

## Manager Authority
- task_id: MGR_E_RESTOCK_READY_INPUT_MODEL_V1
- job_ref: E-RESTOCK-READY-MODEL
- flow: E
- task_type: build_gap
- priority: high
- status: proved
- authority: luke_requested_build_list
- luke_action_required: 0

## Plain-English Purpose
Define exactly what E needs before it can call a SKU business-ready for restocking.

E should still show stock pressure, but it must not make low stock look like a clean buy signal.

## Boundary
- allowed_scope: E restock readiness field design, E confidence labels, E/O handoff contract, manager proof mapping, and focused E tests.
- forbidden_actions: no purchase decision; no PO creation; no E live run without approved proof window; no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no output deletion; no fake ROI fill; no worker restart; no scope widening into O implementation without a separate packet.
- proof_required: E must separate `stock_signal` from `restock_business_ready`, and every blocked row must say what proof is missing.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Use git diff for code rollback. Do not edit business outputs by hand.
- stop_condition: Stop if the work becomes an ordering decision or needs a protected action.

## Expected Build Output
- Clear fields for:
  - stock pressure
  - profit confidence
  - refund confidence
  - B money confidence
  - current price confidence
  - final restock readiness state
  - missing proof

## Acceptance Proof
- A SKU with stock pressure but missing ROI is not business-ready.
- A SKU with ROI but bridge-only B money proof stays warning-labelled.
- O can read the final state as evidence, not an instruction to buy.
