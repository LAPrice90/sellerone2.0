# Execution Batch 001

## Purpose
- One-sentence outcome for this batch:
  - build the overlap expansion pack so the zero-overlap problem becomes a controlled routing task instead of a vague blocker

## Scope guardrails
- Only do:
  - overlap pack and summary builders
  - targeted tests for the overlap builder
  - plan-doc updates needed for Batch 001 proof
- Do not change:
  - H runtime logic
  - F scrape ownership
  - Google Sheets or local DB
- Do not add:
  - a new scraper path
  - live strategy logic changes

## Files allowed to change
- `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- `tests/test_hf_scope_expansion_candidates.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `PLAN.md`
- supporting files:
  - `RESEARCH_REPORT_2026-04-18.md`
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
  - `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
  - `out/reports/hf_learning_operator_report_latest.csv`

## Tasks
### Task 1
- Goal:
  - create the candidate-level overlap recovery pack
- Files:
  - `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- Notes:
  - preserve current zero-overlap proof and route rows into explicit recovery buckets

### Task 2
- Goal:
  - create the summary file and make owner-path routing explicit
- Files:
  - `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- Notes:
  - output must name the current capture owner path and must not invent a new one

## Tests
- Command:
  - `python -m py_compile scripts/one_off/HF010_build_scope_expansion_candidates.py tests/test_hf_scope_expansion_candidates.py`
  - `pytest tests/test_hf_scope_expansion_candidates.py tests/test_hf_learning_foundation.py tests/test_hf_learning_alignment.py -q`
- Expected result:
  - compile passes
  - targeted tests pass
  - two reruns produce the same counts and route buckets

## Monitoring plan
- Live proof needed:
  - `no`
- Forced proof window:
  - `n/a`
- Artifacts to poll:
  - `n/a`
- Poll cadence:
  - `n/a`
- Success threshold:
  - overlap candidate and summary outputs exist with deterministic counts
- Timeout rule:
  - stay in Batch 001 until counts reconcile to current foundation truth
- Fallback if forced proof is blocked:
  - `n/a`
- Next phase after success:
  - Batch 002 tactic scorecard
- Notification mode:
  - passive
- User interruption threshold:
  - only if overlap truth contradicts the signed-off cleanup baseline

## Proof required
- Row counts:
  - current unresolved ASIN-bearing counts and route buckets
- Health rows:
  - targeted tests only for Batch 001
- Output files:
  - `out/analysis_reports/hf_scope_expansion_candidates_latest.csv`
  - `out/analysis_reports/hf_scope_expansion_summary_latest.csv`
- Notes:
  - do not claim recovered overlap yet unless the builder actually proves it

## Completion checklist
- [ ] Scope held
- [ ] Files changed only in allowed set
- [ ] Tests passed
- [ ] Proof captured
- [ ] Reply file updated
