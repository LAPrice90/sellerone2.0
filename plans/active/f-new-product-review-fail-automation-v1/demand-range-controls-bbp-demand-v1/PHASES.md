# Phases

## Phase 1 - Build Audit
- Status: planned
- Goal:
  - Create a read-only audit that compares Amazon visible demand range against BBP and backtest demand.
- Allowed files:
  - `scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`
  - `tests/test_f023_build_demand_range_bbp_conflict_audit.py`
  - this plan folder
- Outputs:
  - `out/analysis_reports/f_demand_range_bbp_conflict_audit_latest.csv`
- Proof:
  - tests pass
  - audit output exists
  - `B0C8C3JF9X` appears in `amazon_blank_bbp_high`

## Phase 2 - Threshold Review
- Status: planned
- Goal:
  - Decide the actual hard-fail and manual-review thresholds.
- Inputs:
  - Phase 1 audit output
- Review questions:
  - Is Amazon blank plus BBP over 49 always a hard fail?
  - Is Amazon `50+` plus BBP over 250 always a hard fail?
  - Should Amazon `50+` plus BBP 101-250 be warning or manual review?
  - Should UK reviews under 6 be an absolute fail or confidence reducer?
- Proof:
  - sample rows reviewed
  - final threshold decision recorded in this folder

## Phase 3 - Triage Integration
- Status: planned
- Goal:
  - Add accepted demand conflict codes into F021 triage output.
- Allowed files:
  - `scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - `tests/test_f021_build_new_product_review_fail_triage.py`
- Proof:
  - F021 output includes accepted rule codes
  - no unclassified rows
  - no queue writes

## Phase 4 - Upstream Root Fix
- Status: planned
- Goal:
  - Move accepted demand rules to the earliest correct owner path so affected products do not enter clean Pass.
- Candidate owner paths:
  - pass review pack builder
  - backtest qualification layer
  - shared pass logic if that is the earliest source of the incorrect pass decision
- Proof:
  - clean Pass count changes for affected rows
  - affected rows move to fail or review lane with explicit reason
  - no downstream masking

## Phase 5 - Optional Seller Stock Evidence
- Status: parked
- Goal:
  - Capture seller stock count only if it is available through an approved scanner or targeted rescan path.
- Current state:
  - seller stock count is not stored in current pass, near-miss, or scrape evidence artifacts.
- Proof:
  - scoped rescan or scanner output writes seller stock count
  - any stock-count rule uses stored evidence only

