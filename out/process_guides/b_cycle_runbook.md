# B Cycle Runbook (Orders -> Fees -> COGS -> P&L)

This guide explains, in plain language, how the B scripts work, which columns come from where, how taxes are handled, and how tokens/COGS flow from the moment an order arrives to a usable P&L.

If you ask "is this right?" in future, the check is: does each step below match the actual script output at that time.

---

## 0) What the B cycle is

The B cycle is the "operational" pipeline. It pulls orders, applies fees, attaches tokens, builds Order_Master, and produces P&L inputs.

It does NOT set selling prices, create purchase tokens, or modify your purchase sheet. It only uses what exists.

### Fast loop vs daily finance
The B cycle is now the fast loop only (orders, tokens, Order_Master).
The heavy finance/report steps moved to the daily A cycle via A020_run_daily_finance.py.
This keeps B fast while still updating fees, VAT, and reports once per day.

### Streamlined mode (trial)
Current trial setup:
- B cycle runs only the fast loop.
- Daily finance runs once per day in A020.
- Goal: reduce cycle time without losing order accuracy.

### Old system (legacy)
Previous setup:
- B cycle ran everything every loop (orders, tokens, finance, VAT, reports).
- Result: long cycle times, sheet quota issues, slow updates.

### Quiet publish mode (no partial data)
If B_CYCLE_QUIET=1, the cycle runs "silent" and does NOT write sheets mid-run.
At the end of the cycle, it publishes Order_Master and P&L once, in one clean update.
This avoids temporary inflated profit while COGS/fees are still catching up.

Default publish set (minimal to avoid sheet bloat):
- Order_Master
- P&L summary only (P&L_Summary tab)

All detailed logs and large tabs stay local.
P&L publish uses no formatting in B cycle to avoid Sheets quota spikes.

### One-off run (no loop)
If you want a single B cycle run and then stop:
- `B_RUN_ONCE=1 python scripts/run_B_cycle.py`

### Maintenance mode (stop loop safely)
Use this before manual debugging to prevent overlap with background B loop.

Pause loop:
- `New-Item -ItemType File -Force out/locks/b_cycle.maintenance`
- Optional reason:
- `Set-Content out/locks/b_cycle.maintenance "maintenance: ticket work in progress"`

Resume loop:
- `Remove-Item out/locks/b_cycle.maintenance -ErrorAction SilentlyContinue`

Alternative env switch:
- `set B_CYCLE_MAINTENANCE_MODE=1` (cmd) or `$env:B_CYCLE_MAINTENANCE_MODE='1'` (PowerShell)

Loop behavior:
- `run_B_cycle.py` checks maintenance mode before each cycle and before each script.
- When active, it pauses and sleeps, then checks again automatically.
- Sleep interval default is 900 seconds (15 minutes), set by `B_CYCLE_MAINTENANCE_SLEEP_SECONDS`.
- Status message includes `check back in <N> minutes` (default 13, set by `B_CYCLE_MAINTENANCE_ETA_MINUTES`).

### A-B maintenance handoff (cycle-safe)
Goal:
- A cycle has priority, but B must finish the current full cycle first.

Handshake files:
- `out/locks/maintenance.requested` (set by A)
- `out/locks/maintenance.ready` (set by B only at cycle boundary after full cycle completes)
- `out/locks/maintenance.active` (set by A while A is running)

Sequence:
1. A sets `maintenance.requested`.
2. B finishes the current full cycle.
3. B sets `maintenance.ready` and pauses.
4. A waits for `maintenance.ready`, then sets `maintenance.active` and runs.
5. A clears `maintenance.active`, `maintenance.requested`, and `maintenance.ready` at completion.
6. B resumes automatically.

Self-heal:
- At the end of `run_A_all.py`, A now checks whether B is actually running.
- If B is not running and `out/B_cycle.lock` is stale, A clears the stale lock and starts `scripts/run_B_cycle.py`.
- Controlled by env var `A_ENSURE_B_AFTER_A` (default `1`).

---

## System health check (after changes)

Whenever we change logic or see weird behavior, run the system checklist before doing more fixes.
This prevents "whack-a-mole" and gives a single source of truth.

**Run**

`python scripts/A015_build_system_health_check.py`

**What it checks**
- orders_all row count and latest purchase date
- order_items_all row count
- orders missing items in recent window (default 24 hours from latest order date) (FAIL)
- Order_Master row count
- Order_Master row drops vs previous snapshot (WARN)
- blank SKU / blank Date rows in Order_Master
- gap between latest order date and Order_Master date
- blank COGS for lvl 1+ orders
- Level 1 keys missing from Order_Master
- token counts (total / available / allocated)
- token COGS ledger row count
- inventory row count
- recent B cycle failures in the log
- VAT country model present with correct schema (FAIL if missing)
- Fee country model present with correct schema (FAIL if missing)

**Output**
- `out/system_health_checklist.csv`
- `out/health_status.csv` (single-line status; OK/WARN/FAIL)
- Console summary with OK/WARN/FAIL

**Alerts**
- Windows toast notification appears when status changes to FAIL.
- You can snooze toast popups (without hiding checklist FAIL/WARN rows):
- `python scripts/one_off/H001_set_health_alert_snooze.py --minutes 90 --reason "waiting for next cycle"`
- Check status: `python scripts/one_off/H001_set_health_alert_snooze.py --status`
- Clear snooze: `python scripts/one_off/H001_set_health_alert_snooze.py --clear`
- Snooze state file: `out/locks/health_alert_snooze.json`

If any FAIL appears, stop and fix that first.

Run lock note:
- A and B now share a run lock (default `out/run_cycle.lock`). Do not run A and B at the same time.

Health check gate:
- A015 exit code 2 (FAIL) blocks quiet publish in B.
- A015 exit code 1 (WARN) allows publish but prints an alert.
- Split isolation modes (new):
- `B_SPLIT_HEALTH_MODE=legacy|shadow|split` (rollout default is `shadow`)
- `B_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_B_split.csv`
- `legacy`: existing behavior, gate from `checklist_B.csv` (or global fallback).
- `shadow`: keep legacy gate, also run `A015 --profile b` and log legacy vs split decision compare.
- `split`: gate from `checklist_B_split.csv` only and run profile `b` at end of cycle.
- Shadow compare artifacts:
- `out/cycle_alerts/flow_selftest_compare.csv` (one row per cycle compare)
- `out/cycle_alerts/flow_selftest_state.json` (`a_match_streak`, `b_match_streak`, `e_match_streak`, `ready_for_cutover`)
- Automatic cutover:
- When `ready_for_cutover=true`, B auto-switches effective mode from `shadow` to `split`.

Detail output (for investigations):
- out/health_order_master_blank_cogs_lvl1plus.csv (orders missing token COGS)
- out/health_orders_missing_items_window.csv (orders missing items in recent window)
- out/token_shortages_by_sku.csv (per-SKU token shortages from B007)

---

## Definition of Done (Z)

Use this as the measurable end state.

- A015 gate active (FAIL blocks publish).
- Staged publish active (no partial sheet writes).
- 0 FAIL for 10 consecutive runs.
- WARNs are 0 or only on an explicit exception list.
- Token shortage log is 1 line per SKU per run.
- Last 3 publish snapshots are kept for rollback.

---

## 1) Inputs and where they come from

### Amazon API sources
- Orders API -> order headers (Order ID, dates, status, marketplace)
- OrderItems API -> items per order (SKU, quantity)
- Financial Events API (Level 3) -> actual fees/charges when they are available

### Local / Sheet sources
- Token Ledger (Google Sheet) -> token costs and availability
- Inventory snapshot (out/inventory_summaries.csv) -> live stock counts
- Purchase/Orders CSV (Amazon Supplier Process - Orders) -> used by one-off backdating, NOT daily

---

## 2) Script sequence and what each step does

### B001_run_orders_to_sheet.py (Level 1)
Purpose: Pull *new orders* and create Level_1_Immediate.

Outputs:
- out/orders_raw.csv
- out/order_items_raw.csv
- out/financial_events_level1.csv
- Sheet tabs: Orders_raw, OrderItems_raw, Level_1_Immediate

Safety overlap rule (new):
- B001 can be run with an overlap window (using ORDERS_CREATED_AFTER/BEFORE).
- It now skips item fetch calls for orders that already exist in out/order_items_all.csv.
- It always re-fetches items for orders in the retry queue.
- This reduces API calls while still catching missed orders.

What Level 1 contains:
- Sales amounts (Price, VAT, ExVAT)
- Shipping and Gift if available
- Estimated fees (FBA/Commission/DSF estimates)
- COGS fields present but filled by token allocation later

Important: Level 1 is a real-time view. It is not the final truth.

### B002_run_pending_orders_to_sheet.py (Level 2)
Purpose: Pull pending orders and build Level_2_Official (better fees & estimates).

Outputs:
- out/financial_events_level2.csv
- Sheet tab: Level_2_Official

Pending order age rule (important):
- Orders newer than 12 hours are skipped in B002 to avoid re-pulling very fresh orders.
- This is a global min-age filter for all B002 targets.
- Controlled by env var B002_MIN_AGE_HOURS (default 12).

Level 2 dedupe repair:
- If Level_2_Official gets duplicated, run a one-time cleanup:
  - `B002_DEDUPE_ONLY=1 python scripts/B002_run_pending_orders_to_sheet.py`
- This keeps one row per Order ID + SKU and restores normal Level 2 behavior.

### Daily finance step (now in A cycle)
Moved out of B into A020_run_daily_finance.py:
- B003_run_financial_events_level3.py
- B005_run_financial_transactions_v2024.py
- D012_build_fee_vat_ledger.py
- D013_build_vat_report.py
- D016_build_fee_detail_ledger_api.py
- D001_build_pnl_daily.py
- B012_build_token_events_append.py
- B010_build_token_ops_outputs.py
- D018_build_token_batch_report.py
- B013_build_token_weekly_drift.py
- B014_build_token_daily_checklist.py
- B021_build_token_proof_pack.py
- D017_audit_daily_guardrails.py
- D003/D004/D005/D006 transaction ledgers
- B006_build_fx_ledgers.py

### B004_build_order_master.py (single pass per cycle)
Purpose: Combine Level 1 + Level 2 + Level 3 into a single Order_Master view.

Rules:
- If Level 3 exists: use it (most accurate fees and charges)
- Else if Level 2 exists: use it
- Else: use Level 1

COGS in Order_Master:
- If token allocations exist, token costs override any COGS fields.

Performance note:
- Order_Master now runs in incremental mode by default (only updates changed orders).
- Full rebuild can be forced by setting ORDER_MASTER_INCREMENTAL=0 for a single run.
- SKU filter runs now write to out/order_master_sku_preview.csv and do NOT overwrite the main Order_Master.

### B011_recover_l3_orphans.py (self-healing safety)
Purpose: Recover gaps where L3 has keys that are missing from Level 1.

Behavior:
- If out/l3_orphans.csv has rows, it runs a bounded B001 lookback (default 14 days).
- The lookback window is anchored to the latest order date in out/orders_all.csv (not "now").
- Rebuilds Order_Master and reruns A015.
- If orphans remain, it logs a notification to out/orphan_recovery_alerts.csv.
- For backfill, it runs across all marketplaces in out/marketplace_participations.csv.
- Each marketplace B001 call has a timeout so one slow marketplace does not block the full B cycle.
- Timeout/failure marketplace alerts are recorded as `b001_timeout_marketplace_<id>` and `b001_failed_marketplace_<id>`.
- After recovery pulls, B011 runs token allocation and token COGS ledger refresh before rebuilding Order_Master.

Controls:
- ORPHAN_RECOVERY_MAX_DAYS (default 14)
- ORPHAN_RECOVERY_MIN_INTERVAL_MIN (default 60)
- ORPHAN_RECOVERY_BACKFILL_START (one-time full backfill start, example 2025-11-01)
- ORPHAN_RECOVERY_B001_TIMEOUT_SEC (default 900)

This step is safe to run daily and does not change markers (ORDERS_SKIP_MARKER_WRITE=1).

### B012_recover_orphan_order_items.py (targeted orphan recovery)
Purpose: Directly call OrderItems API for orphan Order IDs when Orders API does not return them.

Inputs:
- out/l3_orphans_missing_orders_all.csv (or fallback out/l3_orphans_with_orders_all.csv)

Outputs:
- out/orphan_order_items_recovered.csv
- out/orphan_order_items_failed.csv
- out/order_items_all.csv (append + dedupe)

Use this when l3_orphans_count is still > 0 after backfill.

### B007_allocate_tokens_live.py
Purpose: Allocate tokens to orders using actual available tokens.

Rules:
- Tokens are allocated to orders when orders arrive.
- Newest tokens are reserved for live stock (stock should carry newest costs).
- Orders get the remaining tokens oldest-first (FIFO) after reserving for stock.

Outputs:
- out/token_allocations_live.csv
- out/token_ledger_live.csv
- Sheet tabs: Token_Allocations, Token_Ledger

### Token COGS sync (inside B007)
Purpose: push allocated token costs into Level_1_Immediate so COGS appears immediately.

Effect:
- After B007 runs, Level_1_Immediate rows with token allocations get COGS filled.
- If no token exists, COGS stays blank (no estimation).

### B025_build_token_cogs_ledger.py
Purpose: Build a clean token COGS ledger.

Output:
- out/token_cogs_ledger.csv

Note:
- B004 runs once per B cycle after tokens are allocated.
- If B_CYCLE_QUIET=1, there is a final publish B004 at the end of the cycle to write the sheet once.

---

## 3) Columns in Level_1_Immediate and how they are built

### Sales columns
- Price_Total / Price_VAT / Price_ExVAT
  Source: OrderItems + price lookup
  Note: Price is the listing price at time of pull (not necessarily final payout)

### Shipping columns
- Shipping_Total / Shipping_VAT / Shipping_ExVAT
  Source: Order API if shipping charge exists

### Gift and Promotion columns (Level 1)
- Gift_* and Promotion_* exist but are always 0.00 in Level 1.
- We do not estimate gift or promotion at Level 1.

### COGS columns
- COGS_Total / COGS_VAT / COGS_ExVAT
  Source: Token allocation (after B007)
  Not estimated from Level 2/3 selling price

### Fee columns (Level 1 estimate)
- FBA_Fee_* estimated based on SKU fee table
- Commission_* estimated from listing price
- Digital_Fee_* estimated as 2% of FBA+Commission

These are placeholders until Level 2/3 arrives.

### Margin columns
- Margin_ExVAT and Margin_Pct use:
  Revenue ExVAT - Fee ExVAT - COGS_ExVAT

---

## 4) Level 2 and Level 3

### Level 2 (Official estimate)
- Uses better fee models and sometimes more accurate order-level data.
- Still not final truth.

### Level 3 (Financial Events)
- Actual Amazon payout and fees per order
- If Level 3 exists, Order_Master uses it
- Level 3 locks fees and sales for that order
- If Amazon does not provide unique line IDs, Level 3 de-duplicates identical lines so repeated pulls do not double-count the same amounts.
- When unique IDs are missing, we cap duplicate identical lines using Quantity Ordered from order_items_all so we do not undercount split-quantity orders.

---

## 5) Token allocation rules (how COGS is decided)

### Core rule
- Tokens represent cost of goods (what we paid to buy the product).
- Orders consume tokens one by one in allocation order.

### Stock rule
- Newest tokens stay with stock (future orders should carry newest costs).
- Orders get older tokens after stock reservation.

### If tokens run out
- No COGS assigned (COGS stays blank) until tokens exist.
- This is intentional to avoid guessing.

### Pending orders and COGS (important)
- Pending status does NOT mean we skip COGS.
- If tokens exist, COGS should be allocated even for Pending orders.
- Blank COGS for any lvl >=1 order is a real issue and must be fixed at the token allocation step (B007), not masked.

### Researching / Unsellable / Damaged
- These are not available for sale and should not be counted as available tokens.
- They can be tracked separately (B010 apply delta scripts).

---

## 5b) What is "frozen" after Level 3? (ONGOING)

Short answer: fees and sales are frozen, and COGS should not change in ongoing runs.

- Level 3 makes fees and sales final for that order.
- In ongoing runs, COGS should stay attached to the original order and should NOT be back-edited.
- Refunds are treated as forward events:
  - The original order stays as-is.
  - The refund value is posted on the refund date (not backdated).
  - A return token is created ONLY when the item returns to sellable stock.
  - If the return is unsellable, no token is created.
  - The return token is a duplicate of the original token, keeps the original cost, and is marked as a return (for example by an "R" suffix or a return flag).

Backdating is the only time older COGS can shift, and it is a reset tool for a broken state. It should not be used in normal operations once the system is stable.

### Backdate refund rule
- Backdating does NOT subtract refunds. It uses orders + stock only.

---

## 6) Tax handling (VAT)

### Sales VAT
- Derived from order data (Price VAT or calculated from ExVAT)

### Fee VAT
- Level 1 and Level 2 use estimation.
- Level 3 uses actual fee VAT if present.

### VAT/Fee models are mandatory
- out/vat_country_model.csv and out/fee_country_model.csv must exist.
- A015 fails if either is missing (no optional run).

### COGS VAT
- COGS VAT is now calculated from Product DB VAT rate (last_vat_rate_pct or vat_rate).
- If missing, fallback is 20%.
- Purchase costs are treated as ExVAT; VAT is added to COGS_VAT and included in COGS_Total.

---

## 7) How P&L is built from B outputs

Key inputs:
- Order_Master -> Sales, COGS, Fees
- Financial Events -> extra charges (storage, inbound, refunds)

P&L is accurate only if:
- Tokens are allocated correctly
- Level 3 fees available
- Inventory deltas are applied where needed

---

## 8) What "working" means

A healthy run means:
- New orders appear in Level_1_Immediate
- Tokens allocated after B007
- COGS appear in Level_1_Immediate after B007
- Order_Master shows non-zero COGS where tokens exist
- Fee totals shift from Level 1 -> Level 2 -> Level 3 as data arrives

---

## 9) Common failure points

- Tokens missing: COGS will be blank
- Live inventory snapshot stale: allocation caps wrong
- Level 3 fee ledger empty: VAT report fails
- Sheet size limit: B003/D013 errors

---

## 10) Daily sanity check (fast)

1) Run B001 (Level 1)
2) Run B007 (token allocation)
3) Verify Level_1_Immediate has non-zero COGS for new orders
4) Verify Order_Master shows same COGS

If any step fails, stop and fix the root cause.

---

## 11) One-off rules

- Backdating scripts are NEVER part of the daily B cycle.
- Backdating only used when you explicitly run it.

### Backdater is now one-button end-to-end
When you run the backdater (T028_backdate_tokens_from_live_stock.py), it must:
1) Create tokens
2) Allocate tokens to orders
3) Build token COGS ledger
4) Rebuild Order_Master
5) Update the Order_Master sheet tab (the sheet you pointed at: gid=334537132)

So the backdater is the start AND the end of the backdate. One run, full pipeline, no extra steps.

### SKU-only backdate mode (fast test)
If you set BACKDATE_SKU_FILTER=YOUR-SKU, the backdater will now rebuild Order_Master for that SKU only.
This makes single-SKU tests fast and avoids full history rebuild during testing.

---

## 12) Quick glossary

- Token: cost unit you paid for the SKU
- Allocation: attaching token to an order
- Level 1: fast, minimal data, immediate
- Level 2: improved estimates
- Level 3: real fees and payouts

---

## 13) Owner decisions (explicit)

- No estimation of COGS if tokens missing.
- Tokens must be allocated immediately after orders.
- Newest token costs remain on stock.
- Orders use remaining tokens.

---

## 14) Known open items

- If fee VAT is missing in Level 3, VAT report needs fixing.
- If token allocations drift from inventory, research/unsellable deltas must be applied.

---

## 15) Evidence outputs (where to check)

- out/financial_events_level1.csv
- out/token_allocations_live.csv
- out/token_cogs_ledger.csv
- out/order_master.csv

These must align in order: Level 1 -> tokens -> order master.

---

End.

---

## 15b) Sellerboard comparison notes (for audits)

Use this when comparing Order_Master or order_items_all.csv to Sellerboard exports.

- Sellerboard can drop or net out refunded orders.
- Marketplace facilitator / IOSS orders can show VAT handled by Amazon (net proceeds exclude VAT).
- Sellerboard has a fixed export window. Orders outside that window will not appear.
- Some line items include zero-qty canceled rows. Treat the paid line as the true sale.

When comparing, always apply:
- Exclude refunds on both sides.
- Filter to UK only if you are checking UK orders (ship_country_code = GB).
- Apply the Sellerboard window cutoff (use Sellerboard last order timestamp).

If both systems show the same order totals after the filters above, assume Sellerboard display logic is the difference, not a missing order in our data.

---

## 16) Self-healing development rules (mandatory)

Whenever we add a new phase or script:
1) Add a health check item (A015) that validates it.
2) Add an alert rule (FAIL or WARN) so issues are visible immediately.
3) Add schema checks for any new CSV outputs.
4) Use staged writes (build locally, publish once complete).
5) Ensure the step is idempotent (safe to rerun).

If any of these are missing, stop and add them before continuing.
