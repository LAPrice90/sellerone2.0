# B P&L Freshness Warning Review v1

## Manager Authority
- task_id: MGR_B_PNL_FRESHNESS_WARNING_REVIEW_V1
- job_ref: B-PNL-FRESHNESS
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: normal
- luke_action_required: 0

## Plain English
B P&L proof is warning-only because the daily P&L output is stale against the current MOT freshness rule. This job is to prove whether that warning is expected timing, a blocked producer path, or a real repair packet.

## Allowed Work
- inspect B MOT P&L freshness row, latest B manifest, D001/P&L proof artifacts, and existing manager notes
- classify the warning as expected timing, waiting proof, or bounded repair needed
- update board wording and focused manager tests if needed

## Forbidden Work
- no B run or restart
- no D/P&L live rebuild
- no Google Sheets write
- no local DB alignment
- no output deletion
- no refund, fee, shipping, ROI, token, order, price, or queue correction

## Acceptance Proof
- The P&L warning is clearly labelled as timing-only, waiting proof, or a bounded repair task.
- No downstream display is adjusted to hide stale proof.
- B MOT remains the proof source.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before running B, running a live P&L rebuild, or changing output data.

