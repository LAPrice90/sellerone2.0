# B Damaged Return Reuse Decision Preview v1

## Manager Authority
- task_id: MGR_B_DAMAGED_RETURN_REUSE_DECISION_PREVIEW_V1
- job_ref: B-DAMAGED-RETURN-REUSE
- flow: B
- task_type: protected_decision_preview
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B has 5 rows where Amazon return evidence says the returned item was damaged or defective, but the token chain shows reusable stock was later used.

This job is to prepare the human-level decision preview only. It must not correct token, allocation, COGS, order, ROI, or restocking data.

## Allowed Work
- inspect B059 disposition decision preview
- inspect B060/B061/B062 disposition correction proof
- inspect B041 return-token repair preview
- inspect B064 return COGS residual review
- summarise the 5 affected rows in plain English
- recommend either protected correction or protected exception labelling
- create a Luke decision packet only after the impact is clear

## Forbidden Work
- no B run or restart
- no token correction
- no downstream allocation correction
- no return COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth

## Acceptance Proof
- The 5 rows have a clear correction-vs-exception preview.
- Downstream sale-token and return-COGS impact is visible.
- No live write flags are enabled.
- Any live correction or exception is separated into a protected Luke decision.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before token, allocation, COGS, ROI, restocking, Sheet, DB, or output changes.

## Decision Preview Completed - 2026-06-04
B has 5 affected rows in this lane.

Plain English:

- Amazon return evidence says these items were damaged or defective.
- The token chain still shows reusable stock from those returns being used later.
- That means B must not treat the recovered stock or recovered COGS as clean proof for ROI/restocking unless Luke approves a protected correction or a named exception.

Manager recommendation:

- Preferred safe correction: remove or relabel the unapproved reusable returned-stock recovery for these 5 rows, then review the later sale tokens that used them.
- Alternative exception: keep the recovered stock, but label it as a business exception so ROI/restocking never mistakes it for clean Amazon-proved reusable stock.

Affected rows:

- 026-9612992-1390769 / EE-KTDC-KCFY
- 202-9939626-9381935 / 3X-EXDD-TD2K
- 203-0310058-9573145 / WX-L5UA-UB1Q
- 203-0504563-6267559 / 6V-EEC1-2S9Z
- 204-7722459-2601949 / 3X-EXDD-TD2K

Protected decision needed before live repair:

- choose correction, or
- choose named exception.

Until then, this lane stays blocked from clean ROI/restocking proof.

## Luke Approval - 2026-06-04
Luke approved protected correction, not exception, for this lane.

Allowed from here:

- build or use the correct protected correction preview/apply path for these 5 rows
- snapshot affected local B proof files first
- update only the approved local B token/allocation/COGS proof chain if validation passes
- retest through read-only B MOT

Still forbidden:

- no Google Sheets
- no local DB alignment
- no prices or queues
- no output deletion
- no Sellerboard-as-final ROI/restocking truth
- no widening beyond these B return-token correction rows
