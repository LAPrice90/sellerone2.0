# Coding Plan

Date: `2026-04-17`
Scope: build the H/F learning layer in a controlled execution pass that uses frozen inputs, phase gates, and minimal live disruption.
Execution mode: `frozen-input perfection pass`

## 1) Non-negotiable execution rules

- Frozen input rule:
  - before Phase 0 coding starts, Codex must lock the source set in `FROZEN_INPUT_MANIFEST.md`
  - from that point until Phase 6 closes, this ticket must not absorb fresh scrape, ad-hoc `A` runs, or newer live-source files
  - if a source must change, mark the current phase failed, refresh the freeze manifest, and restart scoring from Prep
- Minimal disruption rule:
  - Prep through Phase 3 are read-only or one-off only, so kill no live owners
  - Phase 4 touches F shadow outputs, but F is not a runtime-owned flow in `config/runtime_owner_contract.json`, so there is no scheduler handoff to pause; stop only a manually running `F061_run_legacy_first_checks_local.py` process if that exact file or its shared helpers are being edited
  - Phase 5 touches H runtime-owned paths, so use the controlled restart-drain marker and launcher handoff; do not direct-kill the H owner as the first action
- Deterministic proof rule:
  - every coding phase must pass:
    - `python -m py_compile`
    - scoped pytest
    - first isolated build against frozen inputs
    - second isolated build against the same frozen inputs
    - output comparison on rows, keys, and hashes where practical
    - scorecard update in `PHASE_SCORECARD.md`
- Status language rule:
  - always separate:
    - `code fix applied`
    - `isolated verification passed`
    - `live loop verification pending`
    - `live loop verification confirmed`

## 2) Stop/start matrix

| Phase | Stop before edit | Restart after phase | Notes |
|---|---|---|---|
| Prep | none | none | freeze and scorecard only |
| Phase 0 | none | none | frozen-input foundation build |
| Phase 1 | none | none | read-only joined marts |
| Phase 2 | none | none | read-only alignment and factor outputs |
| Phase 3 | none | none | checks and health only |
| Phase 4 | only stop manual `F061_run_legacy_first_checks_local.py` if editing that script or shared F helper files | none by default | no new scrape during this ticket; use frozen fixtures only |
| Phase 5 | request H restart-drain marker with `requested_by=controlled_restart_gate|reason=overnight_restart_eval`, wait for `out/systems/H/live/H_restart_drain.ready`, confirm H owner is drained | clear drain markers, then relaunch only through `run_H_cycle.bat` | H owner chain is `run_H_cycle.bat` -> `scripts/cycles/run_H_pricing_cycle_guarded.py` -> `scripts/cycles/run_H_pricing_cycle.py` |
| Phase 6 | none unless Phase 5 exposes a scoped follow-up defect | none unless promotion proof requires it | sign-off and archive decision |

## 3) Score gate between phases

- Score categories:
  - Build correctness: `30`
  - Test strength: `25`
  - Determinism: `20`
  - Boundary discipline: `15`
  - Operator clarity: `10`
  - Total: `100`
- Gate:
  - `95-100` = pass and advance automatically
  - `90-94` = hold for one cleanup pass
  - `<90` = fail and fix before continuing
- Automatic fail regardless of score:
  - frozen inputs changed mid-ticket
  - live source file mutated during a read-only phase
  - missing targeted tests
  - schema or key reconciliation failure
  - direct H owner kill without maintenance handoff
  - live restart before isolated proof is complete

## 4) Phase summary

| Phase | Goal | Owner action | Main proof target | Status |
|---|---|---|---|---|
| Prep | freeze inputs and open scorecard | none | manifest and scorecard locked | complete |
| Phase 0 | foundation lock | none | bridge and assumption outputs build twice identically | complete |
| Phase 1 | joined evidence baseline | none | marts reconcile and rerun identically | complete |
| Phase 2 | alignment and factor outputs | none | discrepancy classes traceable on frozen inputs | complete |
| Phase 3 | schema and health truth | none | broken fixtures fail correctly | complete |
| Phase 4 | F shadow calibration | manual F stop only if editing `F061` or shared F helpers | shadow output stays read-only and deterministic | complete |
| Phase 5 | H evidence hooks and operator report | H maintenance, isolated proof, then restart | 10 frozen replays clean before restart, then new owner observed | complete |
| Phase 6 | sign-off and promotion decision | none unless scoped follow-up needed | deliverable ratings and proof language complete | complete |
| Phase 7 | expected-baseline rescrape bridge | none | optional F007 alignment bridge verified by tests and dry-run proofs | complete |
| Phase 8 | non supplier-locked ASIN capture bridge | none | HF no-source ASIN pack + F008/F009 capture + HF002 fallback proof | complete |
| Phase 9 | bounded no-source coverage recovery loop | none | HF007 batch orchestration proves repeatable capture-rebuild progress and threshold stop rules | complete |

## 5) Phase details

### Prep - Frozen input gate
Goal:
- lock the exact evidence set used for this ticket so later phases cannot silently absorb newer data

Files allowed to change:
- this active plan folder
- planned prep helper under `scripts/one_off/`
- planned targeted tests under `tests/`

Implementation tasks:
- fill `FROZEN_INPUT_MANIFEST.md`
- open `PHASE_SCORECARD.md`
- record the no-new-input rule for this ticket
- confirm owner policy:
  - F is not runtime-owned in `config/runtime_owner_contract.json`
  - H is runtime-owned and must use controlled restart-drain in Phase 5

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - scoped pytest for the prep helper if created
  - `python -m py_compile` for any new prep helper and tests
- expected result:
  - freeze manifest is written or updated deterministically
  - scorecard exists
  - no source files are changed

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - manifest locked and scorecard opened
- timeout rule:
  - do not start Phase 0 until prep evidence is complete
- next automatic step:
  - start Phase 0

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 8 - Non supplier-locked ASIN capture bridge
Goal:
- close the universe disconnect where H alignment no-source ASINs are not present in supplier-scoped scrape evidence

Files allowed to change:
- `scripts/one_off/HF006_build_alignment_missing_asin_pack.py`
- `scripts/one_off/HF002_build_learning_alignment.py`
- `tests/test_hf_alignment_missing_asin_pack.py`
- `tests/test_hf_learning_alignment.py`
- this active plan folder

Implementation tasks:
- build a direct ASIN pack from `hf_learning_alignment_30d_latest.csv` rows where `expected_units_source` is blank/no_source
- keep pack format compatible with `F008_capture_full_bbp_evidence_pack.py`
- run a bounded live capture using `F008` from that pack
- normalize capture results with `F009_build_full_capture_consistency_audit.py`
- add `HF002` fallback source `full_capture_asin` for expected units/profit

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF006_build_alignment_missing_asin_pack.py scripts/one_off/HF002_build_learning_alignment.py tests/test_hf_alignment_missing_asin_pack.py tests/test_hf_learning_alignment.py`
  - `pytest tests/test_hf_alignment_missing_asin_pack.py tests/test_hf_learning_alignment.py tests/test_hf_learning_health_checks.py tests/test_hf_learning_operator_report.py tests/test_f007_prepare_targeted_rescrape_subset.py tests/test_f080_build_feedback_calibration_shadow.py`
  - `python scripts/one_off/HF006_build_alignment_missing_asin_pack.py --output-dir out/analysis_reports`
  - `python scripts/one_off/F008_capture_full_bbp_evidence_pack.py --asin-pack-path out/analysis_reports/hf_alignment_missing_asin_pack_latest.csv --max-asins 1 --passes 1 --webscrape-mode data --skip-date-scraping --output-dir out/analysis_reports`
  - `python scripts/one_off/F009_build_full_capture_consistency_audit.py --manifest-path out/analysis_reports/f_full_capture_manifest_latest.csv --output-dir out/analysis_reports`
  - `python scripts/one_off/HF002_build_learning_alignment.py`
  - `python scripts/one_off/HF003_build_learning_health_checks.py`
  - `python scripts/one_off/HF005_build_learning_operator_report.py`
- expected result:
  - pack shows root-cause truth (`alignment_no_source_unique_asins=95`, `scrape_present_rows=0`)
  - capture succeeds for at least one no-source ASIN
  - HF alignment uses `full_capture_asin` source for captured ASIN(s)
  - expected coverage moves above zero while remaining below threshold until more captures run

Monitored validation:
- target:
  - none (one-off bridge and evidence pack path)
- cadence:
  - n/a
- success threshold:
  - source path and fallback path are both code-covered and proven by one live capture artifact
- timeout rule:
  - if capture tooling fails, keep phase open and restore isolated test-only state
- next automatic step:
  - execute Phase 9 implementation for repeated capture batches and thresholded stop rules

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 9 - Bounded no-source coverage recovery loop
Goal:
- remove manual rerun burden by adding one bounded one-off orchestrator that repeatedly runs the proven Phase 8 chain
- make progress measurable per round with explicit stop rules for coverage and no-source backlog

Files allowed to change:
- `scripts/one_off/HF007_run_alignment_coverage_recovery.py`
- `tests/test_hf_alignment_coverage_recovery.py`
- this active plan folder

Implementation tasks:
- add a one-off runner that executes this chain in strict sequence:
  - `HF006_build_alignment_missing_asin_pack.py`
  - `F008_capture_full_bbp_evidence_pack.py`
  - `F009_build_full_capture_consistency_audit.py`
  - `HF001_build_learning_baseline.py`
  - `HF002_build_learning_alignment.py`
  - `HF003_build_learning_health_checks.py`
  - `HF005_build_learning_operator_report.py`
- add bounded stop rules:
  - stop when target expected coverage is reached
  - stop when target no-source row count is reached
  - stop when ASIN pack is empty
  - stop at max rounds
- print per-round metrics in machine-readable form:
  - alignment total rows
  - expected coverage rate
  - no-source rows
  - scrape-gap missing rate
  - health fail and warn counts

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/HF007_run_alignment_coverage_recovery.py tests/test_hf_alignment_coverage_recovery.py`
  - `pytest tests/test_hf_alignment_coverage_recovery.py tests/test_hf_alignment_missing_asin_pack.py tests/test_hf_learning_alignment.py tests/test_hf_learning_baseline.py tests/test_hf_learning_health_checks.py tests/test_hf_learning_operator_report.py`
  - `python scripts/one_off/HF007_run_alignment_coverage_recovery.py --max-rounds 1 --batch-size 5 --passes 1 --skip-date-scraping --webscrape-mode data --target-coverage 0.30 --target-no-source 60`
- expected result:
  - isolated tests pass
  - one live bounded round completes and updates HF outputs sequentially
  - summary reports pre/post coverage and no-source deltas

Monitored validation:
- target:
  - none (one-off execution path)
- cadence:
  - n/a
- success threshold:
  - runner and tests are deterministic for control flow
  - live bounded round completes without breaking existing health schemas
- timeout rule:
  - if live capture fails, keep phase open and retain prior proven artifacts
- next automatic step:
  - open a focused follow-up phase for root-cause scrape-gap missing-rate reduction
  - keep bounded HF007 rounds available as the controlled no-source recovery tool

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 7 - Expected baseline rescrape bridge
Goal:
- allow targeted rescrape selection to include ASINs from HF alignment where `expected_units_source` is blank or `no_source`, without changing default F007 behavior

Files allowed to change:
- `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
- `tests/test_f007_prepare_targeted_rescrape_subset.py`
- this active plan folder

Implementation tasks:
- add optional flags:
  - `--include-alignment-missing`
  - `--alignment-missing-path`
- load HF alignment ASINs where `expected_units_source` is blank or `no_source`
- add `alignment_missing_expected_baseline` as an additional targeted rescrape reason
- keep default behavior unchanged when the new flag is not used
- expose bridge diagnostics in summary output:
  - `include_alignment_missing`
  - `alignment_missing_rows_source`
  - `alignment_missing_asins_source`

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/F007_prepare_targeted_rescrape_subset.py tests/test_f007_prepare_targeted_rescrape_subset.py`
  - `pytest tests/test_f007_prepare_targeted_rescrape_subset.py tests/test_hf_learning_alignment.py tests/test_hf_learning_health_checks.py tests/test_hf_learning_operator_report.py tests/test_f080_build_feedback_calibration_shadow.py`
  - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --include-alignment-missing --output-dir out/analysis_reports`
  - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --output-dir out/analysis_reports`
- expected result:
  - compile and pytest pass
  - include-mode summary shows alignment source counts
  - default mode remains unchanged
  - overlap analysis truth is explicit when no live overlap exists yet

Monitored validation:
- target:
  - none (one-off extension, no loop ownership change)
- cadence:
  - n/a
- success threshold:
  - additive bridge path is test-covered and default behavior is preserved
- timeout rule:
  - none
- next automatic step:
  - keep Phase 7 marked complete and carry evidence into next planning ticket

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 0 - Foundation lock
Goal:
- make sure later learning compares the right item, the right time, and the right expectation

Files allowed to change:
- planned one-off builder under `scripts/one_off/`
- planned targeted tests under `tests/`
- this active plan folder

Implementation tasks:
- build `hf_learning_identity_bridge_latest.csv`
- build `hf_learning_assumption_snapshots_latest.csv`
- build `hf_learning_foundation_metrics_latest.csv`
- freeze these joins:
  - `candidate_id`
  - `supplier_id`
  - `supplier_sku`
  - `asin`
  - `sku` when resolvable
- define fixed windows:
  - H tactic windows: `15m`, `2h`, `24h`, `72h`
  - F product windows: `30d`, `60d`, `90d`
- use approval-decision lineage as the initial buy-time anchor where PO handoff rows are absent
- read only from the frozen input set

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - scoped pytest pack
  - `python -m py_compile`
  - first isolated builder run against frozen inputs
  - second isolated builder run against the same frozen inputs
- expected result:
  - tests pass
  - identity bridge builds with explicit unresolved rows
  - assumption snapshots carry stage and source timestamp
  - first and second runs match on row counts and key coverage

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - score `>=95` and no automatic-fail condition
- timeout rule:
  - fix Phase 0 until deterministic proof passes
- next automatic step:
  - start Phase 1

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 1 - Joined evidence baseline
Goal:
- build one read-only truth layer that joins market facts, H action facts, and actual sales/profit anchors

Files allowed to change:
- planned one-off builder under `scripts/one_off/`
- planned targeted tests under `tests/`
- this active plan folder

Implementation tasks:
- build `hf_learning_market_facts_latest.csv`
- build `hf_learning_action_outcomes_latest.csv`
- build `hf_learning_scrape_gap_report_latest.csv`
- consume the Phase 0 identity bridge and frozen assumption snapshots
- reconcile row keys and timestamps against source files
- keep states separate:
  - eligible to write
  - decision to change price
  - write attempted
  - write applied successfully
- keep the builder read-only against scanner-owned contracts

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - scoped pytest pack
  - `python -m py_compile`
  - first isolated builder run against frozen inputs
  - second isolated builder run against the same frozen inputs
- expected result:
  - outputs build with nonzero rows
  - reconciliation is explicit
  - scrape coverage and stale-share percentages are recorded
  - first and second runs match

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - score `>=95` and no automatic-fail condition
- timeout rule:
  - hold at Phase 1 until joins and reruns are clean
- next automatic step:
  - start Phase 2

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 2 - 30-day alignment and factor impacts
Goal:
- explain estimate-vs-actual gaps with concrete factors instead of one topline miss

Files allowed to change:
- planned one-off builders under `scripts/one_off/`
- planned tests under `tests/`
- this active plan folder

Implementation tasks:
- build `hf_learning_alignment_30d_latest.csv`
- build `hf_learning_factor_impacts_latest.csv`
- define explicit rescrape trigger rules
- wire trigger notes to current tools only:
  - `F007_prepare_targeted_rescrape_subset.py`
  - `F061_run_legacy_first_checks_local.py`
  - `F008_capture_full_bbp_evidence_pack.py`
- prefer `F061_MODE=data_collection` if a later ticket needs a learning-driven refresh
- compare:
  - F expected units and profit
  - H market conditions
  - actual 30-day units and profit
  - factor buckets such as seller count, Amazon pressure, delivery parity, ladder depth, and undercut behavior

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - scoped pytest pack
  - `python -m py_compile`
  - first isolated builder run against frozen inputs
  - second isolated builder run against the same frozen inputs
- expected result:
  - discrepancy classes are populated
  - sample rows trace back to source files
  - thin-sample buckets stay marked thin
  - first and second runs match

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - score `>=95` and no automatic-fail condition
- timeout rule:
  - do not move to health wiring until factor outputs are deterministic
- next automatic step:
  - start Phase 3

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 3 - Health and schema truth
Goal:
- make the learning outputs trustworthy enough to rely on

Files allowed to change:
- planned scoped health and check scripts
- planned tests
- this active plan folder

Implementation tasks:
- add schema checks for every new output
- add freshness and coverage checks
- add alert conditions for:
  - zero-row builds
  - missing key fields
  - broken joins
  - stale alignment output
  - stale or missing scrape coverage
  - breached rescrape threshold

Owner action:
- stop before edit:
  - none
- restart after phase:
  - none

Isolated verification:
- command:
  - scoped pytest pack
  - `python -m py_compile`
  - first isolated checks run
  - second isolated checks run against the same fixtures
- expected result:
  - good fixtures pass
  - broken fixtures fail for the right reason
  - first and second runs match

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - score `>=95` and no automatic-fail condition
- timeout rule:
  - stay in Phase 3 until health truth is deterministic
- next automatic step:
  - start Phase 4

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 4 - F shadow calibration
Goal:
- let F see factor-level truth without changing live buy decisions

Files allowed to change:
- `scripts/flows/F/` scoped files only
- planned tests
- this active plan folder

Implementation tasks:
- create `feeder_feedback_calibration_live.csv`
- feed factor outputs into F summary or review outputs in shadow mode only
- keep current decision outputs visible beside the shadow calibration
- prove scanner outputs remain the scrape truth source
- keep this phase on frozen inputs only

Owner action:
- stop before edit:
  - only a manually running `F061_run_legacy_first_checks_local.py` process if editing that exact script or shared helper files it imports
- restart after phase:
  - none by default

Isolated verification:
- command:
  - scoped F pytest pack
  - `python -m py_compile`
  - first isolated shadow-output run against frozen inputs
  - second isolated shadow-output run against the same frozen inputs
- expected result:
  - shadow output builds
  - live F decision outputs stay unchanged
  - no fresh scrape is triggered
  - first and second runs match

Monitored validation:
- target:
  - none
- cadence:
  - n/a
- success threshold:
  - score `>=95` and no automatic-fail condition
- timeout rule:
  - do not touch H runtime paths until F shadow proof is clean
- next automatic step:
  - start Phase 5

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 5 - H experiment evidence and operator report
Goal:
- make future H tactic changes measurable before strategy tuning changes again

Files allowed to change:
- `scripts/phase1/` scoped files only if needed
- `scripts/cycles/` scoped H runtime files only if needed
- planned report builders under `scripts/one_off/`
- planned tests
- this active plan folder

Implementation tasks:
- add cohort-friendly strategy tags or evidence hooks where needed
- build operator report output
- expose undercut, share, reaction, scrape coverage, and estimate-drift facts in one report pack
- keep isolated proof on frozen inputs before any restart

Owner action:
- stop before edit:
  - request H restart drain by writing:
    - `out/locks/maintenance.requested` with
    - `requested_by=controlled_restart_gate|pid=<pid>|ts=<utc>|reason=overnight_restart_eval|request_id=<id>`
  - wait for `out/systems/H/live/H_restart_drain.ready`
  - confirm no live H owner or worker is still active before editing
- restart after phase:
  - clear drain markers:
    - `out/locks/maintenance.requested`
    - `out/systems/H/live/H_restart_drain.ready`
  - relaunch only through `run_H_cycle.bat`
  - prove a fresh launcher heartbeat and a new H owner process exist

Isolated verification:
- command:
  - scoped H pytest pack
  - `python -m py_compile`
  - 10 isolated frozen replays or equivalent deterministic test runs before restart
- expected result:
  - operator report builds
  - report sources and timestamps are explicit
  - all 10 frozen replays pass with identical result shape

Monitored validation:
- target:
  - `out/systems/H/live/H_runtime_status.json`
  - `out/systems/H/live/H_launcher.heartbeat`
  - `out/systems/H/live/H_cycle_current_run_id.txt`
  - latest terminal markers for the first post-restart run
- cadence:
  - `+5 minutes`
  - `+10 minutes`
  - then every `+15 minutes` up to `+60 minutes`
- success threshold:
  - isolated score `>=95`
  - 10 frozen replays clean
  - H restart ownership restored
  - at least one clean post-restart run observed for operational handoff
- timeout rule:
  - if post-restart proof is incomplete by `+60 minutes`, record exact missing artifact and park as `pending next proof window`
- next automatic step:
  - start Phase 6

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete

### Phase 6 - Sign-off and promotion decision
Goal:
- decide what becomes loop-owned, what stays one-off, and what is ready to archive

Files allowed to change:
- this active plan folder
- only scoped follow-up patches if sign-off exposes a real defect

Implementation tasks:
- rate each deliverable on:
  - code complete
  - result quality
  - sample size
  - proof quality
- document promotion decision clearly
- state runtime truth clearly if H paths changed:
  - `code fix applied`
  - `isolated verification passed`
  - `live loop verification pending` or `confirmed`

Owner action:
- stop before edit:
  - none unless a scoped follow-up fix reopens Phase 5
- restart after phase:
  - none unless a scoped follow-up fix reopens Phase 5

Isolated verification:
- command:
  - only scoped follow-up tests if needed

Monitored validation:
- target:
  - any promoted runtime-owned path only
- cadence:
  - default monitored-validation cadence if promotion happens
- success threshold:
  - deliverable ratings complete and proof language explicit
- timeout rule:
  - if runtime promotion still lacks evidence, sign-off remains `not yet proven`
- next automatic step:
  - archive only when proof requirements are met

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: complete
