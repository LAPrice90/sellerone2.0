SellerOne 2.0
API-First Data Collection & Decision Foundation
Frozen Execution Plan v1

Status: Active
Supersedes: All prior CSV-stub / mixed-input plans
Scope: Data collection, logging, observability, stability
Out of scope: Pricing strategy, automation decisions, repricing logic

1. Purpose

This document defines the complete, frozen process to transition SellerOne 2.0 from CSV-driven scaffolding to a fully API-backed, logged, and stable data foundation.

The goal is to reach a point where:

All required data is sourced from APIs or internal systems of record

All API calls are observable, throttled, and non-conflicting

Daily history is accumulated reliably

The E cycle can refresh its “opinion” on a fixed cadence

No strategy or pricing automation is attempted yet

This plan must be executed as written.
Improvements and strategy belong to a later phase.

2. Core Architectural Rules (Non-Negotiable)
2.1 Single API Owner Rule

All Amazon SP-API calls must be made by one shared API collection layer.

No E, A, or H script may call SP-API directly.

All calls must pass through:

a shared client

a shared throttle state

a shared lock

unified logging

This prevents:

duplicate calls

throttling collisions

silent data divergence

2.2 Evidence Over Assumption

Every API integration must produce:

raw snapshot output

append-only history

call-level logs

run-level summary logs

If data is missing:

rows must still be written

fields left blank

reason logged

No silent failures.

2.3 E Is Compute-Only

The E cycle:

never calls APIs

reads the latest collected datasets

computes facts, flags, and placeholders only

3. Data Domains (What Is Collected Ongoing)
3.1 Internal Truth (No SP-API)

Source of record.

Orders / sales events (velocity only)

Token system:

current_token_cost_gbp

Inventory math:

available

inbound (when known)

days_of_cover

System run logs and schema checks

3.2 Market Context (SP-API Observational Data)

Captured daily (and later intraday):

Our offer:

our_price

fulfilment channel

Prime eligibility (if available)

Market offers:

buy_box_price

buy_box_channel

lowest_fba_price

lowest_fbm_price

offer counts (FBA / FBM)

Optional context:

BSR + category (only if compliant source)

This data is descriptive, not authoritative.

3.3 Financial Adjustments (SP-API / Reports)

Refunds

Adjustments

Used later to compute expected_refund_cost_per_unit_gbp

4. Output Contracts (Hard)

All collected datasets must be written as:

out/<dataset>_snapshot_YYYY-MM-DD.csv

out/<dataset>_history.csv (append or idempotent upsert)

Each row must include:

timestamp_utc or asof_date

sku

asin

marketplace

source

notes / error field

5. Shared API Control & Observability
5.1 Cross-Process Lock

File: out/locks/spapi.lock

Any API runner must acquire the lock or exit cleanly with status SKIPPED_LOCK_BUSY.

5.2 Persistent Throttle State

File: out/api_rate_state.json

Tracks per endpoint:

last_call_time

recent_request_count

backoff_until

5.3 API Call Log (Append-Only)

File: out/api_call_log.jsonl

One line per request:

run_id

timestamp_utc

script_name

endpoint

marketplace

sku_count

http_status

retries

throttled (true/false)

backoff_seconds

error_code

5.4 API Run Summary

File: out/api_run_log.csv

One row per run:

run_id

started_utc

finished_utc

status (OK/WARN/FAIL)

call counts by endpoint

notes

6. Scheduling (Frozen Decision)
Phase 1–2 (Stability & Proof)

API collection: daily (morning)

E cycle: daily, after API collection

A cycle: unchanged (daily)

Phase 3+ (After Stability Proven)

Market context snapshots: every 4 hours (training set only)

E cycle: every 12 hours

E never runs more frequently than its input data refresh.

7. Phased Execution Plan (Jobs + Pass Checks)
Phase 0 – Archive Old Plan

Goal: Eliminate CSV-stub drift.

Jobs:

Archive prior EHF / CSV-based plans

Create new guide folder for this plan

Update Codex starter to reference only this document

Pass checks:

Only one active plan referenced

No CSV-manual inputs assumed anywhere

Phase 1 – API Observability & Single Owner

Goal: Prove API calls work and do not clash.

Jobs:

Implement shared SP-API client

Implement lock + throttle state

Implement api_call_log and api_run_log

Create run_api_collection.py to own all API pulls

Pass checks:

One run produces:

api_call_log entries

api_run_log row

snapshot files (even if partially blank)

Second run respects throttle and lock

Evidence:

log excerpts

row counts

Phase 2 – Fix Pricing Adapter Root Cause

Goal: Market pricing data populates correctly.

Jobs:

Patch pricing response parser to resolve SKU from:

top-level SellerSKU

fallback Identifier.SellerSKU

Validate with known SKUs

Pass checks:

buy_box_price populates for at least some SKUs

no empty map returned on successful API calls

Evidence:

sample snapshot rows

api_call_log showing successful responses

(Primary root cause identified in context report 

E_cycle_api_transition_report_2…

)

Phase 3 – Complete Minimum Market Context

Goal: H data becomes decision-useful.

Jobs:

Populate:

buy_box_channel

lowest_fba_price

lowest_fbm_price

offer_count_fba

offer_count_fbm

Leave BSR blank if unavailable, log reason

Pass checks:

non-zero fill rates

schema checks pass

fail-soft behavior on API errors

Phase 4 – Inventory & Inbound Consolidation

Goal: Stock gates are real and consistent.

Jobs:

Identify existing inventory/inbound scripts

Consolidate calls into API runner

Produce daily inventory and inbound snapshots + history

Pass checks:

one call per endpoint per run

idempotent daily writes

Phase 5 – Refund / Adjustment Signal Capture

Goal: Data source exists for later refund expectations.

Jobs:

Capture refund/adjustment summaries via API or reports

Write daily snapshot + history

Pass checks:

dataset updates daily

gaps logged explicitly

Phase 6 – History Idempotency Hardening

Goal: Long-term reliability.

Jobs:

Normalize daily key (asof_date)

Ensure reruns overwrite/upsert same-day rows

Pass checks:

two same-day runs do not duplicate history rows

Phase 7 – E Cycle Activation

Goal: E refreshes opinion on stable cadence.

Jobs:

Lock E to read latest snapshot datasets

Enforce schedule (daily → 12h after stability)

Pass checks:

E outputs reference latest asof_date

run logs show consistent cadence

8. Explicit Non-Goals (Phase Guardrails)

No pricing strategy

No repricing automation

No ROI decision math yet

No lane selection logic yet

No F automation yet

These belong to later phases.

9. Definition of “Working Finish”

This phase is complete when:

APIs run daily without conflict

Market, inventory, inbound, and refund data are populated and logged

History accumulates reliably

E runs on schedule and consumes API-backed data only

Evidence exists for every API call and dataset