# F Scanner Timeout Policy - Build Spec

Date: 2026-05-01

## Purpose
Create an operator-editable timeout policy for scanner fail reasons.

When F061 scans a supplier row and it fails, the fail reason should decide when that barcode/candidate is allowed to be scanned again.

This must keep the scanner efficient without hiding failures or pretending old results are still valid forever.

## Current State
F061 currently has fail and retry codes in `scripts/flows/F/F061_run_legacy_first_checks_local.py`.

Current fail codes:
- `NOASIN`
- `OVER50K`
- `HAZMATFAIL`
- `NOCOST`
- `ROIFAIL`
- `LOWROI`
- `BRANDFAIL`
- `NODATE`
- `REVIEWFAIL`
- `SCRAPEFAIL`
- `LOWSALESFAIL`
- `SELLERHISTORYFAIL`
- `PRICEHISTORYFAIL`
- `FAIL`

Current retry code:
- `RESCAN`

There is also a hardcoded timeout table in F061:
- `NOASIN`: 240 minutes
- `OVER50K`: 720 minutes
- `HAZMATFAIL`: 1440 minutes
- `NOCOST`: 240 minutes
- `ROIFAIL`: 720 minutes
- `LOWROI`: 240 minutes
- `BRANDFAIL`: 1440 minutes
- `NODATE`: 240 minutes
- `REVIEWFAIL`: 180 minutes
- `SCRAPEFAIL`: 120 minutes
- `LOWSALESFAIL`: 720 minutes
- `SELLERHISTORYFAIL`: 1440 minutes
- `RESCAN`: 60 minutes
- `FAIL`: 240 minutes

Those values are too short for long-term supplier list management and should become configurable.

## Core Rule
Do not use timeout policy to mask bad scanner output.

Timeouts decide when to rescan. They must not change:
- the original fail reason
- PASS/FAIL/RESCAN counts
- scanner evidence
- review handoff outputs

## Required Investigation For Next Chat
Before coding values permanently, investigate each fail reason with the user:
- what causes the fail
- which scanner stage produced it
- how expensive it is to reach that fail
- whether a retry is likely to change the outcome
- what would make it worth retrying earlier, such as supplier cost changing
- whether the timeout should be fixed days, until cost changes, or until user decision

## Suggested Starting Timeout Discussion
Final balanced v3 policy values after user review:
- 90 days is the standard wait for normal commercial/data failures.
- 180 days is the high end for slow-moving evidence.
- 365 days is reserved for hazmat or FBA eligibility.
- `PRICEHISTORYFAIL` is split out from `RESCAN` because no usable 365-day price history is not the same as a technical retry.

| Fail reason | Meaning | Cost to discover | Likely to change soon? | Timeout policy |
|---|---|---:|---|---|
| `NOASIN` | Barcode did not resolve to Amazon ASIN | Cheap | Low in short term | 90 days |
| `OVER50K` | Rank/demand too weak | Cheap/medium | Medium | 90 days |
| `HAZMATFAIL` | Not FBA eligible / hazmat issue | Medium | Low | 365 days |
| `NOCOST` | Missing/invalid supplier cost | Cheap | Only if source changes | until cost changes, max 90 days |
| `ROIFAIL` | ROI clearly fails | Medium | Only if cost/market changes | until cost changes, max 90 days |
| `LOWROI` | ROI weak/near fail | Medium | Medium | until cost changes, max 60 days |
| `BRANDFAIL` | Brand/seller conflict | Expensive | Low | 180 days |
| `NODATE` | Missing product/date history | Expensive | Medium over time | 90 days |
| `REVIEWFAIL` | Review evidence failed | Expensive | Medium | 90 days |
| `SCRAPEFAIL` | Unknown technical scrape failure | Expensive but technical | High | 30 days |
| `LOWSALESFAIL` | Sales too low | Expensive | Medium | 90 days |
| `SELLERHISTORYFAIL` | Seller/history risk block | Expensive | Low until history window moves | 180 days |
| `PRICEHISTORYFAIL` | No usable 365-day price history | Expensive | Low until history fills in | 180 days |
| `RESCAN` | Technical retry needed | Variable | High | 30 days |
| `FAIL` | Generic fail fallback | Unknown | Unknown | 90 days, and investigate why generic |

`RESCAN` reasons currently seen in F061:
- catalog API transient error: `http_429`, request exception, or HTTP 5xx
- catalog candidate lookup transient error: `http_429`, request exception, or HTTP 5xx
- browser or scraper retry condition: `CHROMEVERSIONFAIL`
- review page timeout: `REVIEWS_TIMEOUT`
- incomplete price-history capture: `INCOMPLETE_PRICE_HISTORY_CAPTURE`
- scraper disabled for the run: `SCRAPE_DISABLED`

`NO_PRICE_HISTORY_365D` must map to `PRICEHISTORYFAIL`, not `RESCAN`.

## Required Design
Add a policy file owned by F, not Google Sheets.

Recommended path:
- `config/feeder/f_scanner_timeout_policy.csv`

Required columns:
- `fail_code`
- `enabled`
- `timeout_mode`
- `timeout_days`
- `max_timeout_days`
- `cost_change_resets_flag`
- `source_change_resets_flag`
- `manual_review_required_flag`
- `notes`
- `updated_at_utc`

Allowed `timeout_mode` values:
- `fixed_days`
- `until_cost_changes`
- `until_source_changes`
- `manual_review`
- `disabled`

Rules:
- unknown fail code must not crash the scanner
- unknown fail code should use `FAIL` fallback and produce a health WARN
- disabled policy means no cooldown skip for that code
- manual review policy means do not rescan automatically until operator clears it
- cost/source-change reset must be checked before applying the timeout

## UI Requirement
Add settings in the existing Streamlit operator UI, not a separate app.

Recommended location:
- Price List Queue tab
- collapsed expander near the bottom: `Scanner Timeout Settings`

UI format:
- table/grid with one row per fail code
- editable `timeout_mode`
- editable `timeout_days`
- editable `max_timeout_days`
- checkboxes for cost/source/manual flags
- notes column
- save button
- reset-to-defaults button

Keep it simple and readable:
- show fail reason
- show current setting
- show plain-English meaning
- avoid hiding the fail code, because the logs use the fail code

Do not auto-save every keystroke. Use a clear save action.

## Data Flow
1. F061 produces `f_screening_row_state_live.csv` with `fail_code` and `timeout_until_utc`.
2. New timeout policy replaces the hardcoded timeout table.
3. Price-list manager reads screening memory and timeout policy.
4. Manager skips rows still inside timeout unless reset conditions apply.
5. UI lets the operator edit policy.
6. Health checks report missing, invalid, or unknown policy codes.

## Required Health Checks
Add health rows for:
- policy file exists
- all known fail codes have exactly one policy row
- unknown fail codes in scanner state are reported
- timeout values are valid numbers where required
- manual-review rows are not silently rescanned
- fallback `FAIL` policy exists

Health must be truthful. Do not suppress warnings just because they are expected during setup.

## Required Tests
Add focused tests for:
- default policy file can be created/read
- every known fail/retry code has a policy row
- unknown fail code falls back to `FAIL` and warns
- `fixed_days` calculates correct `timeout_until_utc`
- `until_cost_changes` skips only when cost is unchanged
- `manual_review` blocks automatic rescan
- UI save writes only the policy file
- no Google Sheets writes

## What Not To Touch
Do not change:
- PASS/FAIL logic
- scanner scrape behavior
- API timing/rate limits
- live queue ownership
- review handoff logic
- Google Sheets

## First Implementation Target
Build the policy layer in read-only/default mode first:
- create/read default policy
- keep current hardcoded values as defaults
- write health checks
- show UI settings
- do not change live skip decisions yet

Then, after user agrees the timeout values:
- wire policy into F061 timeout calculation
- wire policy into price-list manager skip decisions

## Handoff Prompt For Next Chat
Implement `F_SCANNER_TIMEOUT_POLICY_SPEC.md`.

Start by investigating the current F061 fail codes and timeout behavior with the user. Do not pick final timeout values alone.

Build the policy file and UI settings first, using the current hardcoded values as defaults. Keep live scanner behavior unchanged until the user approves the timeout values.

Required anchors:
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/*`
- `scripts/flows/O/O400_operator_ui.py`
- `config/feeder/f_scanner_timeout_policy.csv`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`

Proof required:
- focused pytest passes
- UI can load/edit/save policy
- health reports policy state
- no Google Sheets changes
- no live scanner speed or queue behavior changes in first phase
