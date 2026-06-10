# SO21 Data Lifecycle And Dedup Plan

Created: 2026-06-08
Status: planning

## Plain-English Purpose

SellerOne pulls a lot of raw data and only uses a small amount of it.

The goal is to stop raw output from piling up by creating a proper data lifecycle:

- collect
- clean
- deduplicate
- keep the useful current data
- archive useful proof
- remove useless temporary data after approval
- automate the safe parts

## Current Problem

SellerOne currently stores too much raw output.

The `out/` folder is mixed:

- live runtime data
- raw imports
- derived reports
- proof history
- backups
- temp/debug leftovers
- partial failed-run outputs
- old snapshots

Because the data is mixed, workers avoid cleanup or keep everything. That creates storage pressure and makes it harder to tell which data matters.

## Business Goal

Luke should not have to manually inspect huge folders to know what can be kept or cleaned.

SellerOne should know:

- what data is live
- what data is raw source proof
- what data is derived and rebuildable
- what data is duplicate
- what data is old but useful audit history
- what data is useless temp/debug output
- what can be cleaned automatically
- what needs approval before cleanup

## Proposed Data Lifecycle

### 1. Raw Landing

Raw supplier, Amazon, browser, API, and email data lands in a known place.

Rules:

- preserve original source proof while active
- attach source, timestamp, owner, and run id where possible
- do not treat raw dumps as long-term storage by default

### 2. Clean Canonical Data

Useful rows are cleaned into a canonical form.

Rules:

- stable schema
- dedupe key
- owner flow
- source pointer back to raw proof
- current/live flag where needed

### 3. Derived Reports

Reports, summaries, dashboards, and review files are treated as rebuildable unless they are named proof.

Rules:

- short retention window
- keep latest useful outputs
- archive selected proof snapshots only

### 4. Deduplication

Duplicate raw and derived files should be detected before storage grows.

Possible dedupe keys:

- file hash
- source URL plus timestamp bucket
- supplier plus filename plus received date
- Amazon marketplace plus report id
- order id or SKU where relevant
- row count plus schema signature for generated reports

### 5. Retention Rules

Each data family needs a rule:

- keep latest only
- keep last N
- keep last N days
- archive monthly
- keep while investigation active
- purge temp after review
- manual protected

### 6. Automated Custodian

Automation should happen in layers:

1. read-only storage report
2. duplicate report
3. dry-run cleanup manifest
4. reviewed cleanup apply
5. recurring monitor that recommends, not blindly deletes

Automatic deletion should only be allowed for clearly safe temp/debug classes after the rule has been reviewed and proved.

## First Workstream

Recommended first packets:

- `SO21-DATA-FAMILY-INVENTORY`
- `SO21-DUPLICATE-DATA-REPORT`
- `SO21-OUTPUT-RETENTION-RULES`
- `SO21-DATA-CLEANUP-AUTOMATION-DESIGN`

## Protected Boundaries

Do not delete, move, compress, or purge data from:

- live runtime outputs
- current SQL/database files
- active locks
- current proof
- current queue packets
- Google Sheets
- Product DB or local DB facts
- Amazon/security paths

## Expected Outcome

SellerOne should end up with:

- smaller output growth
- clearer storage ownership
- fewer duplicate raw dumps
- clean current datasets
- archived proof where it matters
- automatic reports before cleanup
- safe cleanup automation only after review

## Stop Condition

Stop before any deletion, purge, compression, data movement, database write, Sheet write, runtime change, queue edit, or business action.
