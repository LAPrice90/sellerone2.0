# B Fallback Token Data Correction Decision v1

## Manager Authority
- task_id: MGR_B_FALLBACK_TOKEN_DATA_CORRECTION_DECISION_V1
- job_ref: B-FALLBACK-DATA-CORRECTION
- flow: B
- task_type: protected_data_correction_decision
- status: parked
- authority: needs_luke_decision
- priority: high
- luke_action_required: 0

## Plain English
The existing live token ledger may need correction or parking for fallback tokens that copied the wrong cost. That is protected because it changes local stock-cost truth.

## Current Evidence Summary
- Existing-token correction is not approved yet.
- Current read-only comparison found:
  - 1473 fallback tokens differ from latest prior Sheet cost.
  - 1096 are still available.
  - 377 are already allocated.
- Main affected SKUs:
  - `6V-EEC1-2S9Z`: 753 available fallback tokens at 2.25 where Sheet says 2.22.
  - `A2-T2AC-TW3L`: 720 fallback tokens at 4.51 where Sheet says 4.44.
- Before Luke is asked to approve any correction, B must produce an exact preview showing:
  - which token IDs would change or be parked
  - what cost they currently carry
  - what proof cost would replace it
  - P&L/H/O impact
  - rollback path

## Allowed Work
- build a read-only correction preview after `B-FALLBACK-COST-AUDIT`
- show which tokens would be corrected, parked, or left alone
- show impact on H floors, B P&L, E ROI, and O restocking confidence
- prepare a rollback plan

## Forbidden Work
- no live token ledger edit without explicit Luke approval
- no stock correction
- no order edit
- no B run or restart
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI or restocking live use

## Acceptance Proof
- A preview exists before any data correction is considered.
- The preview separates code bug prevention from historical data correction.
- Luke is asked only after the preview shows the exact affected tokens and business impact.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before applying any existing token correction, token parking, stock correction, order correction, Sheet write, DB alignment, price change, queue edit, or output deletion.

