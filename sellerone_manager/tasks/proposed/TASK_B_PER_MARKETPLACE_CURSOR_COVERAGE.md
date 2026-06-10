# TASK B Per-Marketplace Cursor Coverage

Status: proposed

## Goal
Give each Amazon marketplace its own daily order cursor proof so UK activity cannot hide quiet marketplace orders.

## Manager Expectation
The future B proof must show one fresh cursor or last-success timestamp per Amazon marketplace.

## Current Evidence
- B MOT check: `b_future_marketplace_order_cursors`
- Current state: `fail`
- Current value: `missing_cursors=0;stale_cursors=12`
- Plain English: all Amazon marketplaces are listed, but their independent cursor proof is stale. The shared order marker is fresh, but that must not be allowed to hide quiet marketplaces.
- 2026-05-30 proof detail: the cursor source file has one row for each Amazon marketplace, but the latest cursor timestamp is `2026-05-27T14:40:06Z`, about 74 hours old at the current MOT. This is a real stale-proof condition, not a manager mapping bug.

## Allowed Scope
- per-marketplace cursor proof design
- read-only cursor report
- manager MOT checks
- tests for missing and stale marketplace cursors
- a separately approved read-only cursor proof window that refreshes cursor proof without running B live

## Forbidden Actions
- no live B run
- no B restart
- no shared marker edit
- no cursor overwrite during manager proof
- no order backfill
- no recovered-order live merge
- no Google Sheets write
- no local DB alignment
- no output deletion
- no order data correction
- no price or queue change

## Acceptance Checks
- Every participating Amazon marketplace is listed.
- Missing cursor proof creates a B MOT work item.
- Stale cursor proof creates a B MOT work item.
- A fresh UK/shared marker cannot clear a non-UK marketplace cursor gap.
- The stale cursor gap only clears when the per-marketplace cursor proof itself refreshes.

## Retest Rule
Retest with the B independent MOT and confirm `b_future_marketplace_order_cursors` clears.

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

## Rollback Path
Use git diff for manager-code rollback only.

Do not edit or delete cursor, order, quarantine, or live B outputs as rollback.

## Stop Condition
Stop and return to Luke before changing any live marker, running B, restarting B, or writing live order data.

## 2026-05-30 Worker Classification

This packet stays parked for a separate approved proof window. The safe next repair is a read-only per-marketplace cursor proof refresh, not a B live run, marker edit, backfill, or data correction.
