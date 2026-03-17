# Token System Rulebook & Process Guide

Last updated: 2026-01-28
Owner: Luke / SellerOne 2.0

This guide defines the **token system rules**, **backdating rules**, and **ongoing operating process**. It is the source of truth to avoid re-explaining or reinterpreting the logic.

---

## 1) Purpose of the token system

Tokens represent **unit-level cost** for SKUs. They are used to:
- attach **COGS** to orders,
- reflect **live stock value**, and
- keep pricing consistent over time.

Tokens are not created from “all historical purchases.”
Tokens are created only for **what is actually live**:
- live orders
- live stock (in Amazon inventory)

---

## 2) Core rules (non-negotiable)

### Rule SOT - Single source of truth for live allocation
For live runs, local token files are the single source of truth.

- `out/token_ledger_live.csv` and `out/token_allocations_live.csv` are authoritative.
- Google Sheets are visibility/intake surfaces only and must not drive live allocation decisions.
- B030 validates local allocations and records `mode=local_master`.
- B007 allocates from local files and records `mode=local_master`.

### Rule A — Tokens are limited to live reality
Only create enough tokens to cover:

**Required tokens = Orders + Stock**

### Rule B — Stock tokens do NOT include customer orders
Customer orders already exist in the orders database, so they must not be added again as stock tokens.

**Stock tokens =**
- Available
- Inbound (only if you want future-ready tokens)
- Reserved (non-customer)
- FC processing
- FC transfer

**Do NOT include:**
- Customer orders
- Future supply buyable / reserved future supply
- Unfulfillable (including defective)
- Researching

### Rule B1 — Inventory bucket mapping (what counts as available tokens)
Use this mapping when translating Amazon inventory details into stock tokens.

**Counts as available tokens (YES):**
- Available
- FC processing
- FC transfer
- Inbound (optional: include only if you want future-ready tokens)

**Does NOT count (NO):**
- Customer orders
- Reserved future supply / future supply buyable
- Unfulfillable (including defective)
- Researching

### Rule B2 — Researching inventory (new status)
Researching units are **not sellable** but **still part of live inventory**.
We track them separately so they are not treated as available.

**Token handling:**
- Researching units must have tokens (cost is real).
- Tokens are tagged **research_pending** (not available).
- When Amazon marks them sellable again, they move back to **available**.

### Rule C — Cost allocation order (newest first)
Newest purchase costs go to **stock** first.
Older costs are used for **orders**.

Example:
- Latest batch cost £1.05 (10 units)
- Previous batch cost £1.00 (10 units)
- Stock = 11
- Orders = 9

Allocation:
- Stock: 10 @ £1.05 + 1 @ £1.00
- Orders: 9 @ £1.00

### Rule D — Token creation is append-only
We never delete/rewrite Token_Ledger in normal operations.
If a rebuild is required, it must be deliberate and one-off.

### Rule E — Stock tokens exclude customer orders (explicit)
Customer orders are handled in Order_Master and allocation.
Never include customer orders in stock token counts.

### Rule F — Required token count is capped to live reality
Even if purchase history shows more units, we only create the number
required to cover **live stock + live orders**.

---

## 3) Backdating process (full rebuild)

Backdating is only used when the system is out of sync.
It **must not be part of the daily loop**.

**Backdating and Ongoing are separate processes.**
- Backdating = one-off rebuild using a fixed snapshot (manual trigger only)
  - Uses a frozen inventory snapshot + order master
  - Purpose: reset the system to a clean, correct baseline
- Ongoing = daily flow only (no automatic adjustments)
  - New orders get tokens
  - Refunds/returns handled by B008/B009
  - New stock tokens come only from the Tokens intake sheet

**Never mix these.** If backdating runs in the loop, it will override the ongoing system and create drift.

### Inputs used:
- Orders data (Level 1/2/3)
- Live inventory snapshot
- Purchase history / cost history

### Backdating steps:

1) **Calculate live orders per SKU**
   - Use Order_Master (orders)

2) **Calculate stock tokens per SKU**
   - Available + Inbound + Reserved (non-customer) + FC processing + FC transfer

3) **Compute Required tokens**
   - Required = Orders + Stock

4) **Allocate costs**
   - Newest costs → Stock first
   - Older costs → Orders

5) **Create tokens only up to Required total**
   - Do not create extra tokens for historical purchases

6) **Rebuild allocations**
   - Orders should consume older tokens
   - Stock holds newest tokens

7) **Verify**
   - Spot-check SKUs against live inventory + recent orders

### Backdating must NOT run in the live loop
Backdating scripts are one-off and must be run manually only.

### Output:
- Token_Ledger should reflect **live orders + live stock only**

---

## 4) Ongoing process (daily/weekly)

The daily system should only:
- pull new orders
- apply tokens to orders
- update live stock
- append new tokens from the **Tokens intake sheet**

Allocation rule:
- Token allocation reads from Order_Master and also includes rows in `out/orders_missing_tokens.csv` so missing token COGS can be resolved without waiting for Order_Master to include those orders.

### Live inventory is the source of truth for stock counts
Inventory comes from the SP-API inventory summaries. The reconciliation logic
uses:
- available
- inbound (shipped + receiving)
- reserved_transfers
- reserved_processing
and explicitly excludes reserved_customer (customer orders).

### Ongoing token creation:
Source: Google Sheet **Tokens** tab

Required inputs:
- intake_date
- seller_sku
- qty
- cost_per_unit

System writes:
- batch_id
- status
- processed_at
- error_message
- tokens_created
- token_id_prefix

### Status rules:
- **APPLIED** only if tokens_created == qty
- **PARTIAL** if tokens_created < qty (never mark APPLIED)
- **ERROR** if validation fails

### Partial rows are not “done”
If a row is PARTIAL, the intake row must be corrected and re-run.

---

## 5) Token ID + batch rules

Batch IDs are auto-generated per intake date:
- SR-YYYYMMDD-###

Batch ID generation must:
- check **both** Tokens intake sheet AND Token_Ledger
- never reuse a batch ID

### Batch ID source
Batch IDs are generated by the system from the intake_date. They do not exist
before processing. If intake rows are deleted/rewritten, the same batch ID can
collide unless ledger batch IDs are included in the uniqueness check.

---

## 6) What must never happen again

- Backdating scripts running inside the live loop
- Tokens marked APPLIED when only partially created
- Counting customer orders as stock tokens
- Creating tokens for entire purchase history

## 7) Current implementation (how the scripts actually work today)

This is how the system behaves right now so a new engineer can pick it up
without guessing:

### Inventory capture (A003_run_inventory_to_sheet.py)
- Pulls inventory summaries from SP-API
- Writes `Inventory_raw` and `Listings_focus_summary`
- Updates Product_DB stock fields
- Writes token reconciliation tabs:
  - `Token_Stock_Recon`
  - `Token_Stock_Recon_Mismatches`

**Inventory totals used in recon:**
```
inventory_total = available
                + inbound_shipped + inbound_receiving
                + reserved_transfers
                + reserved_processing
```
Reserved_customer is excluded by design.

Expected tokens:
```
expected_token_total = inventory_total + net_sold_qty
net_sold_qty = sold_qty - refunded_qty
```

Researching alignment:
- `inventory_researching` is compared to `token_research_pending`
- `delta_researching` must be 0 for a clean match

### Token intake (process_stock_receipts_sheet.py)
- Reads Tokens intake tab
- Generates batch_id per intake_date
- Appends tokens to Token_Ledger
- Updates row status:
  - APPLIED if created == qty
  - PARTIAL if created < qty
  - ERROR if validation fails

### Token allocation (B007_allocate_tokens_live.py)
- Reads Token_Ledger + Order_Master
- Orders sorted newest-first (latest orders processed first)
- Tokens sorted oldest-first (by lot_rank or received_date)
- Allocates tokens to orders **FIFO** (older costs to orders)
- Leaves newest tokens available for stock
- Writes Token_Allocations and rewrites Token_Ledger with status updates

### Researching sync (B010_apply_researching_delta.py)
Amazon often does **not** emit RESEARCHING in the stock events ledger, so we
sync it using **inventory snapshots** (daily).

How it works:
- Compare `researching` count in today’s inventory snapshot vs yesterday’s
- If researching increases: move newest **available** tokens → `research_pending`
- If researching decreases: move newest **research_pending** tokens → `available`

This keeps researching inventory non-sellable but cost‑tracked without
waiting for an event that never arrives.

Outputs:
- `out/researching_delta_events.csv`
- `out/token_ledger_live.csv` (when sheets write disabled)

Run daily after A003 and before reconciliation.

**Efficiency note (avoid busywork):**
- If `delta_researching` is non‑zero but **COGS and delta_total are stable**, treat it as informational.
- Only intervene when it causes missing COGS or large reconciliation drift.

### Unsellable sync (B010_apply_researching_delta.py)
Inventory ledgers often miss unsellable events. We sync unsellable counts
from inventory snapshots the same way as researching.

How it works:
- Compare `unsellable` count today vs yesterday
- If unsellable increases: move newest **available** tokens → `unsellable`
- If unsellable decreases: move newest **unsellable** tokens → `available`

Run daily after A003 (or after researching sync).

### One-off backdate (T028_backdate_tokens_from_live_stock.py)
- Pulls live inventory inside the script (no stale CSV)
- Calculates stock tokens from live inventory:
  - available + inbound + reserved_transfers + reserved_processing
  - excludes reserved_customer
- Calculates order tokens from Order_Master (net sold minus refunds)
- Required tokens = stock + orders
- Optional order buffer to cover snapshot gap:
  - Use BACKDATE_ORDER_BUFFER_MINUTES to add recent orders on top of stock
  - This prevents a token shortfall if orders arrive after the inventory pull
- Cost source can be overridden:
  - Use BACKDATE_ORDERS_CSV to point at your purchase-cost file
- Sheet writes can be disabled:
  - Use BACKDATE_SKIP_SHEETS=1 to avoid writing Token_Ledger and Order_Master to Sheets
- Selects newest purchase costs first, but assigns **older costs to orders**
- Rebuilds Token_Ledger + Token_Allocations in one pass
- Writes summary to `out/token_backdate_summary.csv`
- Must never run in the live loop

#### How to run (one-off)
1) Ensure Order_Master is up to date (run B001/B002/B004).
2) Ensure LWA tokens are valid (SP-API access works).
3) Run the script:
   `python scripts/one_off/T028_backdate_tokens_from_live_stock.py`
4) Confirm output:
   - `out/token_ledger_live.csv`
   - `out/token_allocations_live.csv` (cleared, header only)
   - `out/token_backdate_summary.csv`
5) Spot-check 2–3 SKUs against live inventory + recent orders.

### Token COGS (B025_build_token_cogs_ledger.py)
- Builds per-order token cost ledger from allocations

### Refunds + stock adjustments
- B008_apply_refunds_to_tokens.py
- B009_apply_stock_adjustments_to_tokens.py

#### Refunds (B008)
- Refund events mark tokens as **returned_pending** for that order + SKU.
- The original order keeps its COGS; refunds do **not** move COGS off the sale date.

#### Return-to-inventory credits (B009)
- When inventory ledger shows a **SELLABLE return**, tokens in `returned_pending` are moved back to **available** (FIFO).
- When inventory ledger shows **RESEARCHING**, tokens in `returned_pending` are moved to **research_pending** (FIFO).
- A **return ledger** row is written to `out/token_return_ledger.csv` for each token returned to stock.
- `D001_build_pnl_daily.py` reads `token_return_ledger.csv` and adds **positive COGS** on the return date.

Result:
- Sale date keeps its COGS.
- Refund date shows refund transactions.
- Return-to-stock date shows **positive COGS** (credit) using the original token cost.

## 8) Additional rules to avoid future issues

1) **Never run backfill scripts in loops.**
   Only one-off, manual runs.

2) **Never delete intake rows after APPLIED.**
   Deleting rows breaks idempotency and can cause silent token gaps or
   duplicate assumptions.

3) **If Token_Ledger is empty for a SKU, do not allocate.**
   Investigate intake → ledger flow first.

4) **Reconcile daily.**
   `Token_Stock_Recon_Mismatches` must be reviewed when deltas > 0.

5) **Partial intake rows are real errors.**
   A PARTIAL row means token creation did not match qty and must be corrected.

---

## 9) Operator checklist (short version)

Before running backdate:
- Confirm live inventory snapshot
- Confirm order window
- Confirm cost history
- Ensure backdate script is **not in loop**

During daily ops:
- Only process new intake rows
- Never delete intake rows after apply
- **Guardrails (ongoing collector):**
  - Script will not run unless `RECEIPTS_RUN=YES`
  - Hard stop if any intake row has qty > 0 but missing cost_per_unit
  - Hard stop if duplicate batch_id exists in the intake sheet

---

## 10) File locations

- Tokens intake sheet: Google Sheet (Tokens tab)
- Token ledger sheet: Google Sheet (Token_Ledger tab)
- Intake processor: scripts/process_stock_receipts_sheet.py
- Backdate script: scripts/one_off/T028_backdate_tokens_from_live_stock.py

---

## 11) Glossary

- **Token**: one unit of cost assigned to a SKU
- **Token_Ledger**: append-only record of tokens
- **Orders tokens**: tokens attached to actual orders
- **Stock tokens**: tokens representing live inventory
- **Backdating**: full rebuild of tokens for live state

---

## 12) Known decisions

- Stock gets newest costs first
- Orders get older costs
- Customer orders never counted as stock

---

End of guide.
