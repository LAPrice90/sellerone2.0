# O Active Restock Files Review - Reviewer Note

reviewed_uk: 2026-06-09
reviewer_role: O restocking evidence Reviewer
review_target: `CONTROL/O_ACTIVE_RESTOCK_FILES_REVIEW_20260609.md`
job_ref: `O-ACTIVE-RESTOCK-FILES`

## Review Outcome

Pass.

The review note is evidence-backed and safe for Rep planning use as a planning-only control note.

## Exact Reason

- The note matches the current approved packet boundary in `tasks/approved/MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES.md`: proof-file mapping only, no worker run, no purchase action, no Sheet write, no queue edit, no DB alignment, and no runtime widening.
- The note matches the latest MOT evidence in `../out/systems/M/mot/mot_latest.csv` and `../out/systems/M/mot/mot_latest.md`: `o_active_restock_proof_files` is still `fail` at `2026-06-09T15:00:33Z` with `missing=0;short=0;unreadable=0;stale_warn=0;stale_fail=2`.
- The two stale-fail files named in MOT are correctly identified as `legacy_purchase_list_bridge.csv` and `legacy_purchase_list_bridge_health.csv`.
- Direct file checks support the note: the stale legacy pair was last written `2026-05-22 09:43:38 UTC`, while the other packet-named O proof files were written on `2026-06-04` to `2026-06-05`.
- Direct row-count checks support the planning summary: the main current O files still show 608-row planning outputs, while the legacy bridge pair shows 72 and 10 rows.

## Safety Check

This review does not approve:

- orders
- purchase commitments
- receiving stock
- send-to-Amazon actions
- supplier commitments
- price changes
- Google Sheets writes
- queue edits
- Product DB or local DB alignment
- supplier file rewrite, move, import, fetch, or deletion
- O runtime or live worker action
- Amazon or security action

The reviewed note correctly stays on the planning/evidence side only.

## Blocker And Next Lane

The blocker is appropriate.

It is safe to let Rep and Operations use the note for planning explanation, but it is not safe to describe the O proof-file packet as cleared while the two legacy bridge files remain stale in the active proof map.

The safer next Operations lane is:

- proceed with bounded stale-proof-file fix/retest planning

Reason:

- it is already the approved packet for this exact failure
- it directly targets the stale pair named by MOT
- it does not require Luke approval on its current boundary
- it keeps the work in planning/proof territory instead of drifting into ordering or runtime actions

## Reviewer Classification

- review status: pass
- planning status of the underlying O evidence: blocked as a fully current proof set
- Rep-safe use now: planning summary and blocker explanation only
