# SO21 Worker Utilisation Board

Generated UTC: 2026-06-10T08:24:16Z
Owner: Operations

## Summary

- Active workers/reviewers: 0
- Actually working or reviewing now: 0
- Signed out entries tracked: 27
- Quiet active entries needing attention: 0
- Source log: `sellerone_manager/CONTROL/SO21_WORKER_SIGN_IN_OUT_LOG.md`
- CSV output: `out/systems/M/worker_utilisation_board.csv`

## Active Now

No active workers are currently logged.

## Quiet Attention

No active worker is over the quiet threshold in the current log.

## Capacity Warning

Fewer than two non-blocked workers/reviewers are currently moving. Operations should refill a safe lane if one is available.

## Recently Signed Out

| lane | role | job_ref | sign_in_uk | sign_out_uk | duration_minutes | state |
| --- | --- | --- | --- | --- | --- | --- |
| Restocking/Planning | Worker | O-ACTIVE-RESTOCK-FILES | 2026-06-09 16:16 | 2026-06-09 16:24 | 8 | ready_for_review |
| Reviewer/Closure | Reviewer | O-ACTIVE-RESTOCK-FILES | 2026-06-09 16:21 | 2026-06-09 16:26 | 5 | pass |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 11:33 | 2026-06-09 16:45 | 312 | blocked |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 17:10 | 2026-06-09 18:03 | 53 | blocked |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 18:06 | 2026-06-09 18:13 | 7 | repair_ready |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 18:13 | 2026-06-09 18:18 | 5 | blocked |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 18:21 | 2026-06-09 18:26 | 5 | blocked |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 20:16 | 2026-06-09 21:25 | 69 | blocked |
| Emergency Runtime | Worker | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 18:32 | 2026-06-09 18:36 | 4 | blocked |
| Emergency Runtime | Operations F-only handoff | F-SELLER-CENTRAL-SAFE-LOGIN-TODAY | 2026-06-09 22:45 | 2026-06-09 22:50 | 5 | blocked |

## Operating Rule

- Quiet for one Operations pass: nudge.
- Quiet for two Operations passes: block with reason or replace if safe.
- Finished lane: sign out, route review/closure, then refill with the next safe packet.
