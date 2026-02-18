# Dataset Index - STATUS_REPORT_PACK_2026-02-17

1. dataset_01_l1_execution_log_full.csv
- Source: data/execution_log.csv
- Filter: sku = L1-54EX-56YC
- Rows: 63

2. dataset_02_l1_execution_log_overnight.csv
- Source: data/execution_log.csv
- Filter: sku = L1-54EX-56YC, timestamp in overnight window
- Window: 2026-02-16T20:00:00Z to 2026-02-17T08:00:00Z
- Rows: 45

3. dataset_03_listing_stock_gate_2026-02-17.csv
- Source: out/listing_offer_snapshot_2026-02-17.csv + out/inventory_snapshot_2026-02-17.csv
- Purpose: Head candidate list using in-stock gate
- Rows: 12

4. dataset_04_buy_box_win_rate_by_sku.csv
- Source: data/offer_snapshot_facts.csv
- Purpose: buy box win-rate baseline by SKU
- Rows: 12

5. dataset_05_l1_buy_box_timeline.csv
- Source: data/offer_snapshot_facts.csv
- Filter: sku = L1-54EX-56YC
- Purpose: per-snapshot win timeline and price gap
- Rows: 63

6. dataset_06_health_status_last_48h.csv
- Source: out/health_status.csv
- Purpose: recent health trend including WARN windows
- Rows: 359

7. dataset_07_h_cycle_daily_intel_missing_events.csv
- Source: out/H_cycle.log
- Purpose: repeated daily_intel missing evidence
- Rows: 191

8. dataset_08_l1_external_price_jump_events.csv
- Source: data/execution_log.csv
- Purpose: detect possible external writer interference
- Rows: 5
