# B Money Handoff Split v1

## Manager Authority
- task_id: MGR_B_MONEY_HANDOFF_SPLIT_V1
- job_ref: B-MONEY-HANDOFF-SPLIT
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B should prove its own refund, fee, shipping, and refund-drag money chain without waiting for E or O to refresh their confidence labels.

The current B warning is mixing two different things:
- B source proof: whether B has API-backed money evidence.
- Downstream consumption proof: whether E and O have consumed that evidence and become business-ready.

This job separates those so B can hand off clean money proof without pretending E/O restocking is ready.

## Allowed Work
- inspect B067 refund/fee/shipping gap review
- inspect B068 Level 3 fee/shipping proof map
- update manager-only proof labels and MOT wording
- keep E/O downstream warnings visible as handoff warnings, not B source failures
- add focused tests for the split
- run read-only B MOT and focused tests

## Forbidden Work
- no B run or restart
- no live Amazon API pull
- no refund, fee, shipping, ROI, restocking, order, token, allocation, or COGS data correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no Sellerboard values as final live ROI/restocking truth
- no scope widening into E/O live runs

## Acceptance Proof
- B067 summary separates B source proof from downstream E/O consumer warnings.
- B MOT does not keep B money proof parked only because E/O have not consumed it yet.
- Unsafe live ROI/restocking remains blocked.
- E/O downstream warnings remain visible as downstream handoff work.
- Focused B067 and B MOT tests pass.
- Read-only B MOT retest runs without B live execution.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop if clearing the warning would require running B, changing live outputs, promoting Sellerboard estimates, writing Sheets, aligning DB facts, deleting outputs, changing prices or queues, or running E/O live.
