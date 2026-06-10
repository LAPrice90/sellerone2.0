# B Backdate Recovery And Future Order Coverage Blueprint

Created UTC: 2026-05-27T12:00:00Z

## What This Is
B must prove SellerOne has the full order picture across all Amazon marketplaces, not just the busiest marketplace.

This blueprint covers:
- backdate recovery from 2025-11-01
- all Amazon marketplaces
- quarantine proof before any live data use
- per-marketplace daily cursor proof
- Sellerboard outside comparison until direct API refund, fee, and shipping access is complete

## Current Trigger
Sellerboard showed a shipped Amazon.ae order that local SellerOne proof did not contain:
- order: `171-1388771-2409132`
- sales channel: `Amazon.ae`
- SKU confirmed by Luke: `GH-XAAE-HRU7`
- ASIN: `B072K2PG11`
- purchase date: 2026-05-23

Luke confirmed the order exists in Seller Central.

This is not acceptable as a one-order manual repair. The manager must prove whether the same issue exists across the whole B order system and other marketplaces.

## Manager Expectation
B must prove:
- every participating Amazon marketplace was checked
- each marketplace has its own future cursor proof
- the shared UK/global marker is not the only truth
- missing orders are recovered into quarantine first
- recovered orders are deduped before any merge
- Sellerboard-only values are labelled as estimates
- ROI and restocking do not use recovered or bridge values without approval

## MOT Proof Checks
The independent B MOT must check:
- backdate recovery quarantine state
- unrecovered Sellerboard missing orders
- per-marketplace cursor missing or stale count
- duplicate risk in quarantine
- any live-merge-ready recovered order without Luke approval
- quarantine proof labels and schema

Old B checklist FAIL/WARN rows remain clues only.

## Bounded Worker Tasks
Safe tasks Codex can prepare:
- build a read-only all-market backdate scanner
- build per-marketplace cursor proof
- build recovery quarantine proof
- build duplicate and live-merge guards
- update Sellerboard comparison and MOT checks
- add tests that prove failures create bounded B work items

## Forbidden Actions
Stop before:
- running or restarting B
- backfilling live order outputs
- editing shared or per-marketplace markers
- clearing locks or maintenance markers
- writing Google Sheets
- aligning local DB data
- deleting outputs
- correcting token, refund, fee, shipping, order, or ROI data
- feeding recovered or Sellerboard bridge values into live ROI or restocking
- widening beyond B order recovery and future coverage

## Retest Rule
A code edit does not prove this.

The task is proved only when:
- the B MOT runs read-only
- missing orders either become API-proved in quarantine or remain visible as not yet proven
- every Amazon marketplace has fresh per-marketplace cursor proof
- duplicate and live-merge guards are clean
- the same MOT rows clear after the approved worker task

## Plain English Summary
Do not patch one missing order and move on.

First build the system that checks all marketplaces, backdates missing order proof into quarantine, and prevents future quiet-marketplace gaps.
