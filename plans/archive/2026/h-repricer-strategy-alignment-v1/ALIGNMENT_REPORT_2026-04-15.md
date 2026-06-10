# H Repricer Alignment Report

Date: 2026-04-15

## Scope
- Compare live H repricer behavior against the old research and current plan documents.
- Answer:
- what is on track
- what is off track
- whether H is actually selling off or dropping to break-even
- what the next strategy task should be

## Evidence used
- `out/system_health_checklist.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/systems/H/live/h110_sku_lifecycle_log.csv`
- `out/systems/H/live/h110_sku_decision_log.csv`
- `out/listing_offer_seller_snapshot_latest.csv`
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md`
- `out/process_guides/repricing_tool/deep-research-report.md`

## Executive summary
- Stability is good enough to do strategy work now.
- The live repricer is not yet aligned with the full plan.
- Today it behaves mostly like a one-rival engine with strong floor protection, not like a finished ladder-aware repricer.
- Suppression architecture exists, but the current live window shows very little real suppression recovery movement.
- Sell-off behavior exists in code, but it is barely active in live evidence.
- Your race-to-the-bottom concern is valid: current regain logic does not distinguish one rival from a crowded seller ladder.

## 1. What needs to get on track

### 1.1 Multi-seller logic is missing from live price choice
- In current code, `REGAIN` moves directly to the best rival price and `RAISE_FIND_LOSS` moves upward to ceiling.
- The decision engine does not use seller-count or ladder-depth inputs when choosing between reset, hold, or chase.
- Current live evidence confirms the gap:
- active floor snapshot rows: 89
- `REGAIN` rows: 55
- `REGAIN` rows with 2 or more sellers in the latest seller snapshot: 44
- `REGAIN` rows with applied live writes and 2 or more sellers: 21
- This means H is often using a one-rival tactic in clearly multi-seller markets.

### 1.2 Suppression is present, but the recovery loop is not proving success
- Active floor snapshot rows in `SUPPRESSED_ASIN`: 49 out of 89.
- Active strategy states in `STATE_SUPPRESSION_REACTIVATION`: 6.
- In the recent finish-event window from 2026-04-14 onward:
- suppressed rows observed: 34
- suppressed rows with `APPLIED`: 0
- suppressed rows with `NO_WRITE_REQUIRED`: 34
- So suppression logic is present, but current live evidence is mostly "recognized and held", not "recovered and measured."

### 1.3 Strategy observability is not decision-grade yet
- `out/h_ceiling_events.csv` is missing.
- `out/phase1_strategy_monitor.csv` is stale and no longer suitable as the main strategy view.
- `out/h_suppression_cases.csv` and `out/h_suppression_reactivation_log.csv` exist, but key target fields are blank across current rows.
- The floor snapshot is the best current truth source, but it is still not the full success view.

### 1.4 Sell-off policy is under-evidenced in live use
- The plan talks about:
- Phase 2 margin compression
- Phase 3 controlled exit
- Phase 4 liquidation
- Current active strategy-state evidence shows:
- `REGAIN`: 55
- `RAISE_FIND_LOSS`: 21
- `STATE_SUPPRESSION_REACTIVATION`: 6
- `CONTROLLED_EXIT_TO_FLOOR`: 1
- `LIQUIDATE_TO_FLOOR`: 0
- So the sell-off path exists structurally, but it is not yet a strong live operating mode.

## 2. What about the plan is working

### 2.1 Hard-floor protection is working
- The current runtime is clearly floor-protected.
- In the latest floor snapshot:
- 44 rows are at or below the current floor target
- many `REGAIN` writes show `GUARDRAIL_HARD_FLOOR_CLAMP`
- This matches the root rule that H should not blindly chase below protected levels.

### 2.2 Phase and suppression states are wired into live outputs
- The runtime can already emit:
- `REGAIN`
- `RAISE_FIND_LOSS`
- `STATE_SUPPRESSION_REACTIVATION`
- `CONTROLLED_EXIT_TO_FLOOR`
- suppression temp ceiling fields
- suppression threshold memory fields
- So the repo is not missing the concept layer. The gap is mainly in completion and measurement.

### 2.3 Health and freshness evidence are good enough for planning
- Latest H health checks inspected were OK.
- H cycle freshness, publish marker freshness, floor snapshot freshness, and schema checks are all present in the latest checklist.
- That means strategy work is not blocked by a live H hard-fail condition.

## 3. What about the plan is not working

### 3.1 Live behavior is still closer to v1.3 than to v10
- `strategy-steps-v1.3.md` still describes the live contract.
- `masterplan_v10.md` expects:
- separate compliance, eligibility, and demand ceilings
- stronger suppression outputs
- ceiling events
- strategy-grade measurement
- The live runtime has some of these fields, but not the full operational contract.

### 3.2 The repricer is still mostly reacting, not evaluating scenario quality
- Recent finish events from 2026-04-14 onward:
- total finish rows: 795
- `APPLIED`: 252
- `NO_WRITE_REQUIRED`: 404
- classified action reasons:
- `REGAIN_TO_RIVAL`: 383
- `RAISE_FIND_LOSS_UP`: 128
- `SUPPRESSION_PROBE_DOWNWARD_STEP`: 11
- `CANNOT_COMPETE_FLOOR_SEEK_STEP`: 3
- This is a clear signal that most live activity is still "regain the lost buy box or try to raise again", not richer strategy branching.

### 3.3 Suppression outputs are not yet useful enough for operator review
- Current active suppression rows show important fields in the floor snapshot.
- But the dedicated suppression case logs are not yet carrying the same truth cleanly.
- That means the runtime knows more than the operator-facing files currently reveal.

## 4. Has H decided to sell anything off?

### Short answer
- Yes, but only in a very limited way.

### Evidence
- One active row is currently in `CONTROLLED_EXIT_TO_FLOOR`: `LR-7GM6-1RCH`.
- I did not find active `LIQUIDATE_TO_FLOOR` rows in the latest floor snapshot.
- Recent finish-event evidence shows only 3 rows with `CANNOT_COMPETE_FLOOR_SEEK_STEP`.

### Interpretation
- The sell-off path exists.
- It is not yet a broad live behavior.
- Today H is mostly trying to regain or probe upward, not broadly moving weak SKUs into exit logic.

## 5. Has H dropped anything to break-even?

### Short answer
- Yes, a small number of active rows are already at or below break-even.

### Evidence from the latest floor snapshot
- Active rows at or below break-even: 5
- SKUs visible in that condition:
- `0G-JB6S-PN34`
- `A1-KSU1-GZMS`
- `AX-NKNU-29C1`
- `D0-C7C0-H6LN`
- `VL-48KZ-J3F2`

### Interpretation
- Break-even or below-break-even pricing is happening, but it is not yet a clearly measured, reason-coded sell-off program.
- Most of these rows sit inside suppression or floor-conflict logic rather than a mature "planned exit" framework.

## 6. Race-to-the-bottom risk assessment

### Current risk
- Real and current.

### Why
- The live decision engine mainly uses the single best rival price.
- It does not distinguish:
- one cheap rival with room above
- two-seller ladder with a sensible cap
- a crowded ladder where matching the bottom just shares the pain

### What the logic should do next
- If one competitive rival exists and the next rung is materially higher:
- allow a reset test toward the ceiling or the next valid rung
- hold for a reset window before chasing again
- If two or more competitive rivals exist:
- do not jump to max ceiling and hope
- cap the raise at the second-lowest or cluster edge
- avoid auto-undercut loops that only split the buy box three ways
- If we are being undercut repeatedly:
- add a hold window and retry budget
- stop blind matching when repeated undercuts show no buy-box gain or no price rebound

## 7. Recommended next task
- Create the next implementation ticket as:
- `H repricer strategy completion - ladder-aware reset, undercut guard, and measurable outputs`

### Must-have scope
- add seller-ladder scenario classification
- split one-rival reset from multi-seller ladder behavior
- add undercut response windows and retry budgets
- define explicit success outputs for tactic quality
- activate missing ceiling-event output

### Suggested outputs
- `out/h_ceiling_events.csv`
- `out/h_strategy_outcome_log.csv`
- `out/h_strategy_outcome_daily.csv`

### Suggested success fields
- `sku`
- `scenario_type`
- `seller_count`
- `lowest_price_1_gbp`
- `lowest_price_2_gbp`
- `lowest_price_3_gbp`
- `chosen_tactic`
- `target_price_gbp`
- `hold_until_utc`
- `retry_budget_remaining`
- `buy_box_state_before`
- `buy_box_state_after`
- `writer_outcome`
- `reason_codes`

## Bottom line
- H is stable enough.
- H is not yet strategy-complete.
- The next real problem is not "can it run?" but "is it choosing the right tactic for the market shape?"
- The highest-value next step is ladder-aware logic plus decision-grade outputs.
