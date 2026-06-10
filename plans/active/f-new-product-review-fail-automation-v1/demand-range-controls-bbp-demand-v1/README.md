# Demand Range Controls BBP Demand

Ticket: `f-demand-range-controls-bbp-demand-v1`
Parent task: `f-new-product-review-fail-automation-v1`
Date opened: 2026-04-23
Status: planning ready, no code changes in this ticket folder

## Purpose
- Stop BBP demand from creating clean Pass rows when Amazon's visible sold signal does not support that volume.
- Treat Amazon as the demand range source.
- Treat BBP as the estimate source only inside the Amazon-supported range.
- Use UK variant review evidence to reduce trust when BBP demand may be coming from parent or non-UK variation data.

## Plain-English Rule
- Amazon blank sold signal means the product is in the `0-49` visible demand range.
- Amazon `50+` means the product has at least low visible demand.
- BBP can refine demand when it agrees with the Amazon range.
- BBP should be capped, blocked, or reviewed when it greatly exceeds the Amazon range.
- Weak UK review evidence strengthens the case that BBP may be using parent or non-UK variation demand.

## Files In This Folder
- `CODING_PLAN.md` - implementation design for later Codex execution.
- `PHASES.md` - phased execution checklist.
- `EVIDENCE_BASELINE.md` - current evidence and counts from live artifacts.
- `RESPONSE.md` - user-facing response record with detailed changes and results.

## Current Scope
- Planning only.
- No code changes.
- No queue writes.
- No Google Sheets changes.
- No full scraper rescan.

