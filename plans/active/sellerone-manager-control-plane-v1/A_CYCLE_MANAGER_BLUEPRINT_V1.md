# A Cycle Manager Blueprint V1

## Purpose

A is the daily source-fact cycle.

Its job is to refresh the facts the rest of SellerOne depends on:
- listings
- catalog
- inventory
- fees
- daily repricing intel
- A health proof
- safe handoff around the B loop

The manager is not the A business UI and not a repair project by default. The manager is the inspector. It checks whether A really left fresh proof, whether the proof is old or missing, and whether Codex can safely create a bounded task without dragging Luke into raw script detail.

## What A Should Do Each Morning

A should:
- ask for the B maintenance boundary before critical refresh work
- refresh local no-Sheets source facts
- write CSV proof files
- write SQL-compatible proof tables where the source supports it
- trigger E as part of the daily chain
- run the A health gate at the end
- clear maintenance markers after completion
- write a durable maintenance handoff proof artifact

Normal A must not depend on Google Sheets reads or writes.

## Proof Files The Manager Reads

Main proof:
- `out/manifests/A/**/*.json`
- `out/cycle_alerts/checklist_A.csv`
- `out/cycle_alerts/checklist_A_split.csv`
- `out/systems/M/hourly_mot_A.csv`
- `out/systems/M/mot/mot_latest.csv`

Source-fact proof:
- `out/merchant_listings_latest.csv`
- `out/catalog_items_flat.csv`
- `out/inventory_summaries.csv`
- `out/inventory_history.csv`
- `out/inventory_snapshot_latest.csv`
- `out/fees_latest.csv`
- `out/phase1_daily_intel_latest.csv`

SQL proof:
- `a_inventory_summaries`
- `a_inventory_history`
- `a_inventory_snapshot_latest`
- `a_fees_latest`
- `a_phase1_daily_intel_latest`

Proof-only A018 floor support:
- `out/phase1_floor_table_latest.csv`
- optional SQL table `a_phase1_floor_table_latest`

Maintenance handoff proof:
- `out/systems/A/live/a_maintenance_handoff_latest.json`
- `out/systems/A/history/a_maintenance_handoff_history.jsonl`

## What Failure Looks Like

Real A failure:
- latest A manifest is missing, stale, partial, or failed
- required source-fact file is missing, stale, empty, or unreadable
- required SQL proof table is missing or empty
- A checklist has active FAIL rows
- A maintenance handoff proof records unsafe overlap, timeout, or uncleared markers

Proof gap, not runtime failure:
- A018 floor table proof is missing or stale during this batch
- A018 SQL proof is missing while A018 is still proof-only
- latest A run is newer than the handoff proof because the proof writer has not run yet

The manager must not turn proof-only gaps into fake runtime failures.

## What Codex Can Do Without Luke

Codex can create or complete manager-approved tasks for:
- improving manager proof mapping
- adding read-only MOT checks
- adding A runner proof-writing
- fixing code-only no-Sheets leaks
- adding focused tests
- moving a manager task to `fixed_needs_retest` after isolated tests pass

Codex must stay inside the approved task packet.

## When Luke Must Be Interrupted

Luke is needed if the next step requires:
- a live A proof run
- B intervention or restart
- Google Sheets read/write
- local DB alignment or data correction
- queue edits
- pricing changes
- output deletion
- scope widening outside the approved A packet

Luke should not be interrupted just because A has a routine proof gap that Codex can map or test safely.

## Current V1 Decision

A018 stays proof-only in this batch.

That means:
- do not add `A018_build_phase1_floor_table.py` to the A run order yet
- do not change floor values
- do not change H repricing behavior from this A blueprint
- manager may read A018 proof if it exists
- missing A018 proof stays `not_verified`, not an A runtime FAIL

## Acceptance

A manager blueprint V1 is ready when:
- A MOT still proves current source facts without running A
- A018 proof-only rows appear as `ok` when present and `not_checked` when missing
- maintenance handoff proof can be read by MOT and manager reconciliation
- manager expectation reconciliation can close A to 11 of 11 covered when floor and handoff proof exist
- failed handoff proof blocks A honestly
- tests pass without running A or A015
