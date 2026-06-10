# Runbook

## Purpose
- What this plan or system does:
  - advance H/F from cleaned evidence into execution-ready overlap recovery, tactic scoring, and shadow strategy planning

## Standard run order
```powershell
python scripts/one_off/HF010_build_scope_expansion_candidates.py
python -m pytest tests/test_hf_scope_expansion_candidates.py tests/test_hf_learning_foundation.py tests/test_hf_learning_alignment.py -q

python scripts/one_off/HF011_build_strategy_scorecard.py
python -m pytest tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py tests/test_hf_learning_operator_report.py -q

python scripts/one_off/HF012_build_strategy_review_pack.py
python -m pytest tests/test_hf_strategy_review_pack.py tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py -q

python scripts/one_off/HF013_build_strategy_experiment_queue.py
python -m pytest tests/test_hf_strategy_experiment_queue.py tests/test_f080_build_feedback_calibration_shadow.py -q

# Only if a later runtime phase is explicitly approved:
python scripts/one_off/P002_plan_forced_proof_window.py --flow H
```

## Validation steps
- Step 1:
  - confirm overlap counts match the current foundation truth before any recovery work starts
- Step 2:
  - confirm tactic scorecard marks thin-sample tactics as blocked from promotion
- Step 3:
  - confirm review pack separates `missing_expected_baseline` from true underperformance
- Step 4:
  - if live proof can clash with an active owner, run `python scripts/one_off/P002_plan_forced_proof_window.py --flow <flow>` first and use the safe boundary it reports
  - for this plan, only `flow H` is allowed to need a forced proof window

## Expected outputs
- Output:
  - overlap expansion candidates
- Path:
  - `out/analysis_reports/hf_scope_expansion_candidates_latest.csv`
- What good looks like:
  - all route buckets are explicit and stable across reruns
- Output:
  - tactic scorecard
- Path:
  - `out/analysis_reports/hf_strategy_scorecard_latest.csv`
- What good looks like:
  - mature and thin-sample tactics are separated clearly
- Output:
  - strategy review pack
- Path:
  - `out/reports/hf_strategy_review_pack_latest.csv`
- What good looks like:
  - operator can see missing baseline vs true underperformance without reading raw marts
- Output:
  - shadow experiment queue
- Path:
  - `out/analysis_reports/hf_strategy_experiment_queue_latest.csv`
- What good looks like:
  - every row is shadow-only and carries explicit review/gate reasons

## Health checks
- Check:
  - overlap pack freshness
- Pass condition:
  - output is as new as its foundation/alignment inputs
- Warning condition:
  - output exists but is older than the latest rebuild inputs
- Fail condition:
  - output missing or route buckets are blank
- Check:
  - tactic maturity truth
- Pass condition:
  - `multi_seller_ladder_cap` and `single_rival_reset` remain blocked until mature
- Warning condition:
  - tactic counts moved but maturity flag did not update
- Fail condition:
  - thin-sample tactic is marked eligible for experiment queue
- Check:
  - queue shadow-only guard
- Pass condition:
  - all queue rows have `shadow_only_flag=1`
- Warning condition:
  - queue row lacks explicit review reason
- Fail condition:
  - queue row implies live promotion without a later runtime ticket

## Failure recovery
- If input is stale:
  - rebuild the upstream H/F learning artifacts first and rerun the phase
- If output is missing:
  - rerun the owning builder and compare row counts against source truth
- If tests fail:
  - stop in the owning phase and fix the owning script or test before any downstream rerun
- If runtime ownership is unclear:
  - do not touch runtime files; re-check lock, runtime status, and terminal markers first
- If proof would clash with a live loop:
  - do not wait vaguely for the next cycle
  - use the forced proof planner and record the exact boundary required

## Archive note
- What to preserve when this plan is finished:
  - the final scorecard thresholds
  - the overlap route-bucket definitions
  - the shadow queue gating rules
