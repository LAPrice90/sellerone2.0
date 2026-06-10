# Coding Plan

Date:
- `2026-04-18`
Scope:
- build the next H/F optimisation program in ordered phases:
  - overlap expansion first
  - tactic scoring second
  - operator review third
  - shadow experiment queue fourth
  - H runtime cohort hooks only last and only if justified

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 | Build overlap expansion and routing pack | `scripts/one_off/HF010_build_scope_expansion_candidates.py`, `tests/test_hf_scope_expansion_candidates.py`, plan docs | targeted pytest + deterministic reruns | no | complete |
| Phase 2 | Build tactic scorecard and maturity gates | `scripts/one_off/HF011_build_strategy_scorecard.py`, `tests/test_hf_strategy_scorecard.py`, plan docs | targeted pytest + deterministic reruns | no | complete |
| Phase 3 | Build strategy review pack | `scripts/one_off/HF012_build_strategy_review_pack.py`, `tests/test_hf_strategy_review_pack.py`, plan docs | targeted pytest + deterministic reruns | no | complete |
| Phase 4 | Build shadow experiment queue and optional F shadow handoff | `scripts/one_off/HF013_build_strategy_experiment_queue.py`, `scripts/flows/F/F080_build_feedback_calibration_shadow.py`, tests, plan docs | targeted pytest + deterministic reruns | no | complete |
| Phase 5 | Optional H cohort/runtime hooks | H scoped runtime files and tests only | H targeted pytest + isolated reruns + forced proof | yes | deferred - runtime not attempted in this ticket |

## 2) Phase details

### Phase 1 - Overlap expansion and routing
Goal:
- make the zero-overlap problem actionable through deterministic packs instead of operator guesswork

Files allowed to change:
- `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- `tests/test_hf_scope_expansion_candidates.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

Implementation tasks:
- build `hf_scope_expansion_candidates_latest.csv`
- build `hf_scope_expansion_summary_latest.csv`
- route every ASIN-bearing unresolved row into explicit buckets such as:
  - already_in_h_scope
  - outside_h_scope_with_capture_path
  - no_asin
  - stale_source
- carry forward the existing F owner path into the output:
  - `F007`
  - `F061`
  - `F008`

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF010_build_scope_expansion_candidates.py tests/test_hf_scope_expansion_candidates.py`
  - `pytest tests/test_hf_scope_expansion_candidates.py tests/test_hf_learning_foundation.py tests/test_hf_learning_alignment.py -q`
  - run the builder twice against the same inputs
- expected result:
  - output row counts are stable across reruns
  - route buckets are explicit
  - overlap summary matches current foundation metrics before any recovery attempt

Monitored validation:
- live proof needed:
  - `no`
- forced proof window:
  - `n/a`
- artifacts to poll:
  - `n/a`
- poll cadence:
  - `n/a`
- success threshold:
  - deterministic overlap pack exists and current zero-overlap truth is explicit
- timeout rule:
  - stay in Phase 1 until route buckets and counts reconcile
- fallback if forced proof is blocked:
  - `n/a`
- next automatic step after success:
  - start Phase 2
- notification mode:
  - passive
- user interruption threshold:
  - only if overlap truth contradicts current cleanup sign-off assumptions

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed (live loop verification not required for Phase 1)

### Phase 2 - Tactic scorecard and maturity gates
Goal:
- turn H tactic behaviour into a measurable scorecard before any strategy change is proposed

Files allowed to change:
- `scripts/one_off/HF011_build_strategy_scorecard.py`
- `tests/test_hf_strategy_scorecard.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

Implementation tasks:
- build `hf_strategy_scorecard_latest.csv`
- score each tactic on:
  - decision rows
  - eligible-to-write, change, attempted, applied chain
  - fail and expired mix
  - realised units and profit where available
  - sample maturity gate
- keep thin-sample tactics explicit and non-actionable

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF011_build_strategy_scorecard.py tests/test_hf_strategy_scorecard.py`
  - `pytest tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py tests/test_hf_learning_operator_report.py -q`
  - run the builder twice against the same inputs
- expected result:
  - scorecard rows are stable
  - maturity flags correctly mark:
    - `multi_seller_ladder_cap` as below target
    - `single_rival_reset` as below target
    - `suppression_reactivation` as above target

Monitored validation:
- live proof needed:
  - `no`
- forced proof window:
  - `n/a`
- artifacts to poll:
  - `n/a`
- poll cadence:
  - `n/a`
- success threshold:
  - tactic scorecard exists and blocks thin-sample tactics from later queue promotion
- timeout rule:
  - stay in Phase 2 until maturity flags and write-chain counts reconcile
- fallback if forced proof is blocked:
  - `n/a`
- next automatic step after success:
  - start Phase 3
- notification mode:
  - passive
- user interruption threshold:
  - only if scorecard results contradict current H daily evidence

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed (live loop verification not required for Phase 2)

### Phase 3 - Strategy review pack
Goal:
- build the operator-facing pack that explains what is working, what is blocked by missing baseline, and what is blocked by thin sample

Files allowed to change:
- `scripts/one_off/HF012_build_strategy_review_pack.py`
- `tests/test_hf_strategy_review_pack.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

Implementation tasks:
- build `hf_strategy_review_pack_latest.csv`
- optionally emit a markdown summary for the same pack
- separate:
  - missing baseline blockers
  - underperform vs expected candidates
  - aligned candidates
  - outperform candidates
- include tactic-level recommendations such as:
  - keep observing
  - recover overlap first
  - sample too thin
  - eligible for shadow experiment queue

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF012_build_strategy_review_pack.py tests/test_hf_strategy_review_pack.py`
  - `pytest tests/test_hf_strategy_review_pack.py tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py -q`
  - run the builder twice against the same inputs
- expected result:
  - review pack is deterministic
  - recommendation classes are explicit
  - no-source rows stay distinct from true underperformance rows

Monitored validation:
- live proof needed:
  - `no`
- forced proof window:
  - `n/a`
- artifacts to poll:
  - `n/a`
- poll cadence:
  - `n/a`
- success threshold:
  - review pack exists and is source-timestamped
- timeout rule:
  - stay in Phase 3 until pack classes reconcile to alignment and scorecard inputs
- fallback if forced proof is blocked:
  - `n/a`
- next automatic step after success:
  - start Phase 4
- notification mode:
  - passive
- user interruption threshold:
  - only if the pack exposes a material contradiction in source truth

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed (live loop verification not required for Phase 3)

### Phase 4 - Shadow experiment queue
Goal:
- create the shadow-only queue that tells us what deserves future testing without touching live H behaviour

Files allowed to change:
- `scripts/one_off/HF013_build_strategy_experiment_queue.py`
- `scripts/flows/F/F080_build_feedback_calibration_shadow.py`
- `tests/test_hf_strategy_experiment_queue.py`
- `tests/test_f080_build_feedback_calibration_shadow.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

Implementation tasks:
- build `hf_strategy_experiment_queue_latest.csv`
- require explicit queue gates:
  - sample_mature_flag
  - risk_gate_status
  - shadow_only_flag
  - max_cohort_size
  - required_review_reason
- optionally feed queue-derived shadow fields into `feeder_feedback_calibration_live.csv`
- keep all outputs advisory only

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF013_build_strategy_experiment_queue.py scripts/flows/F/F080_build_feedback_calibration_shadow.py tests/test_hf_strategy_experiment_queue.py tests/test_f080_build_feedback_calibration_shadow.py`
  - `pytest tests/test_hf_strategy_experiment_queue.py tests/test_f080_build_feedback_calibration_shadow.py tests/test_hf_strategy_review_pack.py -q`
  - run queue and shadow builders twice against the same inputs
- expected result:
  - queue is deterministic
  - queue stays shadow-only
  - no tactic is promoted when maturity or risk gates fail

Monitored validation:
- live proof needed:
  - `no`
- forced proof window:
  - `n/a`
- artifacts to poll:
  - `n/a`
- poll cadence:
  - `n/a`
- success threshold:
  - experiment queue exists and all rows carry explicit gate reasons
- timeout rule:
  - stay in Phase 4 until queue decisions are deterministic and shadow-only
- fallback if forced proof is blocked:
  - `n/a`
- next automatic step after success:
  - Phase 5 remains blocked unless runtime work is explicitly approved in a later execution ticket
- notification mode:
  - passive
- user interruption threshold:
  - only if shadow queue suggests unsafe promotion pressure

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed (live loop verification not required for Phase 4)

### Phase 5 - Optional H cohort/runtime hooks
Goal:
- only if earlier phases justify it, add cohort tagging or queue-linked fields so a later H runtime ticket can measure experiments honestly

Files allowed to change:
- `scripts/phase1/phase1_main_loop.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- `tests/test_phase1_main_loop.py`
- `tests/test_h_split_health_gate.py`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/*`

Implementation tasks:
- add cohort or queue-reference fields to H outputs
- keep live logic unchanged unless a separate runtime experiment ticket explicitly authorises more
- if any runtime toggle is added, default it off

Isolated verification:
- command:
  - `python -m py_compile scripts/phase1/phase1_main_loop.py scripts/cycles/run_H_pricing_cycle.py tests/test_phase1_main_loop.py tests/test_h_split_health_gate.py`
  - `pytest tests/test_phase1_main_loop.py tests/test_h_split_health_gate.py -q`
  - run isolated H replay or equivalent deterministic proof set before touching runtime
- expected result:
  - cohort fields exist without altering current tactic outcomes
  - tests pass before any H owner handoff

Monitored validation:
- live proof needed:
  - `yes`
- forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow H`
- artifacts to poll:
  - `out/H_pricing_cycle.lock`
  - `out/systems/H/live/H_runtime_status.json`
  - `out/H_cycle_last_terminal_info.txt`
  - `out/h_pricing_cycle_state.json`
- poll cadence:
  - `+5 minutes`
  - `+10 minutes`
  - then every `+15 minutes` up to `+60 minutes`
- success threshold:
  - isolated tests pass
  - controlled H proof run finalizes cleanly
  - owner process is restored after the proof window
  - new cohort fields are visible in owned runtime artifacts
- timeout rule:
  - park as `pending forced proof window` with exact missing artifact
- fallback if forced proof is blocked:
  - do not touch runtime and keep the queue/report work as one-off only
- next automatic step after success:
  - close the runtime hook phase or open the next controlled experiment ticket
- notification mode:
  - passive until fail, warn, contradiction, or timeout
- user interruption threshold:
  - interrupt only for proof failure, new fail/warn, or when approval is needed to widen scope

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - deferred in this ticket (runtime promotion not attempted)

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
- No live H strategy change may start from this plan until:
  - overlap recovery outputs exist
  - tactic scorecard exists
  - experiment queue exists
  - the runtime phase is explicitly authorised in a later execution pass

## 4) Execution proof (2026-04-18)
- Phase 1 verification:
  - `python -m py_compile scripts/one_off/HF010_build_scope_expansion_candidates.py tests/test_hf_scope_expansion_candidates.py`
  - `pytest tests/test_hf_scope_expansion_candidates.py tests/test_hf_learning_foundation.py tests/test_hf_learning_alignment.py -q`
  - deterministic reruns:
    - `scope_candidate_rows=52362`
    - `outside_h_scope_rows=6979`
    - `no_asin_rows=35831`
    - `stale_source_rows=9552`
    - `reconcile_identity_asin_not_in_scope_vs_outside_bucket=match`
- Phase 2 verification:
  - `python -m py_compile scripts/one_off/HF011_build_strategy_scorecard.py tests/test_hf_strategy_scorecard.py`
  - `pytest tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py tests/test_hf_learning_operator_report.py -q`
  - deterministic reruns:
    - `strategy_scorecard_rows=6`
    - maturity gates:
      - `multi_seller_ladder_cap` -> `sample_mature_flag=0`
      - `single_rival_reset` -> `sample_mature_flag=0`
      - `suppression_reactivation` -> `sample_mature_flag=1`
- Phase 3 verification:
  - `python -m py_compile scripts/one_off/HF012_build_strategy_review_pack.py tests/test_hf_strategy_review_pack.py`
  - `pytest tests/test_hf_strategy_review_pack.py tests/test_hf_strategy_scorecard.py tests/test_hf_learning_alignment.py -q`
  - deterministic reruns:
    - `strategy_review_rows=12`
    - alignment class rows include:
      - `missing_expected_baseline=65`
      - `underperform_vs_expected=24`
      - `aligned=2`
- Phase 4 verification:
  - `python -m py_compile scripts/one_off/HF013_build_strategy_experiment_queue.py scripts/flows/F/F080_build_feedback_calibration_shadow.py tests/test_hf_strategy_experiment_queue.py tests/test_f080_build_feedback_calibration_shadow.py`
  - `pytest tests/test_hf_strategy_experiment_queue.py tests/test_f080_build_feedback_calibration_shadow.py tests/test_hf_strategy_review_pack.py -q`
  - deterministic reruns:
    - `strategy_experiment_queue_rows=6`
    - `strategy_experiment_queue_fail_rows=6`
    - `queue_shadow_only_all=1`
  - F080 shadow handoff proof:
    - bounded retries recorded in `plans/archive/2026/h-f-overlap-sample-strategy-v1/F080_SHADOW_RETRY_PROOF.csv`
    - two successful hash-verified runs captured:
      - `shadow_output_rows=5`
      - `queue_rows_current=9552`
      - `decision_rows_current=9552`
      - `source_hash_verified=1`
- Full-pack clean-run target:
  - `3` deterministic unchanged-input runs captured in:
    - `plans/archive/2026/h-f-overlap-sample-strategy-v1/FULL_PACK_CLEAN_RUN_PROOF.csv`
  - all three runs reconcile on:
    - scope, scorecard, review, and queue row counts
    - route bucket counts
    - risk-gate counts
    - `queue_shadow_only_all=1`
