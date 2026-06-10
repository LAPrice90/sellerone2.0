# B Completion And Order Coverage Blueprint

Created UTC: 2026-05-27T12:45:00Z

## What This Is
B completion is split into two gates.

`B Management ready for maintenance` means the manager can watch B, create bounded repair jobs, and prove retests without Luke managing technical steps.

`B order truth complete` means orders, marketplaces, Sellerboard comparison, refunds, shipping, fees, and ROI support are API-proven or clearly labelled.

## Current Truth
The old B checklist is only a clue.

B has current proof for core outputs, owner, heartbeat, lock state, and maintenance marker state.

B is not complete while these remain open:
- admin Sellerboard inbox access is not yet proven by local Gmail metadata proof
- Amazon.ae missing order recovery is not yet API-proven in quarantine
- per-marketplace order cursors are missing for some marketplaces
- refund, shipping, fee, and ROI bridge values are not fully API-proven

## Manager Expectation
The independent B MOT must show:
- B Management readiness gate
- B order truth completion gate
- admin Sellerboard email source proof through the local Gmail OAuth route used by FPM016
- Sellerboard attachment arrival, format, freshness, and cleanup safety
- marketplace recovery quarantine state
- per-marketplace cursor freshness
- Sellerboard missing-order and SKU mapping state
- duplicate and live-merge guard state
- bridge labels: `API proved`, `Sellerboard bridge estimate`, or `not yet proven`

## Bounded Worker Tasks
Codex can safely work on:
- manager readiness gate logic
- read-only marketplace coverage reporting
- read-only recovery quarantine proof
- per-marketplace cursor proof
- Sellerboard bridge comparison
- parser/report tests
- MOT retest rules and work-item packaging

## Forbidden Actions
Stop before:
- Gmail authorization
- Gmail deletion
- running or restarting B
- editing locks or maintenance markers
- writing Google Sheets
- aligning local DB data
- deleting outputs
- merging recovered orders into live data
- feeding Sellerboard or recovered values into ROI/restocking
- changing prices or queues

## Retest Rule
No code edit proves B completion.

Each B task is proved only when the same independent B MOT check clears after the bounded worker repair.
