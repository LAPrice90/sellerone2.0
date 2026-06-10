# TASK B P and L Health Gate Proof

Status: proved

## Goal
Explain and clear the B P and L freshness blocker without running random finance scripts or masking the stale output.

## Current Evidence
- B MOT check: `b_pnl_daily`
- Current state: `fail`
- Current value: `blocked_by_b_health_gate`
- Plain English: the latest B cycle did not refresh P and L because the B health gate was failing before the publish/P and L section.
- Current gate clue: `token_shortages_by_sku` has a true live shortage row.
- 2026-05-30 proof detail: `out/token_shortages_by_sku.csv` shows SKU `AK-OB6V-HIYD`, missing quantity `3`, shortage class `true_live_shortage`, and next action `wait_for_receipt_or_approved_stock_correction`.
- 2026-05-30 proof detail: the latest B manifest completed, but its B health gate failed on `token_shortages_by_sku`, so `D001_build_pnl_daily.py` was not seen in that run.

## Allowed Scope
- B manager/MOT proof mapping
- B health-gate proof inspection
- token-shortage explanation/reporting only
- bounded code inspection if the shortage is caused by calculation/proof code
- task packaging for the exact upstream blocker

## Forbidden Actions
- no B live run
- no B restart
- no D001 one-off run as proof
- no Google Sheets write
- no price change
- no queue edit
- no token/data correction
- no local DB alignment
- no output deletion
- no stock receipt or stock correction without Luke approval
- no downstream masking of P and L freshness

## Proof Path
1. Keep `b_pnl_daily` failing while the B health gate is blocking P and L.
2. Prove the upstream gate cause from B scoped evidence, not from chat.
3. If the token shortage is a real stock/receipt issue, leave it parked as a business/protected decision.
4. If the token shortage is a code/proof bug, create a narrower B token-proof repair packet.
5. Retest with:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

Success means:
- `b_pnl_daily` is `ok`, or
- `b_pnl_daily` still fails but names the exact upstream gate and does not send Codex into random D001/P and L repair.

## Rollback Path
Use git diff for manager-code rollback only.

Do not restore or edit business outputs as rollback.

## Stop Condition
Stop when the B MOT either:
- proves P and L freshness,
- keeps the failure accurately tied to the upstream B health gate,
- or identifies a protected stock/receipt/token correction decision.

## 2026-05-30 Worker Classification

This is not a safe manager-code repair. The MOT is correctly pointing to the upstream B health gate. Clearing it needs either normal receipt evidence or an explicitly approved stock/token correction path, not a standalone D001 run and not a finance output edit.

## 2026-05-30 Proof Result

- Luke approved the bounded correction path.
- 3 approved stock-correction tokens were applied for `AK-OB6V-HIYD`.
- `out/token_shortages_by_sku.csv` now has header only.
- `out/cycle_alerts/checklist_B_split.csv` shows:
  - `token_shortages_by_sku=ok 0`
  - `order_master_missing_token_no_placeholder_rows=ok 0`
  - `order_master_placeholder_cogs_rows=ok 0`
- B cycle `B_20260530T191754Z` reached a clean health gate, published P and L, and finalized with `fail=0`, `warn=0`.
- B MOT no longer marks `b_pnl_daily` as a decision or failure.
