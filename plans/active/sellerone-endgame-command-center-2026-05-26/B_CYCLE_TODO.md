# B Cycle Todo

Created: 2026-05-26
Owner flow: B
Business purpose: orders, tokens, COGS, sales truth, and daytime sales loop.

## Source Plans To Read First

- `project_control/EXPECTATIONS/B_cycle_expectations.md`
- `project_control/TASK_QUEUE.md`
- B active plans under `plans/active/`

## Current Evidence

- `out/cycle_alerts/summary.csv` shows B has 0 FAIL and 0 WARN.
- Earlier token shortage and placeholder COGS issues were completed on 2026-05-06.
- B proof must remain owner-safe if a manual proof is ever needed.

## Plain-English Finish Line

B is endgame-ready when order, token, and COGS truth can support restock and new-product receiving without manual repair.

## Phase 0 - Keep B Stable

- [ ] Do not manually overlap B scripts while B owner is active.
- [ ] If B proof is required, use maintenance handoff and `B_RUN_ONCE=1` at a safe boundary.
- [ ] Confirm token shortage log remains one line per SKU per run.

Success condition:
- B remains 0 FAIL / 0 WARN and supports downstream cost truth.

## Phase 1 - Prepare For O Receiving And New Products

- [ ] Confirm B token system expectations for pending PO lots and received unit tokens.
- [ ] Confirm new-product feeder handoff will not create available tokens before receipt.
- [ ] Confirm COGS and returns traceability remain clean after receiving.

Success condition:
- O and F can add bought stock without breaking token traceability.

## Stop Conditions

Stop before changing anything if:

- `out/B_cycle.lock` is active and maintenance handoff is not ready
- a manual proof would overlap the B loop
- local DB or Sheets alignment is requested without approval

