# Phase Scorecard

## Gate
- Pass:
  - `95-100`
- Hold:
  - `90-94`
- Fail:
  - `<90`

## Automatic fail rules
- frozen inputs changed mid-ticket
- live source mutated during a read-only phase
- missing targeted tests
- broken schema or key reconciliation
- direct H owner kill without maintenance handoff
- live restart before isolated proof completes

## Score table

| Phase | Build 30 | Tests 25 | Determinism 20 | Boundary 15 | Operator 10 | Total 100 | Gate | Status | Notes |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| Prep | 30 | 25 | 20 | 15 | 10 | 100 | pass | complete | locked `2026-04-17T17:03:25Z`; `py_compile` pass; `pytest tests/test_hf_learning_prep_freeze.py` pass; sources=19 |
| Phase 0 | 26 | 25 | 20 | 15 | 10 | 96 | pass | complete | `py_compile` pass; `pytest tests/test_hf_learning_prep_freeze.py tests/test_hf_learning_foundation.py` pass (`5`); builder run twice with stable key hashes (`identity=946501f2...`, `assumption=c0937de9...`, `metrics=a209e554...`); metrics output added at `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`; known data gap: `identity_resolution_rate=0.0000` because frozen F candidate ASIN set has no overlap with frozen H listing ASIN set |
| Phase 1 | 27 | 24 | 20 | 15 | 10 | 96 | pass | complete | `py_compile` pass; `pytest tests/test_hf_learning_prep_freeze.py tests/test_hf_learning_foundation.py tests/test_hf_learning_baseline.py` pass (`6`); `HF001_build_learning_baseline.py` run twice with stable key hashes (`market=ffe96cfa...`, `actions=0fa70050...`, `gaps=2aa5ce8e...`); scanner-owned source hashes unchanged (`scanner_source_hash_verified=1`) |
| Phase 2 | 26 | 24 | 20 | 15 | 10 | 95 | pass | complete | `py_compile` pass; `pytest` HF pack pass (`7`); `HF002_build_learning_alignment.py` run twice with stable key hashes (`alignment=12dfaa5c...`, `factor=73eea6e9...`); output is deterministic and the dominant class is explicitly `missing_expected_baseline` (`95/95`) for downstream calibration work |
| Phase 3 | 29 | 24 | 20 | 15 | 10 | 98 | pass | complete | `py_compile` pass; `pytest` HF pack pass (`9`); `HF003_build_learning_health_checks.py` run twice with stable checklist hash (`827bdebb...`); checklist reports `fail=0`, `warn=2` (missing scrape rate and expected coverage) |
| Phase 4 | 27 | 24 | 20 | 15 | 10 | 96 | pass | complete | `py_compile` pass; `pytest tests/test_f080_build_feedback_calibration_shadow.py` pass (`2`); `F080_build_feedback_calibration_shadow.py` run twice with stable key hash (`5fcdfa81...`); source mutation guard holds (`source_hash_verified=1`) |
| Phase 5 | 28 | 24 | 20 | 15 | 10 | 97 | pass | complete | `py_compile` pass; `pytest tests/test_hf_learning_operator_report.py` pass (`1`); `HF005_build_learning_operator_report.py` run twice with stable key hash (`01345692...`); report rows=`18` with health summary embedded |
| Phase 6 | 29 | 24 | 20 | 15 | 10 | 98 | pass | complete | sign-off doc written (`PHASE6_SIGNOFF.md`); promotion decision recorded as shadow/one-off only; runtime claim explicitly marked `not yet proven` for promotion |
| Phase 7 | 28 | 24 | 20 | 15 | 10 | 97 | pass | complete | `F007_prepare_targeted_rescrape_subset.py` optional alignment bridge added; `pytest tests/test_f007_prepare_targeted_rescrape_subset.py` plus HF/F scoped pack pass; include mode is additive with default behavior unchanged |
| Phase 8 | 29 | 24 | 19 | 15 | 10 | 97 | pass | complete | `HF006_build_alignment_missing_asin_pack.py` added and tested; large `F008` live run from HF pack succeeded (`asins_selected=20`, `success_rows=20`); `F009` normalization wrote `facts_rows=20`; `HF002` full-capture fallback (`full_capture_asin`) lifted expected coverage to `0.2105` and reduced no-source rate to `0.7895`; HF health now `warn_count=1` (scrape-gap only) |
| Phase 9 | 29 | 24 | 19 | 15 | 10 | 97 | pass | complete | `HF007_run_alignment_coverage_recovery.py` added with bounded stop rules; race fix applied in `HF001_build_learning_baseline.py` so external scanner drift is reported not fatal; cumulative manifest-union fix prevents coverage rollback; scoped pytest pack pass (`13`); live bounded rounds reached `expected_coverage_rate=0.3158` and reduced no-source rows from `75` to `65` |
