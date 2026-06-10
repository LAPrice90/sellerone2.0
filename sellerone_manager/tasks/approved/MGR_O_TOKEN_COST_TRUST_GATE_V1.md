# O Token Cost Trust Gate v1

## Manager Authority
- task_id: MGR_O_TOKEN_COST_TRUST_GATE_V1
- job_ref: O-TOKEN-COST-TRUST-GATE
- flow: O
- task_type: manager_read_only_guard
- status: proved
- authority: manager_approved_safe_proof
- priority: high
- luke_action_required: 0

## Plain English
O must not treat affected SKUs as reorder-ready while the token-cost source is suspect. Reordering can still be reviewed manually, but the system must show that profit proof is not clean.

## Current Evidence Summary
- B token-cost mismatch can affect O profit and reorder confidence.
- Fallback tokens differing from latest prior Sheet cost: 1473.
- Available wrong-cost fallback tokens: 1096.
- Already allocated wrong-cost fallback tokens: 377.
- Main affected SKUs:
  - `6V-EEC1-2S9Z`
  - `A2-T2AC-TW3L`
- Read-only comparison output:
  - `out/systems/M/b_token_sheet_comparison/summary.md`

## Allowed Work
- inspect O restock proof outputs and profit-input confidence fields
- add or extend read-only O/MOT proof so affected SKUs are blocked from action-ready status when B fallback-cost risk is active
- add focused O/MOT tests
- keep user-facing wording simple: token cost not trusted yet

## Forbidden Work
- no purchase order creation
- no receiving action
- no send-to-Amazon action
- no price change
- no queue edit
- no Google Sheets write
- no local DB alignment
- no output deletion
- no token correction
- no business decision

## Acceptance Proof
- O can identify SKUs affected by B fallback-cost risk.
- Affected SKUs cannot become action-ready purely from stale or unproved token-cost evidence.
- O still allows manual review wording without claiming automation-ready profit proof.
- O distinguishes "manual review allowed" from "system says this is clean to reorder".

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O

## Stop Condition
Stop before any buying, receiving, live PO, token, price, queue, Sheet, DB, or output mutation.

