# A Cycle Blueprint

## Plain-English Purpose
A is the daily setup cycle.

Think of it like opening the warehouse and office in the morning:
- check what products exist
- check what Amazon says is live
- check what stock exists
- check what fees and costs look like
- refresh the local source facts that other flows depend on
- rebuild the daily support data for pricing and restocking
- run a health check at the end

A should give the rest of SellerOne a fresh, trusted starting point for the day.

## What A Is Not
A is not the repricer.
A is not the supplier scanner.
A is not the UI.
A should not be treated as a place to browse business data.

A is a refresh-and-proof cycle. It prepares the daily source facts.

## No-Sheets Direction
A is moving away from Google Sheets as the normal daily path.

Plain-English version:
- A collects the facts.
- O/UI shows the facts and records user decisions.
- Manager/MOT checks whether the facts are fresh, complete, and safe to trust.

Normal A should write local CSV proof and local SQL-compatible facts. It should not use Google Sheets as the normal read or write path, and it should not directly change user-editable Product DB decisions during normal source-fact refresh.

Old script names may still say `to_sheet` while the migration is in progress. The name is legacy wording. The intended normal behavior is local proof first, with legacy Sheet writing disabled unless Luke explicitly approves that exact action.

Current default switches:
- `A_SKIP_LEGACY_SHEET_OUTPUT_STEPS=1`
- `A001_WRITE_LEGACY_SHEETS=0`
- `A002_WRITE_LEGACY_SHEETS=0`
- `A004_WRITE_LEGACY_SHEETS=0`
- `A_ENABLE_STOCK_RECEIPTS_SHEET=0`

## How A Starts
The normal entrypoint is:

```text
run_A_all.bat
```

That calls:

```text
scripts/cycles/run_A_all.py
```

The runner does three important control jobs:
- prevents two A runs from overlapping
- asks B for a safe maintenance boundary before A does critical daily work
- writes a manifest so the manager can see which steps ran and where they stopped

## Current A Script Order
This is the order currently declared in `scripts/cycles/run_A_all.py`.

| Step | Script | Simple job | Main proof/output |
|---|---|---|---|
| 1 | `A001_run_listings_to_sheet.py` | Ask Amazon what listings are live and save the latest listing facts. | `out/merchant_listings_latest.csv` |
| 2 | `process_stock_receipts_sheet.py` | Legacy stock receipt Sheet intake. Disabled by default until O/UI receipt events replace it. | `out/stock_receipts_latest.csv` |
| 3 | `A002_run_catalog_items_to_sheet.py` | Ask Amazon for catalog details like title, brand, images, size, package fields, and identifiers. | `out/catalog_items_flat.csv` |
| 4 | `A003_run_inventory_to_sheet.py` | Refresh FBA stock, inbound stock, reserved stock, unsellable stock, and stock history. | `out/inventory_summaries.csv`, `out/inventory_history.csv` |
| 5 | `A004_run_fees_to_sheet.py` | Refresh Amazon fee estimates so profit and pricing logic has current fee inputs. | `out/fees_latest.csv`, `out/fees_failed.csv` |
| 6 | `A010_apply_researching_delta.py` | Apply inventory researching changes through the existing B010 logic. | `out/researching_delta_events.csv` |
| 7 | `A005_run_inventory_adjustments_report.py` | Pull Amazon stock adjustment and ledger evidence for observation and audit. | `out/inventory_adjustments_latest.csv` |
| 8 | `A016_refresh_phase1_daily_intel.py` | Build daily SKU intelligence used by H/pricing support. | `out/phase1_daily_intel_latest.csv` |
| 9 | `run_E_cycle.py` | Rebuild E analytics after A has refreshed core inputs. | `out/e_run_log.jsonl` |
| 10 | `A020_run_daily_finance.py` | Run the daily finance/token/P and L jobs that used to make B heavier. | finance, token, and P and L outputs |
| 11 | `A015_build_system_health_check.py` | Build the end health checklist so the system knows whether A is safe enough. | `out/cycle_alerts/checklist_A.csv` |

## Script That Exists But Is Not In The Current A Run Order
`A006_build_stock_events_raw.py` exists, but it is not currently in the declared A run order.

Plain-English meaning:
- it can build raw stock event rows from inventory ledger evidence
- the manager should not assume it is part of the daily A run until the runner actually calls it

## Legacy Product DB Sheet Steps
These old Sheet-only steps are no longer part of the normal no-Sheets A run order:

- `dedupe_product_db.py`
- `sync_product_db_to_main_sheet.py`

Plain-English meaning:
- do not treat them as daily proof that A is healthy
- do not re-add them to normal A just to make an old Sheet path look complete
- keep them as legacy reference until O/UI and local SQL proof replace the old behavior fully

## What The Manager Should Understand About A
The manager should not start by shouting about warnings.

The manager should first know this simple story:

```text
A refreshes the daily source facts.
If A is fresh and trustworthy, B/E/H/O can use its outputs.
If A is stale or broken, later flows may be working from old facts.
```

## What The Manager Should Check For A
The manager should check these things quietly:

- Did one A run start, with no overlapping A run?
- Did A respect the B maintenance handoff?
- Did the manifest record every configured step?
- Did each required output refresh after its step ran?
- Did A015 write a fresh A checklist?
- Did any step fail in a way that stops later steps?
- Did any step skip for a known safe reason?
- Did Sheet-writing steps run only when allowed?
- Did the final state say completed, partial, or failed?

## Independent Hourly MOT
A must not be trusted only because A says it is running or completed.

That is how silent failures happen:
- the cycle dies before it writes its failure
- the UI keeps showing an old running state
- a stale file looks like a current answer
- downstream flows keep using old stock, listing, or fee data

So A needs an independent MOT check.

The independent MOT does not run A. It does not call Amazon. It does not use AI tokens.

It only reads proof that should already exist:
- latest A manifest
- required A output files
- file ages
- row counts
- A checklist
- local database tables that should receive A data
- stale A lock files

The first A MOT command is:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow A
```

It writes:

```text
out/systems/M/mot/mot_latest.csv
out/systems/M/mot/mot_latest.json
out/systems/M/mot/mot_latest.md
out/systems/M/mot/mot_history.jsonl
out/systems/M/mot/mot_worklist.csv
out/systems/M/mot/mot_retest_queue.csv
```

This is the no-token reviewer layer. The AI should read these small files instead of burning tokens digging through raw script logs.

The hourly Windows runner is:

```text
run_manager_hourly_mot.bat
```

The installer for the scheduled task is:

```powershell
sellerone_manager/install_manager_hourly_mot_task.ps1
```

## What Should Interrupt Luke
Luke should only be interrupted for A when a real decision is needed.

Examples:
- stock receipt rows need a business correction, such as duplicate batch IDs or unclear receipt data
- credentials or access are missing
- a repair would need permission to write legacy Sheets
- a business rule is unclear, such as how a product should be treated
- Codex needs approval to change worker scripts

Luke should not be interrupted just because:
- a normal output exists
- a known warning is still present
- the manager found a technical task Codex can handle quietly

## What Codex Can Usually Handle Quietly
Codex can usually prepare manager-owned work for A without asking Luke:

- document what each A script is meant to do
- add manager checks for script inputs and outputs
- compare expectation files against real script behavior
- create bounded repair tasks
- improve proof wording
- classify whether an issue is blocker, warning, stale evidence, missing proof, user decision, or noise

Codex should not edit A worker scripts until there is an approved task with:
- allowed files
- forbidden files
- proof path
- rollback path
- stop condition

## Proof Rule For A
Do not prove A by running `A015_build_system_health_check.py` on its own.

That only checks health. It does not prove the full A cycle ran properly.

A proof should come from:
- the A run manifest
- the A-owned checklist
- the required output files from the relevant step
- an approved A-owned proof window if a manual proof run is needed

## A Manager Setup Goal
For each A script, the manager should eventually have a small record that says:

- what the script is for
- what it reads
- what it writes
- what success looks like
- what failure looks like
- what Codex can fix quietly
- what needs Luke
- what proof confirms the script is healthy

That is the useful blueprint work before chasing live warnings.
