# O Restock Session v1 Task Packet

Created UTC: 2026-06-02T18:31:49Z
Owner flow: O
Status: local view and health proof built

## Plain-English Goal
Build the first O restock-session lane so Luke can do second-check restocking from the UI instead of moving between the old Purchase List, Product DB, supplier files, supplier websites, and manual notes.

This is a construction step. It does not make O a finished buying loop.

## What The Manual Walkthrough Proved
- O needs one grouped restock review session by supplier.
- Old restock suggestions are useful clues, not current truth.
- Fresh supplier file or API proof must be checked before buying.
- Exact supplier SKU or barcode match matters.
- Similar title is not enough.
- Current price, current supplier cost, fees, VAT, refund drag, inbound cost, and ROI floor must be visible before a clean buy.
- Supplier stock, backorder state, pack size, MOQ, and supplier order value can block a buy.
- Drop, snooze, likely discontinued, needs fresh scan, already ordered, awaiting shipment, and supplier MOQ too low need to be real UI states.
- New product handoffs need dedupe by supplier and ASIN.
- Supplier SKU migration needs barcode-led proof.

## Build Classification
| Area | Class | Meaning |
|---|---|---|
| Restock session source model | not_started | Needs a new local O model joining restock candidates into one review session. |
| Supplier proof joining | not_started | Needs exact SKU/barcode match state, stock state, and backorder/missing states. |
| Expected-profit confidence model | not_verified | Existing profit proof exists, but refund and inbound cost confidence are not complete. |
| Reason-coded UI decisions | not_started | Needs safe draft decisions that do not become live PO actions. |
| Supplier grouped review | not_started | Needs ABGee/Bliss/CLF/Culpitt/DHB grouped session view. |
| Draft supplier order batch view | proof_only | Can show review batches, but must not create real POs. |
| Receiving and send-to-Amazon | not_started | Not part of v1. |

## Allowed Work
- Build local O restock-session view files.
- Add O schema/path contracts for those files.
- Add a UI lane or tab inside the existing O operator UI.
- Add local draft decision reason codes.
- Add tests and an O MOT readiness check.
- Use the manual walkthrough as a fixture/requirements source.
- Write local O proof outputs and history snapshots created by the new builder.

## Forbidden Work
- No Google Sheets write.
- No Product DB fact update from the manual walkthrough.
- No queue edit.
- No price change.
- No local DB alignment.
- No real purchase order.
- No receiving event.
- No send-to-Amazon action.
- No H pause.
- No market proof scan.
- No output deletion.
- No claim that O is complete.

## Proposed Outputs
These outputs are local O proof/view files only:

- `out/systems/O/live/restock_session_review_live.csv`
- `out/systems/O/live/restock_session_supplier_summary_live.csv`
- `out/systems/O/live/restock_session_reason_codes.csv`
- `out/systems/O/live/restock_session_health.csv`
- timestamped history folder under `out/systems/O/history/`

## Required Row States
Every session row should have:

- source class: `native_o`, `legacy_bridge`, `feeder_review_handoff`, or `manual_walkthrough_fixture`
- supplier proof state
- market price proof state
- fee proof state
- refund proof state
- inbound cost proof state
- pack/MOQ proof state
- demand confidence
- action safety state
- operator decision state
- blocked reason when not orderable

## Required Operator Decisions
The UI should support draft local decisions for:

- order quantity draft
- snooze
- drop
- likely discontinued
- needs fresh supplier scan
- backorder wait
- already ordered or paid
- awaiting supplier shipment
- supplier MOQ too low
- profit too low
- proof missing

These decisions are draft O events only until a later approved step connects them to PO creation.

## Acceptance Proof
- Targeted O session tests pass.
- Existing O UI tests still pass.
- O MOT passes without claiming O is complete.
- O user-working readiness stays ok.
- No buy-ready row exists unless all required proof is present.
- No PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, H pause, or market scan action is performed.

## Worker Stop Conditions
Stop and return to the manager if:

- the UI would need a real PO action
- the UI would need a Sheet write
- the build needs Product DB fact changes
- a row needs live market proof from H-owned files
- a supplier order must be placed
- an Amazon handoff would be created
- root cause of a profit or supplier-state mismatch is unclear

## First Implementation Step
Build the local restock-session view and health proof before adding deeper decision capture. The first proof should answer:

- Can O show all current restock work in one supplier-grouped session?
- Can O label every row's source and missing proof?
- Can O stop unsafe rows from looking buy-ready?

Only after that proof passes should the UI decision buttons be wired.

## Build Result - 2026-06-02

The first implementation step passed.

- O built 608 local restock-session rows.
- O grouped those rows into 426 supplier summary rows.
- O labelled 72 rows as `legacy_bridge` and 536 as `native_o`.
- O marked all 608 rows blocked from clean-buy wording, which is correct because refund/inbound and other proof gaps remain visible.
- O wrote local-only reason codes with `creates_live_action=0`.
- O wrote session health proof with all checks `ok`.
- O MOT reports `o_restock_session_readiness=ok`.

Next allowed build:

- Add local draft decision capture for the restock-session rows.
- Keep PO, receiving, send-to-Amazon, Sheets, prices, queues, local DB alignment, H pause, and market scans blocked.
