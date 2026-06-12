# A2-T2AC-TW3L Floor Not Updated Active Risk Result - 2026-06-12

Job ref: `A2-T2AC-TW3L-FLOOR-NOT-UPDATED-ACTIVE-RISK`

## Plain-English Result

This is a real system failure.

The system protected itself from making a bad automatic write, but it failed Luke as a manager system because it did not keep the unresolved business risk at the top of the list.

## What Is Happening

`A2-T2AC-TW3L` has newer stock receipt tokens at cost `4.89`.

H is still selecting an older fallback token at cost `4.51`.

Because H can see that a newer receipt token exists, it marks the selected fallback token as a conflict. That part is correct.

Then H refuses to produce a clean floor and the repricer does not write. That is also safer than writing a bad floor.

The failure is what happens next: the Manager/MOT layer did not turn that blocked state into a loud active pricing-risk item.

## Evidence Checked

- Latest H trace still selects fallback token `ADJ-A2-T2AC-TW3L-FBA15LKBY55D-0141`.
- Latest H trace still references newer receipt token `SR-20260605-ROW0092-0001`.
- Latest H trace still shows receipt cost `4.89`.
- Latest H trace still shows selected fallback cost `4.51`.
- Latest H floor table leaves the floor blank for this SKU and shows `token_selection_conflict`.
- Latest H lifecycle row finishes as `FLOOR_INPUT_MISSING_HOLD`.
- Latest runtime snapshot shows `READ_ONLY_NO_WRITE`.
- Repricing live execution log has no write rows for this SKU.
- MOT contains a warning for `h_blocked_skus=A2-T2AC-TW3L`, but the board did not treat it as urgent active work.

## Root Cause In Business Terms

The picker is still taking an old untrusted box from the shelf, even though the new labelled delivery is sitting there.

The cashier refuses to price the product from the wrong box, which is good.

But the shop manager then files that under "later" instead of "sort this now before we sell wrong".

## Next Safe Repair

Create a Builder packet to fix the H token-selection path and MOT escalation:

`H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`

The repair should:

- make H prefer valid fresh receipt tokens over older fallback tokens where the newer receipt token is available for the same SKU
- keep fallback tokens blocked or quarantined when they conflict with newer receipt proof
- add a specific MOT/business alert when an SKU has `token_selection_conflict` and no clean floor
- keep repricer writes blocked until the clean floor is proved

## Protected Boundary

This result does not approve a price change, token edit, Google Sheet write, queue edit, database edit, Task Scheduler change, Amazon action, runtime restart, or output deletion.

