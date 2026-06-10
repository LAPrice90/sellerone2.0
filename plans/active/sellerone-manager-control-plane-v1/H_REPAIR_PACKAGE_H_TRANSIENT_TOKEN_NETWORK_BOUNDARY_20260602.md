# H Repair Package - Transient Token Network Boundary - 2026-06-02

## Approved Check
`h_transient_token_network_boundary`

## Root Cause Summary
- The active H MOT failures are grouped into one real H run failure, not four unrelated proof defects.
- Latest completed failed run: `H_20260602T084547Z`.
- H failed during `snapshot_refresh/own_offer_lookup` before publish started.
- The direct failure was an external token/network lookup problem: Amazon token host name resolution failed while the own-offer helper was trying to reach `api.amazon.com`.
- The later status-only publish proof also hit a Google OAuth token host name resolution failure.
- The finalizer and terminal marker told the truth for that run: H failed and was not safe to mark ready.
- A newer scheduler-owned H run `20260602T085154Z` started by itself after the failure. Codex must only watch that run through proof files.

## Current Failed Checks Grouped Into One Issue
- `h_latest_manifest_state`
- `h_terminal_publish_truth`
- `h_boundary_finalizer_truth`
- `h_manager_readiness`

These are one issue: H has no newer clean terminal proof yet after a real token/network-boundary failure.

## Allowed Files For A Future Repair Batch
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/tools/H_own_offer_lookup.py`
- `scripts/tools/H_item_offers_lookup.py`
- `scripts/api/get_listing_item_price.py`
- `scripts/api/get_pricing.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`, only for status-only error classification and proof wording
- focused H lifecycle, token-boundary, and manager MOT tests under `tests/`
- this repair package and `CODING_PLAN.md`

## Forbidden Files And Actions
- Do not run H from Codex.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align local DB facts.
- Do not delete outputs.
- Do not restart workers.
- Do not hand-edit manifests, terminal markers, publish markers, MOT rows, health rows, or H output files to make proof look clean.
- Do not widen into A, B, E, F, or O.

## Proof Path For A Future Repair
- First prove the token/network failure path in focused tests.
- A safe code repair may improve retry, classification, or manager-visible proof for transient token/network failure.
- A safe code repair must not convert a real failed run into success.
- Compile every touched H/API/proof file.
- Run focused H tests for the changed code.
- Run manager H MOT tests.
- Retest with the read-only H MOT command.
- Real H recovery is proved only when a natural or separately approved H-owned run leaves:
  - latest manifest final state `completed`
  - terminal state `finalized`
  - publish status `ok` or a clearly safe parked state
  - independent H MOT clears `h_latest_manifest_state`, `h_terminal_publish_truth`, and `h_boundary_finalizer_truth`

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow H

## Rollback Path
- Use git diff for code rollback.
- Do not alter H output files to satisfy proof.
- If future code changes affect token/network handling, revert only the touched token-boundary or proof-classification code and rerun focused tests plus H MOT.

## Stop Condition
- Stop if the repair would require a live H run, scheduler pause/resume, publish, price change, queue edit, Sheet write, DB alignment, output deletion, worker restart, or scope widening.
- Stop if evidence shows the next failure is not token/network-boundary related.
- If the newer natural H run finalizes cleanly, record that as proof and mark the MOT packets proved after read-only H MOT clears.
