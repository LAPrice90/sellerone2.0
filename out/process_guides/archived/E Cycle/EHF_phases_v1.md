# Phases v1 - E + H + F (Starting at F0)

This file is the roadmap. Each phase has clear entry/exit gates.
Current focus: Phase 1 only. Phases 2-6 are FUTURE ONLY unless explicitly approved.

---

## Phase 1 - Stabilize E (facts + logs)

Goal:
- E outputs are trustworthy and repeatable.

Work:
- E velocity windows stable (7/30/90 + blended placeholder)
- Restock signals stable (no behaviour change yet)
- e_run_log and e_decision_log produced every run

Exit gate:
- 10 consecutive runs with:
  - 0 FAIL
  - WARNs only on known exceptions
  - spot checks match expectations

---

## Phase 2 - Add value metrics (value over volume) [FUTURE ONLY]

Goal:
- Prioritization uses profit/day, not units/day.

Work:
- profit_per_unit_gbp_30d computed
- value_velocity_gbp_per_day computed
- these appear in sku_performance_summary and decision logs

Exit gate:
- value metrics populated for most selling SKUs
- blanks are explained by reason codes (no silent gaps)

---

## Phase 3 - Build H (daily offer history for training set) [FUTURE ONLY]

Goal:
- Decisions have market context (buy box price range, volatility, BSR trend).

Work:
- config/f_training_set.csv created (5-10 SKUs)
- H001 captures daily snapshots for those SKUs via SP-API (training set only)
- listing_offer_history.csv maintained with schema checks
- optional: backfill from BBP/Keepa exports (training set only)
- manual exports are emergency one-off only and must never run in daily loops

Exit gate:
- At least 14 days of history for the training set
- snapshot and history files are consistent and readable

---

## Phase 4 - Operate F0 (manual pricing manager) [FUTURE ONLY]

Goal:
- You act as F for training SKUs using E + H.

Work:
- Daily decisions logged for each training SKU
- Outcomes logged next day
- Weekly review produces 3-5 repeated scenario patterns

Exit gate:
- 30-50 decision/outcome pairs recorded
- at least 3 repeated patterns are written as rules (not just stories)

---

## Phase 5 - Promote to F1 (system suggests, human approves) [FUTURE ONLY]

Goal:
- Reduce manual load without increasing risk.

Work:
- F suggestion script outputs:
  - recommended state
  - recommended price band
  - reason codes
- Human approves and executes via PPP/manual

Exit gate:
- Suggested actions match your manual calls most of the time
- Misses are explainable and lead to rule updates

---

## Phase 6 - F2 (automate execution for a subset) [FUTURE ONLY]

Goal:
- Automatic execution for a small, safe subset of SKUs.

Work:
- F applies price updates via your chosen actuator (PPP or your own API calls)
- Hard guardrails enforced (profit floors, stock gates, max durations)
- Full logging and rollback

Exit gate:
- Automation runs without surprises for 30 days on the subset

End.
