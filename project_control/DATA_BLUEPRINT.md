# Data Blueprint Registry

## Purpose
The Data Blueprint Registry is the single source of truth for SellerOne datasets.

It exists to make dataset ownership, canonical paths, approved writers, approved consumers, and scoring status explicit in one place.

The canonical registry table is:
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`

This document is the policy and explanation guide for using that registry.

## What A Dataset Family Is
A dataset family groups related datasets by business and operational purpose.

Current family model:
- `Finance`
- `Tokens`
- `Inventory`
- `Market_Intel`
- `Repricing_Intelligence`
- `Analytics`
- `Inbound_Logistics`
- `Health_Governance`
- `Runtime_Control`

Each registry row must have exactly one primary `dataset_family`.

## Registry Rules
- One row represents one dataset family item.
- Do not create separate primary rows for canonical path and mirror path of the same dataset.
- Every row must declare one `owner_cycle`: `A`, `B`, `C`, `E`, `H`, or `System`.
- Every row must declare one `canonical_path`.
- Mirror paths are optional and must be listed in `allowed_mirror_paths`.
- `writer_scripts` and `consumer_scripts` must reflect currently approved/observed usage.
- `status` must be one of:
- `Unscored`
- `Baselining`
- `Scored`

## Scoring Dimensions
Each scored dataset has four component scores on a `0` to `10` scale:
- `freshness_score_0_10`
- `reliability_score_0_10`
- `completeness_score_0_10`
- `decision_importance_0_10`

Guidance:
- Freshness: whether updates happen at expected cadence.
- Reliability: stability across runs and low failure/staleness behavior.
- Completeness: expected columns/fields and usable content are present.
- Decision Importance: operational impact if wrong or stale.

## Score Formula
`overall_data_performance_score_0_10` is calculated as:

`overall = 0.25 * freshness + 0.35 * reliability + 0.20 * completeness + 0.20 * decision_importance`

Store rounded value to 2 decimal places.

## Cycle Score Rollup Logic
Cycle scores are computed as importance-weighted averages of datasets owned by that cycle.

For cycle `X`:

`cycle_score_X = sum(dataset_overall * decision_importance) / sum(decision_importance)`

Rules:
- Include only rows where `owner_cycle = X`.
- Include only rows with `status` of `Baselining` or `Scored`.
- If no eligible rows exist, cycle status remains `To Baseline`.

Family scores can be rolled up the same way, grouped by `dataset_family`.

## Canonical Path vs Mirror Path Rules
- Canonical path is the primary operational read/write authority for that dataset row.
- Mirror paths are allowed compatibility targets only.
- A mirror path must never be treated as a separate primary dataset row.
- If both canonical and mirror are still in active use, keep one row and note compatibility in `notes`.

## Enforcement Targets
The registry is intended to enforce the following once guard checks are implemented:
- Every critical dataset has a declared owner cycle.
- Every critical dataset has one canonical path.
- Multiple writers require explicit registry approval.
- Unregistered `out/` writes are flagged.
- Non-canonical reads are flagged unless mirror-approved.
- Critical datasets must be at least `Baselining`, not permanently `Unscored`.

## Adding Future Datasets
When adding a new dataset:
1. Add one registry row in `DATA_BLUEPRINT_REGISTRY.csv`.
2. Assign `dataset_id`, `dataset_family`, and `owner_cycle`.
3. Set canonical path and any approved mirror paths.
4. List writer and consumer scripts.
5. Set `status`:
- `Unscored` only when evidence is truly insufficient.
- `Baselining` when provisional scoring can be justified.
- `Scored` when evidence window is mature.
6. Add schema header reference and clear notes.
7. Set `last_scored_utc` when component scores are populated.

## Initial Critical Dataset Coverage
This first implementation covers critical families:
- `Finance`
- `Tokens`
- `Inventory`
- `Market_Intel`
- `Repricing_Intelligence`
- `Analytics`
- `Inbound_Logistics`
- `Health_Governance`

It includes core transactional, token, inventory, repricing, analytics, checklist, and manifest dataset rows required for phase-1 registry governance.

## H Floor Health Governance Policy
Owner: `H` cycle

Review window:
- 30 days from policy adoption, then renew, resolve, or reclassify.

Current check classification:
- Temporary Baselining Exception:
- `h_floor_no_order_inputs`
- `h_floor_referral_source_coverage`
- `h_floor_referral_source_coverage_parked_observability`
- Fix Immediately:
- `h_floor_formula_consistency`
- Conditional (Fix or Exception depending on active dependency):
- `h_floor_referral_band_integrity`

Scoring impact:
- Repricing datasets must not be promoted from `Baselining` to `Scored` while unresolved `h_floor_*` checks remain without a documented exception state.

## Runtime Control Dataset Policy
The following runtime control datasets are classified as Non-Scored Governance Signals:
- `H_runtime_status`
- `H_launcher.lock`
- `B_cycle.lock`
- `restart_controller.latest.json`

Rules:
- Excluded from Data Performance Score rollups.
- Monitored via presence and freshness SLA checks.
- Used for runtime diagnostics and control safety only.
- If later used as direct decision data, scoring eligibility can be reviewed.

## Dataset Promotion Criteria
A dataset may move from `Baselining` to `Scored` only when all criteria are met:
- Stable write cadence is observed over a defined evidence window.
- Canonical writer is explicitly defined.
- No unresolved ownership conflict exists.
- Relevant health checks are passing, or a documented exception is active.
- Schema is stable for required fields.
- No active downstream WARN dependencies are unresolved.
- Manifest integrity is confirmed where applicable.
