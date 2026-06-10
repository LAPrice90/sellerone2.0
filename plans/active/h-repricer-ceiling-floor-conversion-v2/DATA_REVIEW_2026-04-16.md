# H Data Review - 2026-04-16

## Scope
- Purpose:
  - capture the live H evidence that justifies the next plan phase
- Source files:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/h_strategy_outcome_log.csv`
  - `out/system_health_checklist.csv`
  - `out/health_status.csv`

## Headline findings
- The previous plan did its job on false-fail cleanup.
- The next blocker is not generic stability. The next blocker is truth and conversion.
- Ceiling outputs are still carrying invalid effective states.
- Daily strategy rollups are not fully trustworthy yet.
- The strongest current tactic is `RAISE_FIND_LOSS_LADDER_CAP`.
- The weakest current areas are:
  - `multi_seller_ladder_cap` conversion
  - `suppression_reactivation` conversion
  - `controlled_exit` success visibility
  - `SELLER_DETAIL_HOLD` failure handling

## Current evidence

### 1) Ceiling/floor conflict evidence
- Latest ceiling-event run:
  - `run_id=20260416T211441Z`
  - rows: `58`
  - effective ceiling conflicts: `8`
  - conflict rate: `13.79%`
- Latest runtime-floor snapshot:
  - rows: `89`
  - effective ceiling conflicts vs traced floor: `11`
  - conflict rate: `12.36%`
- Conflict shape:
  - all latest ceiling-event conflicts are `COMPLIANCE`-bound
  - target relation on latest ceiling-event conflicts:
    - `target_below_floor`: `4`
    - `target_at_floor`: `4`
- Ceiling input quality:
  - `CEILING_RULE_INPUTS_MISSING`: `37 / 58`
  - `CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK`: `4 / 58`

### 2) Example SKUs showing the current ceiling problem
- `A1-KSU1-GZMS`
  - effective ceiling `3.28`
  - hard floor `3.70`
  - target `2.99`
- `D0-C7C0-H6LN`
  - effective ceiling `6.00`
  - hard floor `7.31`
  - suppression path involved
- `0G-JB6S-PN34`
  - runtime snapshot effective ceiling `2.48`
  - traced floor `6.22`

### 3) Current strategy result picture
- Latest `h_strategy_outcome_daily.csv` date: `2026-04-16`

#### Multi-seller
- `multi_seller_ladder_cap / REGAIN_LADDER_CAP`
  - decisions `1162`
  - applied `584`
  - success `6`
  - failed `0`
  - expired `508`
  - aborted `648`
- `multi_seller_ladder_cap / MULTI_SELLER_LADDER_CAP`
  - decisions `19`
  - applied `4`
  - success `0`
  - failed `0`
  - expired `4`
  - aborted `15`

#### Raise/find-loss
- `raise_find_loss / RAISE_FIND_LOSS_LADDER_CAP`
  - decisions `588`
  - applied `73`
  - success `137`
  - failed `1`
  - expired `54`
  - aborted `396`
- `raise_find_loss / RAISE_SINGLE_RIVAL_RESET`
  - decisions `38`
  - applied `0`
  - success `5`
  - failed `0`
  - expired `6`
  - aborted `27`

#### Share/hold
- `share_hold / HOLD_OBSERVE`
  - decisions `1393`
  - success `45`
  - failed `0`
  - expired `52`
  - aborted `1289`
- `share_hold / RISK_GATED_HOLD`
  - decisions `304`
  - success `0`
  - failed `0`
  - expired `0`
  - aborted `303`
- `share_hold / SELLER_DETAIL_HOLD`
  - decisions `189`
  - success `22`
  - failed `23`
  - expired `143`
  - aborted `0`

#### Suppression and exit
- `suppression_reactivation / SUPPRESSION_REACTIVATION`
  - decisions `126`
  - success `1`
  - failed `0`
  - expired `78`
  - aborted `45`
- `controlled_exit / CONTROLLED_EXIT_TO_FLOOR`
  - decisions `11`
  - applied `11`
  - success `0`
  - failed `0`
  - expired `11`
  - aborted `0`

### 4) Rollup integrity issue
- Latest daily rows include impossible count relationships:
  - `multi_seller_ladder_cap / MULTI_SELLER_LADDER_CAP`
    - `decision_rows=19`
    - `at_floor_rows=605`
  - `suppression_reactivation / SUPPRESSION_REACTIVATION`
    - `decision_rows=126`
    - `at_floor_rows=189`
- This means the operator rollup is not yet safe to use as the only scorecard.

### 5) Health state
- Latest health status row:
  - `2026-04-16T19:59:56.744273+00:00, OK, fail=0, warn=0`
- Important note:
  - this health snapshot is older than the latest H strategy data above
  - it is clean, but stale for proving the new phase

## What is working
- False-fail cleanup from the previous plan appears to be holding.
- `raise_find_loss_ladder_cap` is producing the best current success volume.
- H is stable enough to generate useful data for the next planning phase.

## What is not working
- Effective ceiling contract is still broken in current live outputs.
- Operator rollup integrity is broken.
- Multi-seller and suppression conversion remain weak.
- Controlled exit does not yet show positive success evidence.
- Seller-detail hold still carries real failed rows.

## Planning conclusion
- Phase order should be:
  1. fix truth contracts
  2. fix ceiling source behavior
  3. optimise tactic conversion using the cleaned evidence
- Do not start with more strategy tuning while the truth layer is still wrong.
