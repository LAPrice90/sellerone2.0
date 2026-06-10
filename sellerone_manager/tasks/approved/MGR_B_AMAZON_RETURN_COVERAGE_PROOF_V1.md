# B Amazon Return Coverage Proof v1

## Manager Authority
- task_id: MGR_B_AMAZON_RETURN_COVERAGE_PROOF_V1
- job_ref: B-AMAZON-RETURN-COVERAGE
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B has 15 rows where token or stock-adjustment evidence suggests stock moved, but the Amazon customer return report does not prove the same order and SKU. This job is to keep that gap visible and check whether better outside proof exists.

## Allowed Work
- inspect B052 coverage audit, B039 customer return report proof, B041 repair preview, B038 bridge, B064 residual review, and B051 workpack
- separate exact customer-return proof from stock-adjustment-only proof
- label rows as `exact_amazon_return_proved`, `stock_adjustment_only`, `token_only`, `nearby_sku_only`, or `not_yet_proven`
- update B MOT mapping and focused manager tests if needed

## Forbidden Work
- no B run or restart
- no Amazon live fetch unless a separate approved fetch boundary exists
- no token correction
- no stock recovery exception
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI/restocking live use

## Acceptance Proof
- The 15 rows are classified from outside proof.
- Stock-adjustment-only evidence remains blocked from recovered stock and ROI/restocking.
- B MOT shows no unclassified return-coverage rows.
- Any proposed exception becomes a Luke decision packet, not an automatic repair.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before trusting stock-adjustment-only evidence as stock recovery.

## Proof Result
- B052 rebuilt the read-only Amazon return coverage audit.
- The 15 rows are labelled `stock_adjustment_only`.
- 0 rows are labelled `exact_amazon_return_proved`.
- 0 rows are unclassified.
- 0 rows are order-level safe for stock recovery.
- 0 rows allow live writes, ROI/restocking use, or Sellerboard-final truth.
- B MOT retested the audit as `ok`.

