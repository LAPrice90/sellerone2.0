# History Risk Overrides Pass

Ticket: `f-history-risk-overrides-pass-v1`
Parent task: `f-new-product-review-fail-automation-v1`
Date opened: 2026-04-23
Status: planning ready, no code changes in this ticket folder

## Purpose
- Stop clean Pass rows when the same product already carries strong price/history risk evidence.
- Convert contradictory signals into clear review routing.
- Keep the user out of raw CSV review where the issue can be summarized by rule group.

## Plain-English Problem
- The system can say `PASS` while nearby evidence says `Avoid`, `Exit-only`, or `history_recommendation=FAIL`.
- That creates review noise because the product reaches clean Pass even though history says it is risky.

## Current Finding
- Current clean Pass rows after demand routing: `226`
- Rows with at least one direct history-risk conflict: `149`
- This is a large remaining noise source.

## Files In This Folder
- `CODING_PLAN.md` - implementation design for later Codex execution.
- `PHASES.md` - phased execution checklist.
- `EVIDENCE_BASELINE.md` - current evidence and counts from live artifacts.
- `DECISION_BRIEF.md` - plain-English approval brief.
- `RESPONSE.md` - user-facing response record with changes and results.

## Current Scope
- Planning only.
- No code changes.
- No queue writes.
- No Google Sheets changes.
- No scraper runs.
- No A scripts.

