# A Cycle Expectations

## Purpose
The A cycle is the daily orchestration layer for core product and health data. It refreshes key datasets, runs required daily steps, and provides health gate evidence for safe downstream use.

Current direction: A is a no-Sheets source-fact cycle. It should refresh local CSV proof and local SQL-compatible facts, while O/UI owns user viewing and user-editable decisions.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Daily orchestration runner | A cycle runs the defined step order end-to-end | In Progress | Manifest evidence exists with full step traversal on recent runs |
| Listings refresh | Listings data is refreshed daily | In Progress | Implemented in A001 flow |
| Catalog refresh | Catalog item data is refreshed daily | In Progress | Implemented in A002 flow |
| Inventory refresh | Inventory snapshot and history are refreshed daily | In Progress | Implemented in A003 flow |
| Fees refresh | Fee estimates are refreshed daily | In Progress | Implemented in A004 flow |
| No-Sheets source-fact path | A refreshes local facts without normal Google Sheets reads/writes | In Progress | 2026-05-26 code split applied for A001/A002/A004 and A runner disables Sheet-only Product DB steps; live A-owned proof still pending |
| Daily intel refresh | Daily intel is rebuilt for repricing support | In Progress | Implemented in A016 flow |
| Floor table support | Floor table support inputs are refreshed | In Progress | A018 is called by H path; daily dependency exists |
| E cycle trigger | A cycle triggers E cycle as part of daily run | In Progress | `run_E_cycle.py` is in A run order |
| Health gate run | A015 health checks run as part of A completion | In Progress | Split/legacy health modes exist |
| Maintenance handoff safety | A waits for B maintenance boundary before critical run | In Progress | Maintenance markers are implemented |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed A runs:
- Fails: count runs where A cycle exits nonzero or has blocking health fail.
- Warnings: count runs with degraded final state, stale evidence, or non-blocking warn outcomes.
- Clean runs: count runs with full traversal, no blocking fail, and current-cycle health evidence.

Suggested scoring baseline:
- Start at 100.
- Subtract 20 if any fail exists in window.
- Subtract 5 per warned run, up to 30.
- Reliability is "To Baseline" until 10 comparable runs are available.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- A run order covers required daily data refresh and health gate scope.
- Listings, catalog, inventory, and fees refresh must run locally even when legacy Google Sheet output paths are disabled.
- Inventory summaries and inventory history must persist through SQL-compatible writers after stale-token-floor correction, so CSV and SQL fallback tables stay aligned.
- Sheet-only Product DB sync steps must not be required for normal A completion.
- User-editable Product DB decisions belong to O/UI edit events and local SQL apply proof, not normal A source-fact refresh.
- Required outputs are produced and evidenced in manifests.
- Stable:
- No blocking fail in last 10 runs.
- At least 8 of last 10 runs are clean.
- Health evidence is current-cycle and not stale.
- Ready for expansion:
- Stable baseline maintained for 2 consecutive review windows.
- Warning causes are understood and controlled.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Faster step timing and runtime optimization.
- Better operator dashboards for A-only diagnostics.
- Additional observability detail beyond current manifest requirements.
- Non-critical report polish and formatting improvements.

## SECTION 5 - Planning Tolerance Gate
- This expectations file defines reliability quality targets. It is not an automatic planning-stop rule by itself.
- Planning and optimisation work may proceed when A scoped hard-block conditions are clear.
- Hard-block examples for A planning:
- active FAIL in A scoped gate
- required A runtime path not operational
- required A outputs stale beyond cadence
- unresolved ownership or crash-loop conditions affecting A operation
- Soft-block examples for A planning:
- accepted non-blocking WARN with clear reason
- "To Baseline" reliability label while runs are still being accumulated
- older aggregate labels that lag newer live A evidence
- Soft-blocks must be reported and tracked, but do not by themselves stop planning.
