# B No-Replacement Shortage Exception Review v1

## Manager Authority
- task_id: MGR_B_NO_REPLACEMENT_SHORTAGE_EXCEPTION_REVIEW_V1
- job_ref: B-NO-REPLACEMENT-REVIEW
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B has 1 non-sellable return row with no clean replacement token. This job is to prove the shortage clearly and keep it out of recovered stock unless Luke later approves a business exception.

## Allowed Work
- inspect B061 apply preview, B060 impact preview, token ledger, token allocation proof, and token COGS proof
- prove whether the row is a true no-replacement shortage, a missing-date proof gap, or a mapping gap
- keep the row blocked from stock recovery and ROI/restocking until a protected decision exists
- update B MOT mapping and focused manager tests if needed

## Forbidden Work
- no B run or restart
- no token creation or correction
- no replacement-token swap
- no downstream allocation correction
- no COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI/restocking live use

## Acceptance Proof
- The 1 no-replacement row has a clear manager label.
- If no replacement stock exists, the row stays parked as shortage/exception review.
- If proof is missing rather than stock missing, a bounded follow-up task is created.
- B MOT continues to block the row from ROI/restocking and Sellerboard-final truth.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before proposing or applying any live stock recovery exception.

## Proof Result
- B066 built the read-only no-replacement shortage/exception review.
- The 1 row is classified as `true_no_replacement_shortage`.
- The proof found 29 clean same-SKU tokens, but all 29 had already been used before the downstream sale.
- 0 rows are direct replacement-swap-ready.
- 0 rows allow live writes, ROI/restocking use, or Sellerboard-final truth.
- B MOT retested the row as warning-labelled/parked, not failed.

