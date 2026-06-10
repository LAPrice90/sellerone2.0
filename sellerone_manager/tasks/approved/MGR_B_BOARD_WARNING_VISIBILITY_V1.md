# B Board Warning Visibility v1

## Manager Authority
- task_id: MGR_B_BOARD_WARNING_VISIBILITY_V1
- job_ref: B-BOARD-WARNING-VISIBILITY
- flow: B
- task_type: manager_board_visibility
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B is warning-only, not clean. The manager board must show the current B warning work without making Luke read raw MOT output.

Current B outside proof says:

- B has 0 active fails.
- B has 6 active warnings.
- Core B runtime proof is present: latest manifest, orders, order items, order master, token ledgers, stock snapshot, worker owner, supervisor owner, and maintenance marker proof are ok.
- B order truth is not complete because refund, return-token, Sellerboard bridge, marketplace coverage, P and L freshness, and API money-proof confidence still need clear labels or later proof.
- Old B checklist rows are clue-only and must not drive repair by themselves.

## Allowed Work
Manager/MOT and task-board visibility only:

- classify current B warnings into board lanes
- ensure `b_pnl_daily`, `b_marketplace_coverage_report`, and `b_management_ready_for_maintenance` are visible as warning-only or waiting-proof board work when current B MOT sees them
- keep `b_refund_return_token_bridge`, `b_sellerboard_refund_fee_roi_bridge`, and `b_order_truth_completion` visible as parked warning lanes until API proof or protected approval changes them
- keep `b_manifest_gate` and `b_old_checklist_clue` as clue-only/not-checked context, not worker repair jobs
- update manager packet wording and focused manager tests if needed

## Forbidden Work
- no B run or restart
- no lock or maintenance marker edits
- no Google Sheets writes
- no price or queue changes
- no token, order, refund, fee, shipping, stock, or ROI data correction
- no local DB alignment
- no output deletion
- no live ROI or restocking use
- no scope widening into A, E, H, F, or O

## Acceptance Proof
- Run the B independent MOT only.
- Refresh approved manager task packets.
- Confirm the Manager Task Board has B cards for proved history, parked warning lanes, and protected decisions without creating a false Luke decision.
- Confirm B remains 0 fail and warning-only unless new evidence appears.

## Proof Completed - 2026-06-04T09:50Z
- B independent MOT was refreshed read-only.
- B remained warning-only with 0 independent B failures.
- Manager-approved task packets were refreshed.
- Stale B protected-decision board rows were corrected:
  - the original returned-token apply decision is proved, not awaiting Luke
  - the superseded disposition decision is parked, not awaiting Luke
- Current B proof gaps remain visible through MOT rows and parked packet lanes rather than a private chat list.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop immediately if the work requires a B worker cycle, restart, protected data correction, marker edit, Sheet write, local DB alignment, output deletion, price/queue change, or use of bridge values as final ROI/restocking truth.
