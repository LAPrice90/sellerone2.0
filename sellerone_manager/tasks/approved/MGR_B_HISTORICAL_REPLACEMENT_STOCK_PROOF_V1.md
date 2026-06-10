# B Historical Replacement Stock Proof v1

## Manager Authority
- task_id: MGR_B_HISTORICAL_REPLACEMENT_STOCK_PROOF_V1
- job_ref: B-HISTORICAL-REPLACEMENT-STOCK
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B has 4 non-sellable return rows where the currently visible replacement token arrived after the later sale it would replace. This job is to prove whether older clean stock existed at the time, or to keep the rows blocked.

## Allowed Work
- inspect B061 apply preview, B060 impact preview, B059 decision preview, B058 conflict preview, token ledger, token allocation proof, and token COGS proof
- build or refresh read-only manager proof that separates date-valid replacement stock from late replacement stock
- keep each row labelled as `date_valid_currently_available`, `date_valid_but_already_used_later`, `replacement_arrived_after_sale`, `missing_date_proof`, or `not_yet_proven`
- update B MOT mapping and focused manager tests if needed

## Forbidden Work
- no B run or restart
- no token correction
- no replacement-token swap
- no downstream allocation correction
- no COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI/restocking live use

## Acceptance Proof
- B061/B060/B059/B058 proof remains read-only.
- The 4 late-candidate rows are labelled with clear timing proof.
- No row becomes replacement-swap-ready unless the replacement token is proved available on or before the downstream sale.
- B MOT shows the rows as proved, warning-labelled, or parked without creating a false Luke decision.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any live token, allocation, COGS, order, Sheet, DB, output, price, queue, ROI, or restocking change.

## Proof Result
- B065 built the read-only historical replacement-stock proof.
- The 4 rows are classified as `date_valid_but_already_used_later`.
- 0 rows are direct replacement-swap-ready.
- 0 rows allow live writes, ROI/restocking use, or Sellerboard-final truth.
- B MOT retested the row as warning-labelled/parked, not failed.

