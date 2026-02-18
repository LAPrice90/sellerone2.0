# Head of Sales Manager — Phased Implementation Plan (Codex Runbook)

Purpose: Build a “Head of Sales” advisory layer that **never changes prices**.
It reads existing outputs and produces **guidelines** (min, max, posture, reasons) for store managers.

Non-negotiables:
- Read-only on Amazon (collect pricing/competition data is fine; no price updates).
- Output is advisory only.
- Explainable outputs (reason codes + review triggers).
- Start with training set scope (10 SKUs).

---

## Phase 1 — Create the Head of Sales output (skeleton)

### Goal
Create a new output file that store managers can read.

### Output (new file)
`out/hos_guidelines_snapshot_YYYY-MM-DD.csv`

### Required columns
- `asof_date, marketplace, sku, asin`
- `our_price_gross, buy_box_price_gross, buy_box_price_used_gross, buy_box_channel`
- `lowest_fba_price_gross, lowest_fbm_price_gross, offer_count_fba, offer_count_fbm`
- `current_token_cost_gbp, break_even_price_gbp, expected_refund_cost_per_unit_gbp`
- `roi_at_our_price_pct, roi_at_buy_box_price_pct`
- `min_price_gross, max_price_gross`
- `posture` (compete / hold / step_back / investigate)
- `reason_codes` (pipe-separated)
- `review_triggers` (pipe-separated)
- `notes`

### Codex prompt
> Implement Phase 1 output file creation.
> - Do not change any existing outputs.
> - Read the latest `out/listing_offer_snapshot_*.csv` + `out/sku_performance_summary.csv`
> - Join by SKU (normalize: strip + uppercase).
> - Write the new `out/hos_guidelines_snapshot_YYYY-MM-DD.csv` with the required columns.
> - Fill everything you can; leave blanks if not available.
> - Print: row count + 3 sample rows.

---

## Phase 2 — Add the **minimum price** rule (10% ROI floor)

### Goal
Compute the **minimum allowed price** so store managers never price below your policy floor.

### Business rule (plain)
Minimum price is the lowest gross price that still gives **at least 10% ROI**.

### Mechanics (Codex already has economics)
- Use `current_token_cost_gbp`, `break_even_price_gbp`, and VAT rate logic already present in E.
- Add a 10% ROI uplift on cost:
  - `min_exvat = break_even_exvat + 0.10 * current_token_cost_gbp`
  - `min_gross = min_exvat * (1 + vat_rate_pct/100)`
- If cost is missing (should not happen now): set `min_price_gross` blank and add `reason_codes=missing_cost`.

### Codex prompt
> Implement Phase 2 minimum price rule in the HOS output.
> - Add `min_price_gross` for every SKU row.
> - Add `reason_codes` entry when min price cannot be computed.
> - Print: count of rows where min_price_gross is blank (should be 0 for training SKUs).

---

## Phase 3 — Add the **maximum price** rule (Buy Box suppression ceiling)

### Goal
Compute a conservative **max price** so we don’t go too high and lose Buy Box eligibility.

### Business rule (plain)
Maximum price is the smallest of:
1) A “Buy Box suppression ceiling” anchored to the current Buy Box price
2) A manual/known historical “max sold” ceiling (optional now)

### Version 1 (no historical max yet)
- Use Buy Box anchor:
  - `suppression_buffer = 1.15` by default
  - `max_gross = buy_box_price_used_gross * suppression_buffer`
- If Buy Box missing:
  - Use fallback already used in economics: history -> lowest_fba -> our_price
  - If still missing: leave max blank and set posture=investigate.

(We will refine buffer logic later using evidence; V1 is a conservative placeholder.)

### Codex prompt
> Implement Phase 3 max price rule in the HOS output.
> - Add `max_price_gross = buy_box_price_used_gross * 1.15`
> - If buy box is missing and fallback was used, add reason code `buy_box_fallback_used`.
> - If no price exists after fallbacks, set posture=investigate and include trigger `missing_market_price`.
> - Print: how many rows used buy box fallback.

---

## Phase 4 — Add posture + revisit triggers (store manager guidance)

### Goal
Give store managers a simple instruction: match/hold/step back, and when to revisit.

### Posture rules (starter set)
- If `roi_at_buy_box_price_pct` is blank → `investigate` (missing market price coverage)
- Else if `roi_at_buy_box_price_pct < 10` → `step_back` (policy not met at Buy Box)
- Else → `compete` (safe to match Buy Box within bounds)

### Review triggers
- If `buy_box_price_used_gross < min_price_gross` → add `buy_box_below_floor`
- If `buy_box_price_used_gross > max_price_gross` → add `buy_box_above_ceiling`
- If `offer_count_fba` increases materially (later; for now just record counts)
- If buy box missing → add `buy_box_missing`

### Codex prompt
> Implement Phase 4 posture and triggers.
> - Fill `posture`, `reason_codes`, and `review_triggers`.
> - Keep rules simple and explainable.
> - Print: posture distribution for training SKUs (counts of compete/hold/step_back/investigate).

---

## Phase 5 — Test output (required proof)

### Goal
Prove the manager is producing usable guidance without touching pricing.

### What to run
- Run the existing collection path for offers (training set scope) so snapshot is fresh.
- Run E cycle so `sku_performance_summary` is fresh.
- Generate `hos_guidelines_snapshot_YYYY-MM-DD.csv`.

### Required console proof
1) `hos_guidelines_snapshot_YYYY-MM-DD.csv` created
2) Row count equals listing snapshot rows (expected 10 in training scope)
3) For training SKUs:
   - `min_price_gross` filled count = 10
   - `max_price_gross` filled count >= 7 (buy box may be missing; fallback should cover most)
   - `posture` exists for all 10
4) Print 3 sample rows including:
   - a SKU with Buy Box present
   - a SKU where buy box fallback was used
   - a SKU where posture is `step_back` (if none, force one by temporarily setting buy box below min in a test harness only — no production changes)

### Example test output (shape)
- sku=6V-EEC1-2S9Z, min=..., max=..., buy_box=7.99, posture=compete, reasons=fba_parity|roi_ok, triggers=
- sku=AX-NKNU-29C1, min=..., max=..., buy_box_used=lowest_fba, posture=investigate, reasons=buy_box_missing|fallback_used, triggers=buy_box_missing
- sku=JB-RGB6-LZOJ, min=..., max=..., buy_box=6.15, posture=compete, reasons=roi_ok, triggers=

### Codex prompt
> Run Phase 5 test proof and print the required proof lines exactly.
> Confirm no price update endpoints are called and no write APIs exist in this flow.

---

## Notes / next expansions (do not implement yet)
- Add “historical max sold” as an optional max cap when you start product vetting inputs.
- Replace fixed suppression buffer (1.15) with evidence-based buffer bands later.
- Expand offer collection scope from training -> active only when you want ROI coverage beyond 10.
