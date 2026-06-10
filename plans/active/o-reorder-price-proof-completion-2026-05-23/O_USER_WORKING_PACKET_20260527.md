# O User-Working Readiness Packet - 2026-05-27

## Goal

Prove O is safe to work on with Luke as a user-facing mid-build system.

This does not mean O is live. It means O can be used for viewing, walkthroughs, and decision-shaping while real buying actions stay blocked.

## Ready Means

- O MOT has no real safety fails.
- `o_user_working_readiness` is `ok`.
- O remains labelled mid-build, not complete.
- Reorder rows can be reviewed without becoming purchase orders.
- Product DB browse/edit UI can be walked through as UAT.
- Bridge, proof-only, not-started, and not-verified stages stay visibly labelled.
- H market proof remains automation-tracked and does not block user review work.

## Allowed Work

- Run O MOT and read O proof files.
- Run targeted O UI and O manager tests.
- Inspect the Reorder page, Product DB browse tab, and Product DB Edit tab.
- Draft notes for what Luke should look at in the UI.
- Make small UI wording or guardrail fixes if they keep O clearly mid-build and do not change business data.

## Forbidden Work

- No Google Sheets writes.
- No price changes.
- No queue edits.
- No local DB alignment.
- No purchase orders.
- No receiving events.
- No send-to-Amazon handoff.
- No output deletion.
- No H pause/resume.
- No market proof scan.
- No O010/O100 live decision-to-PO run.
- No marking O complete.

## Proof To Collect

- `python -m sellerone_manager.app --hourly-mot --mot-flow O`
- `python -m pytest tests/manager/test_hourly_mot.py tests/test_o_ui_operator_view.py tests/test_o410_product_database_ui.py tests/test_o420_product_database_edit_ui.py -q`
- Confirm `out/systems/M/hourly_mot_O.csv` has `o_user_working_readiness=ok`.
- Confirm any remaining O warnings are non-user blockers, not safety failures.

## Stop Conditions

- Any O MOT `fail`.
- Any row becomes action-ready without cost, market, net-fee, and Max pay proof.
- Any UI path can create PO, receiving, Amazon handoff, price, queue, Sheet, or DB changes without protected approval.
- Any wording claims O is complete.

## Next Safe Build Step

Prepare the user walkthrough of the existing O UI:

- Reorder page: review evidence and blocked rows.
- Product DB browse: inspect product truth and freshness.
- Product DB edit: confirm edit-event capture only, not direct truth writes.

Success is Luke being able to use O as a construction walkthrough without any live buying path being opened.
