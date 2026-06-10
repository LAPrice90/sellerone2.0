# A Hourly Read-Only Data Watch Design

Created: 2026-06-09 18:15 UK
Owner: Rep
Status: management design, not implemented

## Plain-English Decision

The hourly A task should not run the full morning A cycle.

The better design is:

- daily A does the real data pull
- hourly A becomes a read-only data watch
- no hourly maintenance mode
- no hourly B handoff
- no hourly full source refresh

## Why This Exists

Luke remembered the reason correctly:

- the system needed a daytime check for data timing and miscounts
- but the current hourly task solves that by running the whole A morning pull again
- that creates crossed wires because A is the morning source-data cycle

The useful part is the checking.

The bad part is using full A to do it.

## Current Problem

`AMZ Pricing Summary Hourly` currently runs:

- `run_A_all.bat`
- which runs `run_A_all.py`
- which requests A/B maintenance handoff
- which refreshes source data and health evidence

That means the hourly job can:

- interrupt F maintenance/proof windows
- interfere with B handoff timing
- create partial A runs during the day
- make row-count changes look like business movement when they are really timing overlap
- refresh some files while other cycles are reading older files

## Target Design

### 1. Daily A Morning Pull

Purpose:

- the real source-data refresh
- listings
- catalogue
- inventory
- fees
- daily intel
- finance
- health evidence

Schedule:

- once per morning, currently 06:00

Maintenance:

- yes, because this is the full source-data writer

Rule:

- this remains the only normal full `run_A_all.bat` scheduler entry

### 2. Hourly A Data Watch

Purpose:

- check whether the latest completed A data still looks safe to use
- detect timing problems, stale outputs, count drops, duplicate spikes, and missing proofs
- warn Operations without changing source data

Schedule:

- hourly, or every 30 minutes if needed

Maintenance:

- no

Rule:

- read-only only
- writes only a small report/status file
- must not run `run_A_all.bat`
- must not ask B for handoff
- must not refresh source facts

### 3. Safe Refresh Request

Purpose:

- if the hourly watcher finds a real issue, it raises a request instead of fixing it by running A

Possible outcomes:

- warning only
- request next safe A proof window
- request tomorrow morning A attention
- request Luke approval if the repair would touch protected data

Rule:

- the watcher does not self-start a full A run

## How It Avoids Maintenance Mode

The hourly watcher avoids maintenance mode because it does not write the files other cycles depend on.

It reads:

- latest successful A manifest
- latest A output timestamps
- row counts
- duplicate counts
- key source file ages
- B/F/O consumer evidence where useful

It writes:

- one small hourly status report
- one optional alert file

Because it is not changing the source-data floor, it does not need to ask B or other cycles to stop walking across it.

## Snapshot Rule

Daily A should publish data like a completed delivery.

The system should only trust:

- latest successful A snapshot
- latest successful A manifest
- outputs from a fully completed A run

The hourly watcher should never promote a partial A run as safe.

If the latest A run is partial:

- keep using the last successful snapshot
- report the partial run
- do not let downstream cycles treat the partial run as a clean refresh

## What The Hourly Watcher Should Check

Minimum checks:

- latest successful A run age
- latest A run state: completed or partial
- row counts compared with the last successful snapshot
- sudden drops in listings, catalogue, inventory, fees, or daily intel
- duplicate SKU or ASIN spikes
- missing required outputs
- files modified while the run was incomplete
- B/F/O reading a stale or mixed A snapshot
- whether any maintenance marker is active

## Example Outputs

The watcher should produce a plain status like:

- green: latest A data safe
- amber: latest A data ageing or minor count warning
- red: latest A data unsafe, keep last successful snapshot
- blocked: cannot judge because evidence is missing

Example business wording:

- "A data is safe. Last full A completed at 06:00."
- "A data warning. Inventory row count dropped 18 percent against last successful snapshot."
- "A data unsafe. Latest A run was partial, so downstream cycles should keep using the last successful snapshot."

## What It Must Not Do

The hourly watcher must not:

- run full A
- request maintenance handoff
- refresh listings
- refresh catalogue
- refresh inventory
- refresh fees
- write Google Sheets
- align databases
- change prices
- change outputs used by live cycles
- restart B, F, H, O, or any scheduler task
- hide a partial A run by making reports look clean

## What Happens To `AMZ Pricing Summary Hourly`

Recommended future decision:

- retire or disable the current hourly full-A task
- replace it with a new read-only watcher task

Do not make that permanent scheduler change during the F emergency unless Luke explicitly approves it as a scheduler cleanup action.

## Success Definition

This design is successful when:

- daily A remains the only normal full A source-data pull
- hourly checking continues without maintenance mode
- hourly checking does not block F
- partial A runs are not treated as clean data
- downstream cycles can tell which A snapshot is safe
- Operations gets a simple green/amber/red data status

## Recommended Worker Ticket

Job ref:

- `A-HOURLY-READ-ONLY-DATA-WATCH`

Worker scope:

- map which A outputs were being protected by the hourly task
- design the read-only watcher checks
- create the watcher in preview/report-only mode
- do not change Task Scheduler until reviewed
- recommend whether to retire `AMZ Pricing Summary Hourly`

Priority:

- after F emergency is resolved, unless hourly A continues to block F tonight
