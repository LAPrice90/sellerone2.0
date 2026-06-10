# Weak UK Variant Review Signal

Ticket: `f-weak-uk-variant-review-signal-v1`
Parent task: `f-new-product-review-fail-automation-v1`
Date opened: 2026-04-23
Status: planning ready

## Purpose
- Stop clean Pass rows when parent/global/variant review volume looks strong but UK-specific evidence is weak.
- Use stored UK review evidence first.
- Only request new data if the current stored evidence is not enough.

## Plain-English Problem
- A product can have many parent or variant reviews, but very few UK reviews.
- For a UK-selling decision, weak UK review evidence should reduce confidence or block clean Pass.
- This was one of the original reasons the user failed `B0C8C3JF9X`.

## Current Finding
- Current clean Pass rows after demand and history routing: `79`
- Rows with `historical_uk_reviews < 6`: `32`
- Rows with `historical_uk_reviews < 3`: `22`
- This issue is still material after the first two routing fixes.

## Files In This Folder
- `CODING_PLAN.md` - implementation design for Codex execution.
- `PHASES.md` - phased execution checklist.
- `EVIDENCE_BASELINE.md` - current evidence and counts from live artifacts.
- `DECISION_BRIEF.md` - plain-English approval brief.
- `RESPONSE.md` - user-facing response record.

## Current Scope
- Planned implementation should continue end to end unless missing data blocks it.
- No Google Sheets changes.
- No local DB alignment changes.
- No scraper run unless explicitly approved.
- No A scripts.

