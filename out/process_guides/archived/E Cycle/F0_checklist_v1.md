# F0 Checklist v1 (Daily)

Use this checklist daily. Keep it short and strict.

---

## A) Run E (decision layer)

- [ ] A/B cycles already ran and health is OK
- [ ] E001 ran and wrote sku_sales_velocity.csv
- [ ] E003 ran and wrote sku_restock_signals.csv
- [ ] E004 ran and wrote sku_performance_summary.csv
- [ ] E produced e_decision_log.csv and e_run_log.jsonl
- [ ] Row counts recorded
- [ ] Spot checks done (fast/slow/non-UK)

## B) Capture H snapshot (training SKUs only)

- [ ] listing_offer_snapshot_YYYY-MM-DD.csv saved
- [ ] listing_offer_history.csv appended (or updated idempotently)
- [ ] Source tagged (SPAPI / BBP)
- [ ] Manual export used only with explicit approval (one-off, not daily)
- [ ] Any obvious listing anomalies noted (hazmat delivery, suppressed box, etc.)

## C) F0 decisions (5-10 SKUs only)

For each training SKU:
- [ ] Stock gate checked (days_of_cover vs inbound)
- [ ] Value checked (units/day and stock posture only for now)
- [ ] Forward ROI checked from E fields (roi_at_our_price_pct / roi_at_buy_box_price_pct)
- [ ] State chosen (COOPERATE / PROBE / PRESSURE / STARVE / DEFENSIVE / LIQUIDATE / HIBERNATE)
- [ ] PPP configured OR manual override applied
- [ ] Decision logged (same day)

## D) Next-day outcomes

- [ ] Yesterday's decisions reviewed
- [ ] Outcomes logged (units, buy box change if known, price movement)
- [ ] Any new scenario added to notes

End.
