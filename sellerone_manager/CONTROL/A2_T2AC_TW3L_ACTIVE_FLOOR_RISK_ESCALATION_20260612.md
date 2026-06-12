# A2-T2AC-TW3L Active Floor Risk Escalation - 2026-06-12

Job ref: `A2-T2AC-TW3L-FLOOR-NOT-UPDATED-ACTIVE-RISK`

## Plain-English Verdict

Luke is right. This should not have been sitting in `Ready Later`.

The guard stopped an unsafe automatic floor write, but the management system then treated that as if the risk was handled. It was not handled. The SKU still has a live pricing risk because H is still choosing an older fallback stock token instead of the newer receipt token.

## What The Evidence Shows

SKU: `A2-T2AC-TW3L`

- Fresh stock receipt tokens exist at cost `4.89`.
- H is still selecting an older fallback token at cost `4.51`.
- H detects the conflict and refuses to create a clean floor.
- Because no clean floor is produced, the repricer does not write a new floor.
- The latest runtime snapshot still shows `READ_ONLY_NO_WRITE`.
- `data/repricing_live_execution_log.csv` shows no live repricer write for this SKU.
- The board incorrectly left `Token Pricing Issue` under `Ready Later`.

## Current Business Risk

This is not a missing-token problem anymore.

This is a token-selection and escalation problem:

1. B has the newer stock receipt tokens.
2. H can see the newer token.
3. H still selects the older fallback token first.
4. H blocks the write because it knows the floor is not clean.
5. The Manager/MOT view does not escalate that blocked floor as a live business risk strongly enough.

## Immediate Control Decision

The board must treat this as active until one of these is true:

- H selects the newer receipt token and produces a clean floor.
- A protected decision is made to quarantine/ignore the older fallback tokens for this SKU.
- Luke approves a separate protected live price/floor correction path.

## What Was Not Done

No price was changed.

No token ledger was edited.

No Google Sheet was written.

No queue, database, Task Scheduler, Amazon, or runtime process was changed.

## Required Follow-Up

Create and run a bounded read-only worker packet:

`A2-T2AC-TW3L-FLOOR-NOT-UPDATED-ACTIVE-RISK`

The packet must answer:

- why H still chooses the fallback token
- whether the fallback tokens should be quarantined from clean floor selection
- why MOT did not turn this into a visible urgent pricing alert
- what exact proof will show the floor is safe again

