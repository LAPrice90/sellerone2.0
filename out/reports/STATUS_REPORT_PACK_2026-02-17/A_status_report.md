# Status Report - Masterplan v9 - 2026-02-17 UTC

## 1) Scope and purpose
This report is a full status snapshot of the repricing program based on:
- out/process_guides/repricing_tool/master plans/masterplan v9.md
- out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md
- live execution evidence in data/ and out/

It is designed to answer:
- what has been implemented
- what is working in live pilot data
- what is still missing for scale
- what data is required next for Head, Supervisor, and Buy Box correlation

## 2) Your words (verbatim)
I want you to create a status report from our plan can you also include on the report my words here and some data setss to work with put them on a file(a) and put them in a folder easy to find. we started working on out\process_guides\repricing_tool\master plans\masterplan v9.md but we needed to drip feed it through to collect data as a lot of factors are depending on data... we ran phase1 in out\process_guides\repricing_tool\master plans\masterplan v9.md and a fw things we're not ideal in practice so we've chipped away with changes... we are currently running a single SKU on live data, we ran it overnight and dispite accidentally leaving profit protector pro on and the the two systems fought eachother over night it looks like its working effectiely. I'm in the process of rolling out data colelcting on all our listings we have, essentially filling in our "heads" job across the board, with the idea that he looks at our full set of data, he picks from the listings that actually have stock not to waste time looking to reprice stock we dont have, one course of confusing is the CPT price, we set the ceiling price as the minimum between CPT*1.2 or max sold price. so do we call CPT daily/weeks or whatever on all our listings with A cycles? So it can help with not just this but restocking as well, we if the max price is only 12% roi we may decide we dont want to restock despite it scraping through with the minimum ROI. it will then use the calcuations used in the current 12 products to calculate 10% ROI (for now) to set a floor, we will have to look at what to set this as day to day because sometimes we are paying long term storage fees on products we cant sell, we just need to get rid of stuff to gain back the capital tied up etc so the product can be binned off, or we may decide to increase the minumum if certain suppliers tend to have higher return rates on certain categories so we may start new products on a higher roi floor than others to test returns before adjusting etc... finally I dont think we have anything data wise to do anything with our 'supervisor' so I would appriciate a large in depth report on our system, what we have done, what the long term plan is, what data we need to move forward, what have I said here thats not covered in our masket plan etc... I also dont think we're taking in buy box win % to tie in to our repricing data so that would be good to get in the next phase... we need to decide on when and how to use the data to corrilate to our buy box calcuations, maybe we have a % idea by checking every 15m we can see how frequently we get the box... we need solid ideas on when sharing and not sharing is ok... leave no stone unturned here we need this report to be a window to what our process does so we can plan effectively.

## 3) Executive status
- Phase 1 implementation status: complete in the execution tracker (Tasks 1 to 8 marked DONE).
- Live pilot status: active on single SKU L1-54EX-56YC.
- Current health snapshot: 127 checks ok, 0 non-ok in out/system_health_checklist.csv.
- Latest health status row: 2026-02-17T10:32:43.619473+00:00 status=OK fail_count=0 warn_count=0.

## 4) Alert (must not ignore)
Alert:
- out/H_cycle.log contains repeated daily_intel missing for today events.
- Count: 191 events.
- First seen: 2026-02-13T15:58:41Z.
- Last seen: 2026-02-17T10:23:10Z.
- This means H-cycle is repeatedly running with incomplete A-cycle daily intel coverage.

Suggested fix:
- Root-cause level: guarantee daily intel coverage for all active pilot SKUs before H-cycle execution.
- Operationally: make A016 daily intel refresh part of the daily pre-H gate, and gate H-cycle to defensive_hold for SKUs missing same-day intel.
- Evidence file: dataset_07_h_cycle_daily_intel_missing_events.csv.

## 5) Live pilot evidence (L1-54EX-56YC)
Execution log window:
- first event: 2026-02-16T17:13:17Z
- last event: 2026-02-17T10:21:47Z
- rows: 63

State mix:
- REGAIN: 47
- RAISE_FIND_LOSS: 16

Write status mix:
- WRITE_NOT_APPLIED: 28
- APPLIED: 26
- NO_WRITE_REQUIRED: 9

Overnight window check (2026-02-16T20:00:00Z to 2026-02-17T08:00:00Z):
- execution rows: 45
- snapshots eligible for buy box outcome: 45
- our featured wins: 10
- overnight buy box win rate: 22.22%

External write contention signal:
- Detected 5 large old-price jump events (abs(jump) >= 0.30) before decision rows.
- These events are consistent with your note that another repricer was still active.
- Evidence file: dataset_08_l1_external_price_jump_events.csv.

## 6) What has been done vs plan
From phase_1_execution_plan.md:
- Storage adapter: DONE
- Market snapshot processor: DONE
- DVE layer: DONE
- Ceilings: DONE
- Probe engine: DONE
- Write and verify: DONE
- OAS hard-fail layer: DONE
- Main loop wiring: DONE

Plan updates already captured in tracker:
- CPT moved to pin-and-observe behavior.
- CPT no longer treated as a direct max-price clamp in Phase 1.

## 7) Long-term plan (from masterplan v9, simplified)
Current position:
- You are operating Stage A style pilot behavior with live single-SKU learning.

Planned path to scale:
1. Stage B - hard three-ceiling enforcement across expanded SKU set.
2. Stage C - profit-led decision layer as default behavior.
3. Stage D/E - pressure recommendation only, then manual case workflow.
4. Stage F - daily eligibility intelligence as reliable baseline.
5. Stage G/H - demand ceiling learning and DVE correction with strict admissibility.
6. Stage I - event-led runtime hardening before broad expansion.

## 8) Data you need next to move forward
Priority data blocks:
1. Daily intel coverage table for all active SKUs
- fields: SKU, FOEP status, CPT status/value, eligibility source, confidence, refresh timestamp.
- reason: removes blind H-cycle operation.

2. Stock-gated Head candidate table
- fields: SKU, available, inbound, total quantity, in-stock flag, ROI floor profile.
- reason: Head only spends cycles on sellable stock.

3. Buy box win-rate time series at 15-minute cadence
- fields: SKU, snapshot_ts, has_our_offer, winner_known, our_featured_win, our-vs-winner price gap.
- reason: gives Supervisor real conversion/competitiveness evidence.

4. ROI floor profile table by supplier/category
- fields: SKU, supplier, category, floor_roi_pct, return_rate_band, storage-pressure flag.
- reason: dynamic floor control for exit/liquidation vs hold strategy.

5. Restock decision overlay with ceiling realism
- fields: SKU, max feasible ceiling, projected ROI at ceiling, restock_yes_no, reason code.
- reason: stops reordering low-upside items that only scrape minimum ROI.

## 9) Coverage check - what you said that is not fully covered in masterplan yet
Already covered in v9:
- CPT as risk telemetry, not automatic hard demand ceiling.
- Head and Supervisor role separation.
- event-led runtime with heartbeat fallback.
- three-ceiling model and hard floor rule.

Partially covered or missing in implementation data:
- Full stock-gated Head process across all listings (design exists, rollout data pipeline not complete).
- Supplier/category-specific dynamic ROI floors (conceptual fit exists, table and policy not fully implemented).
- Supervisor evidence pack tied to buy box win-rate by time bucket (not yet first-class in current outputs).
- Clear rules for when sharing buy box is acceptable vs when to avoid sharing (needs explicit policy matrix).

## 10) CPT cadence recommendation (answer to your cadence question)
Recommended:
1. Run CPT/FOEP daily for all active sellable SKUs in A-cycle.
2. Run weekly CPT/FOEP refresh for non-active catalog SKUs.
3. Promote to daily for non-active SKUs that are candidates for restock, high-margin, or currently unstable.

Why this cadence is practical:
- Daily on active items supports repricing and restock decisions.
- Weekly on inactive items controls API and runtime cost while keeping baseline intelligence fresh.

## 11) Buy box win-percent integration design for next phase
Use data/offer_snapshot_facts.csv as the source of truth.

Proposed formula per SKU per day:
- Eligible snapshots = snapshots where has_our_offer=1, winner_known=1, unknown_outcome=0.
- Wins = eligible snapshots where is_our_offer=1 and is_featured_offer_winner=1.
- Win rate % = wins / eligible snapshots.

Decision use:
- Low win rate + healthy margin room -> allow controlled share actions.
- High win rate + weak margin -> allow margin harvest up toward ceiling.
- Low win rate + low margin room -> hold/defend, avoid aggressive price cuts.

## 12) Sharing vs not sharing - practical policy draft
Share the Buy Box when:
- you are still above hard floor and above required ROI floor
- share improves expected daily profit vs strict win-only mode
- competitor behavior is stable enough for admissible learning

Do not share (defend or hold) when:
- sharing drops below hard floor or required ROI floor
- competitor is structurally stronger and share would cause anchor damage
- stock is thin and value capture is better than unit chase
- outcome data quality is poor (unknown outcome windows)

## 13) Stock-gated Head rollout status
Current evidence (2026-02-17 snapshot join):
- listing rows in H snapshot: 12
- in-stock Head candidates: 12
- candidate source file: dataset_03_listing_stock_gate_2026-02-17.csv

Portfolio-wide inventory context:
- total inventory rows: 336
- rows with available > 0: 61
- rows with available = 0: 275

## 14) Files in this report pack
Main files:
- A_status_report.md - this full report
- A_dataset_index.md - quick map of all datasets

Datasets:
- dataset_01_l1_execution_log_full.csv
- dataset_02_l1_execution_log_overnight.csv
- dataset_03_listing_stock_gate_2026-02-17.csv
- dataset_04_buy_box_win_rate_by_sku.csv
- dataset_05_l1_buy_box_timeline.csv
- dataset_06_health_status_last_48h.csv
- dataset_07_h_cycle_daily_intel_missing_events.csv
- dataset_08_l1_external_price_jump_events.csv

## 15) Immediate decision list
1. Confirm CPT cadence policy: daily active + weekly inactive.
2. Confirm buy box win-rate KPI definition above.
3. Confirm Head stock gate rule (available > 0) as default.
4. Confirm dynamic ROI floor policy dimensions (supplier, category, storage pressure).
5. Confirm Supervisor evidence pack format and threshold rules for share vs no-share.
