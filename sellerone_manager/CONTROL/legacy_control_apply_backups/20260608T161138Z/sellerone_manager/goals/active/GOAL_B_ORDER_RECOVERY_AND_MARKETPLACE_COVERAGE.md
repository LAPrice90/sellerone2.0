# GOAL B Order Recovery And Marketplace Coverage

Status: active

## Goal
Make B prove the full order picture across all Amazon marketplaces from November 2025 onward, while keeping recovered orders quarantined until they are safe to use.

## Success Criteria
- All Amazon marketplaces have future cursor proof.
- Backdate recovery checks from 2025-11-01.
- Missing Sellerboard shipped orders are either API-proved in quarantine or clearly labelled `not yet proven`.
- Recovered orders are deduped before any merge.
- Sellerboard bridge values are not treated as final API truth.
- ROI and restocking do not use recovered or bridge values without Luke approval.

## Manager Boundary
This goal is B-only unless another cycle directly blocks B proof.

Codex may create manager proof, worker task packets, read-only reports, and tests.

Codex must stop before running B, restarting B, editing markers, writing Sheets, aligning local DB data, deleting outputs, changing prices or queues, merging recovered orders, or feeding bridge values into ROI.

## Proof
The independent B MOT is the proof owner. Old B checklist FAIL/WARN rows are clues only.
