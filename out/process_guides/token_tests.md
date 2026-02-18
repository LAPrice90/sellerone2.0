# Token System Test Checklist

Last run: 2026-01-29
Owner: Luke / SellerOne 2.0

This checklist turns visual spot-checking into explicit, repeatable tests. 
**Do not treat this as a report — it is a PASS/FAIL test sheet.**

---

## 0) Inputs used (record what was actually tested)

- Inventory snapshot: `out/inventory_summaries.csv`
- Token ledger: `out/token_ledger_live.csv`
- Token recon: `out/token_stock_recon.csv`
- Recon mismatches: `out/token_stock_recon_mismatches.csv`
- Token backdate summary: `out/token_backdate_summary.csv`
- Orders sheet snapshot: `out/orders_sheet_orders.csv`

---

## 1) Rules under test (must match rulebook)

**R1 — Stock token count**
- Stock tokens count = Available + FC processing + FC transfer 
- Inbound tokens: **included** (unless explicitly disabled)
- Customer orders: **excluded**

**R2 — Allocation order**
- Newest costs stay with stock
- Oldest costs go to orders

**R3 — Token count limits**
- Tokens are created only for: live stock + live orders
- No tokens for full historic purchases

**R4 — No downstream masking**
- Only fix at base (inventory snapshot / token ledger / allocation), never by altering outputs.

---

## 2) Automated checks (read-only)

### 2.1 Recon deltas must be zero (except in-flight SKUs)
- File: `out/token_stock_recon_mismatches.csv`
- **PASS if:** only SKUs explicitly marked “in-flight” appear
- **FAIL if:** any other SKU appears

**In-flight SKUs (ignore temporarily):**
- Z7-26PV-O9LR
- 8U-QPFH-3EKQ
- NN-TSZ1-X2RD
- XE-YPAI-HX9F
- LP-QMNJ-J49G
- W3-8FN7-FSP0
- C6-XGZB-J6QA

**Result:**
- PASS / FAIL: FAIL
- Notes: non-inflight list refreshed from latest recon.
- Unsellable exceptions (auto-fix blocked because no movable tokens): IB-U5FA-BO2Y, MW-9K5M-VKW8, OZ-3NKR-VLYG, RB-82FL-T88J

---

### 2.2 Token cost allocation vs purchase history
- File: `out/purchase_allocation_mismatches.csv`
- **PASS if:** 0 mismatches
- **FAIL if:** any SKU appears

**Result:**
- PASS / FAIL: FAIL
- Notes: 1 mismatches; first: 0Z-Y60V-499R

---

### 2.3 Token statuses sanity
- File: `out/token_ledger_live.csv`
- **PASS if:** only statuses in {available, allocated, returned_pending, unsellable}
- **FAIL if:** unexpected statuses present

**Result:**
- PASS / FAIL: PASS
- Notes: Only valid statuses present: ['allocated', 'available', 'returned_pending']

---

## 3) Manual spot-checks (visual)

Pick 3 SKUs and compare Amazon inventory vs token_available:

| SKU | Amazon Available | FC Processing | FC Transfer | Inbound | Expected Tokens | Token Available | PASS/FAIL |
|-----|------------------|--------------|-------------|---------|-----------------|----------------|----------|
| Z7-26PV-O9LR | 19 | 0 | 13 | 0 | 32 |                |          |
| 8U-QPFH-3EKQ | 1 | 0 | 4 | 0 | 5 |                |          |
| NN-TSZ1-X2RD | 1 | 5 | 11 | 0 | 17 |                |          |
| XE-YPAI-HX9F | 10 | 0 | 16 | 0 | 26 |                |          |
| LP-QMNJ-J49G | 2 | 0 | 4 | 0 | 6 |                |          |
| W3-8FN7-FSP0 | 3 | 0 | 3 | 0 | 6 |                |          |
| C6-XGZB-J6QA | 5 | 0 | 6 | 0 | 11 |                |          |
| F7-PMJ2-SG6A | 14 | 0 | 0 | 0 | 14 |                |          |
| A2-T2AC-TW3L | 142 | 8 | 0 | 0 | 150 |                |          |
| DC-K5WH-R7F5 | 125 | 1 | 2 | 0 | 128 |                |          |
| L3-ZQ8U-A7LQ | 22 | 2 | 0 | 0 | 24 |                |          |
| R7-98IN-2PW8 | 45 | 1 | 0 | 0 | 46 |                |          |

---

## 4) Final gate

✅ **Ready to move on only if:**
- Recon mismatches cleared (except in-flight)
- Purchase allocation mismatches = 0 (or approved exceptions)
- Manual spot-checks all PASS

**Decision:**
- [ ] PASS → move on
- [ ] FAIL → fix base issue and retest

---

## 5) Running this test (simple order)

1. `python scripts/A003_run_inventory_to_sheet.py`
2. (If testing backdate) `python scripts/one_off/T028_backdate_tokens_from_live_stock.py`
3. Read outputs listed above

---

End of checklist.
