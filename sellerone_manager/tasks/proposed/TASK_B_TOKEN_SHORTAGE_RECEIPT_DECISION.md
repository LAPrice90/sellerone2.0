# TASK B Token Shortage Receipt Decision

Status: proved

## Goal

Clear the remaining B health gate blocker without hiding a real stock/token shortage or forcing P and L to publish from bad upstream evidence.

## Current Evidence

- B MOT check: `b_pnl_daily`
- Current state: `decision_needed`
- Current value: `blocked_by_protected_token_shortage`
- B manager task state: `blocked_needs_luke`
- B manifest: latest B run completed the core order/token/order-master steps, then failed the B health gate.
- Blocking health check: `token_shortages_by_sku`
- SKU: `AK-OB6V-HIYD`
- Missing quantity: `3`
- Shortage class: `true_live_shortage`
- Current recorded next action: `wait_for_receipt_or_approved_stock_correction`

## Decision Recorded

Luke approved the bounded correction on 2026-05-30 with:

```text
Approve correction
```

## Result

- Added approved correction row to `out/manual_token_corrections_approved.csv`.
- Applied 3 approved stock-correction tokens with `scripts/one_off/T030_apply_approved_token_corrections.py`.
- Backup written to `out/backups/manual_token_corrections_20260530T191308Z/`.
- Audit row written to `out/manual_token_correction_events.csv`.
- B maintenance was requested, reached `maintenance.ready`, correction was applied, and maintenance was released.
- B-owned proof cycle `B_20260530T191754Z` published P and L.
- B split health after proof: `fail=0`, `warn=0`.
- B MOT after proof: `status=warn`, `fail_count=0`, and no Luke decision.

## Plain English

B is not broken at the order-collection level. B is refusing to publish P and L because one SKU has sold units that do not have enough trusted stock tokens behind them.

That is the correct failure. The manager must not bypass it by running D001 manually or editing the finance output.

## Allowed Scope

- inspect B token shortage proof
- inspect receipt or stock-token evidence
- create a bounded correction plan if the shortage is proven to be a data-entry or receipt timing issue
- wait for normal receipt evidence if the shortage is genuine
- retest B MOT after the upstream shortage clears

## Forbidden Actions

- no B live run
- no B restart
- no D001 standalone P and L run as proof
- no Google Sheets write
- no price change
- no queue edit
- no token correction without approval
- no stock receipt creation without approval
- no local DB alignment
- no output deletion
- no downstream masking of P and L freshness

## Decision Path

Choose one of these when this becomes a Luke decision:

1. Wait for receipt evidence
   - Use this if the stock is genuinely awaiting receipt or normal token creation.
   - B remains blocked for P and L until the next B health gate clears.

2. Approve a bounded stock/token correction
   - Use this only if the missing quantity is proven to be a data-entry or receipt timing issue.
   - Correction must be done through a separate approved repair packet with rollback proof.

3. Reject correction and keep parked
   - Use this if the shortage reflects real missing stock or uncertain evidence.
   - Manager keeps B P and L blocked rather than publishing untrusted profit.

## Acceptance Checks

- `token_shortages_by_sku` clears or is explicitly parked by decision.
- The next finalized B run no longer blocks P and L on the health gate.
- B MOT `b_pnl_daily` becomes `ok`.
- B MOT `b_management_ready_for_maintenance` becomes `ok` or only warning-level.
- No Sellerboard bridge values are fed into live ROI/restocking.

## Proof Command

After the upstream shortage clears through receipt or approved correction:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

## Stop Condition

Correction path is now complete. Any future stock, token, receipt, Sheet, local DB, queue, price, or finance-output correction still needs its own exact approval.
