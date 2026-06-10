# B Level 3 ServiceFee Superseded Path v1

## Manager Authority
- task_id: MGR_B_LEVEL3_SERVICEFEE_SUPERSEDED_PATH_V1
- job_ref: B-LEVEL3-SERVICEFEE-PATH
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B should not stay parked because an old ServiceFee file is empty if the current Level 3 API proof already has the useful order-level commission, FBA fee, shipping income, shipping chargeback, and refund-fee reversal evidence.

This job classifies the old empty ServiceFee path as superseded when the current useful API source paths are present.

## Allowed Work
- inspect B068 Level 3 fee/shipping proof map
- update manager-only proof labels and MOT wording
- add focused tests for superseded/non-blocking ServiceFee path
- run B068/B067 read-only proof and read-only B MOT

## Forbidden Work
- no B run or restart
- no live Amazon API pull
- no fee, shipping, refund, ROI, order, token, COGS, or restocking data correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no Sellerboard values as final live ROI/restocking truth
- no scope widening

## Acceptance Proof
- The old empty ServiceFee path is labelled as superseded or non-blocking when the current Level 3 API money paths are present.
- B068 still fails or warns if required useful API source paths are missing.
- Unsafe live ROI/restocking remains blocked.
- Focused B068/B MOT tests pass.
- Read-only B MOT retest clears the false Level 3 parked warning or leaves only a real bounded warning.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop if this would require a live Amazon pull, B run/restart, business output write, Sheet write, DB alignment, output deletion, price/queue change, or live ROI/restocking use.
