# B Refund Token Remaining Lanes v1

## Manager Authority
- task_id: MGR_B_REFUND_TOKEN_REMAINING_LANES_V1
- job_ref: B-REFUND-TOKEN-LANES
- flow: B
- task_type: manager_lane_completion
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B is not stuck because everything is unknown. The remaining refund-return-token warning is already split into named lanes.

This job is to turn the generic parked bridge warning into clear next work:

- 15 rows where stock movement exists but exact Amazon customer-return proof is missing.
- 5 rows where Amazon says the return was damaged or defective, but reusable stock was still used later.
- 1 row where the original return/B009 path still needs separate proof or a protected decision.

## Allowed Work
- inspect B038 refund-return-token bridge
- inspect B041 repair preview
- inspect B051 warning workpack
- inspect B052 Amazon return coverage audit
- inspect B059/B060/B061/B062 disposition proof
- inspect B064 return COGS residual review
- create or refresh manager-visible task rows/packets for each remaining lane
- update B MOT mapping/tests if a lane is proved, superseded, or wrongly parked
- rerun read-only B MOT

## Forbidden Work
- no B run or restart
- no token correction
- no stock recovery exception
- no allocation or COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth
- no scope widening outside B refund-return-token completion

## Acceptance Proof
- The remaining B refund-token work is visible as lane-specific board work, not a vague parked lump.
- The 15 stock-adjustment-only rows stay blocked from clean stock recovery unless direct Amazon return proof or a protected exception exists.
- The 5 damaged/defective reuse rows become a protected correction/exception packet, not a silent manager repair.
- The 1 original/B009 conflict becomes a named proof or decision packet.
- B MOT remains read-only with 0 active B failures.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any live token, allocation, COGS, order, ROI, restocking, Sheet, DB, price, queue, output deletion, B run, or restart action.
