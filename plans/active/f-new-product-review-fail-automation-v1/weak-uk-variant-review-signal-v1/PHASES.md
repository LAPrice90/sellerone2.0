# Phases

## Phase 1 - Build Audit
- Status: planned
- Goal:
  - Create a read-only UK review signal audit from current stored evidence.
- Output:
  - `out/analysis_reports/f_uk_review_signal_audit_latest.csv`

## Phase 2 - Triage Integration
- Status: planned
- Goal:
  - Add UK review signal columns into F021 triage.

## Phase 3 - F019 Upstream Routing
- Status: planned
- Goal:
  - Route `uk_reviews_lt3` and `uk_reviews_3_to_5` rows before clean Pass pack write.

## Phase 4 - Optional Evidence Upgrade
- Status: parked
- Goal:
  - Use propagated parent/global/matching-variant review fields only after a scoped evidence run proves they exist in live scrape evidence.

