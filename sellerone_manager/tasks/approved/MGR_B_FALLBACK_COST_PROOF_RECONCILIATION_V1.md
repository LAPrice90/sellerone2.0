# B Fallback Cost Proof Reconciliation v1

## Manager Authority
- task_id: MGR_B_FALLBACK_COST_PROOF_RECONCILIATION_V1
- job_ref: B-FALLBACK-PROOF-RECONCILE
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: manager_approved_safe_proof
- priority: high
- luke_action_required: 0

## Plain English
Two proof sources now disagree. B070 says fallback token costs are proved, but the Sheet comparison says 1473 fallback tokens differ from the latest prior Sheet cost. This job decides which proof rule is correct before any downstream system trusts the token cost.

## Current Evidence Summary
- B070 / B MOT says:
  - fallback tokens checked: 3120
  - weak or unproved fallback costs: 0
  - receipt-proved rows: 2
  - source-token-proved rows: 3118
- Sheet comparison says:
  - fallback tokens checked: 3120
  - fallback tokens differing from latest prior Sheet cost: 1473
  - available wrong-cost fallback tokens: 1096
  - allocated wrong-cost fallback tokens: 377
- Main conflict examples:
  - `6V-EEC1-2S9Z`: B fallback/source proof allows 2.25, Sheet comparison expects 2.22 for 753 tokens.
  - `A2-T2AC-TW3L`: B fallback/source proof allows 4.51, Sheet comparison expects 4.44 for 720 tokens.
- Read-only Sheet comparison:
  - `out/systems/M/b_token_sheet_comparison/summary.md`
- B070 audit output:
  - `out/systems/B/refunds/b_fallback_token_cost_audit.csv`
  - `out/systems/B/refunds/b_fallback_token_cost_audit_summary.csv`

## Allowed Work
- inspect B070 fallback-cost audit output
- inspect Sheet comparison outputs
- inspect local token ledger rows for the two main affected SKUs
- inspect B009 and B070 proof rules
- decide whether `source_token_proved` is strong enough when the source token cost itself may be older than Sheet receipt truth
- update B MOT classification if the proof rule is too weak
- add focused tests for the reconciliation rule

## Forbidden Work
- no token correction
- no stock correction
- no order edit
- no B run or restart
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI or restocking live use

## Acceptance Proof
- The manager explains why B070 says 0 weak rows while Sheet comparison says 1473 mismatches.
- The proof rule is explicitly classified as one of:
  - `sheet_cost_supersedes_source_token`
  - `source_token_cost_is_valid`
  - `requires_batch_link_proof`
  - `requires_luke_business_decision`
- `6V-EEC1-2S9Z` and `A2-T2AC-TW3L` are both resolved or kept blocked from clean trust.
- H and O remain blocked from clean trust for affected SKUs until the reconciliation clears.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any live token, stock, order, Sheet, DB, output, price, queue, ROI, or restocking change.

