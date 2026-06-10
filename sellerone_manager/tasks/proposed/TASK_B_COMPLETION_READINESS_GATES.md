# TASK B Completion Readiness Gates

Status: proposed

## Goal
Add B completion gates so the manager can separate maintenance readiness from full order truth completion.

## Manager Expectation
The worker should keep B completion proof inside the independent MOT. It must not rely on old checklist FAIL/WARN counts as the main truth.

## Allowed Scope
- B independent MOT readiness rows
- B manager expectation text
- B completion blueprint
- manager tests
- approved task packet refresh

## Forbidden Actions
- no Gmail authorization
- no Gmail deletion
- no B run
- no B restart
- no lock or maintenance marker edits
- no Google Sheets write
- no local DB alignment
- no output deletion
- no recovered-order live merge
- no ROI/restocking use
- no price or queue change

## Acceptance Checks
- B MOT has `b_management_ready_for_maintenance`.
- B MOT has `b_order_truth_completion`.
- Admin inbox access missing keeps a Luke decision visible.
- Missing order or marketplace coverage gaps keep B order truth incomplete.
- Clean independent B proof clears both completion gates.
- Old B checklist FAIL/WARN remains only a clue.
- 2026-05-30 check: `b_management_ready_for_maintenance` must remain blocked while either `b_future_marketplace_order_cursors` or `b_pnl_daily` is `fail`.
- 2026-05-30 check: `b_order_truth_completion` must remain blocked while `b_future_marketplace_order_cursors` is `fail`; Sellerboard bridge warnings remain visible but must not feed live ROI.

## Retest Rule
Retest with the B independent MOT and manager tests. A completion gate is proved only when the relevant B MOT row clears.

## Stop Condition
Stop and return to Luke before any protected action or scope widening beyond B manager proof.

## 2026-05-30 Worker Classification

The readiness and order-truth rows are derived gates. They are not separate data problems to patch. Current blockers are:

- stale per-marketplace cursor proof
- P and L blocked by the B health gate after a true live token shortage

The correct repair path is to clear those upstream proof blockers through approved B proof or receipt/correction evidence, then retest the same B MOT rows.
