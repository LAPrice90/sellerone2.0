# Evidence Baseline

Date: 2026-04-23
Source artifacts:
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`

## Current Counts
- Clean Pass rows after demand routing: `226`
- Near-miss review rows after demand routing: `3096`
- Demand-routed remove-from-clean-pass rows already moved by Issue 1: `38`
- Demand-routed manual-review rows already moved by Issue 1: `2`

## Issue 2 Count
- Rule candidate: clean Pass row has direct history-risk conflict.
- Affected clean Pass rows: `149`
- Clean Pass rows without direct history conflict: `77`

## Direct Signal Counts
These counts overlap because one ASIN can have several history-risk signals.

| Signal | Count |
|---|---:|
| `history_recommendation=FAIL` | `109` |
| `phase_recommendation=AVOID` | `109` |
| `backtest recommendation=Avoid` | `102` |
| `commercial_note=Avoid` | `99` |
| `commercial_note=Exit-only` | `38` |

## Stronger Combined Groups
| Group | Count |
|---|---:|
| `history_fail_phase_avoid` | `109` |
| `backtest_avoid_commercial_avoid_or_exit` | `99` |
| `failure_events_100_plus` | `66` |
| `selloff_days_exceed_normal_days` | `58` |
| `exit_only_clean_pass` | `38` |

## Highest Priority Examples
| ASIN | Supplier SKU | Expected profit | Units | History | Phase | Backtest | Commercial |
|---|---:|---:|---:|---|---|---|---|
| `B0D7J4KKK5` | `1322103` | `446.28` | `12` | `FAIL` | `AVOID` | `Exit-only` | `Exit-only` |
| `B097M66Y91` | `1178650` | `344.52` | `99` | `FAIL` | `AVOID` | `Avoid` | `Avoid` |
| `B0CDC154RH` | `1274797` | `223.85` | `10` | `FAIL` | `AVOID` | `Avoid` | `Avoid` |
| `B08X2K5GZ2` | `1169877` | `147.90` | `15` | `FAIL` | `AVOID` | `Avoid` | `Avoid` |
| `B0BWNFBGQR` | `1222030` | `118.49` | `17` | `FAIL` | `AVOID` | `Avoid` | `Avoid` |

## B0C8C3JF9X Context
- `B0C8C3JF9X` is no longer in clean Pass after Issue 1 demand routing.
- It still demonstrates the issue:
  - `backtest_decision_state=pass`
  - `commercial_note=Avoid ... PASS`
  - `watch_data_summary` includes `history_recommendation=FAIL`
- This should become supporting evidence in the history-risk rules.

## Data Sufficiency
- Enough stored data exists for a read-only history-risk audit.
- No new scrape data is needed for the first audit.
- Seller stock remains out of scope for this issue.

## Post-Proof Update (2026-04-23)
- Audit rebuilt from pre-upstream-routing pass snapshot:
  - `out/analysis_reports/f_live_price_file_pass_review_20260423T133613Z.csv`
- Audit output:
  - `out/analysis_reports/f_history_risk_pass_conflict_audit_latest.csv`
  - `audit_output_rows=226`
  - `remove_from_clean_pass=147`
  - `allow_if_other_checks_pass=79`
- Audit `history_risk_code` counts:
  - `history_fail_phase_avoid=109`
  - `backtest_avoid_commercial_avoid_or_exit=16`
  - `exit_only_clean_pass=22`
  - `history_risk_clear=79`
- Upstream routing proof after F019:
  - clean Pass before rebuild: `226`
  - clean Pass after rebuild: `79`
  - history-routed remove rows (F019 summary): `175`
  - history-routed manual-review rows (F019 summary): `0`
  - demand routing still active: remove `10`, manual `2`
- F021 final fail-type counts after rebuild:
  - `type_1_data_or_calc=1119`
  - `type_2_known_policy_or_memory=1`
  - `type_3_missing_evidence_rescan_needed=2153`
