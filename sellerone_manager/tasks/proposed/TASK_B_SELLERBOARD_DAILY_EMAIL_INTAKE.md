# TASK B Sellerboard Daily Email Intake

Status: proposed

## Goal
Connect the daily Sellerboard email attachment to the B manager proof lane.

## Manager Expectation
The worker should make the latest Sellerboard OrderList CSV from `admin@drjselect.co.uk` available to the manager bridge, prove the format, and report cleanup candidates without deleting anything.

If Codex cannot see the admin inbox yet, this task is blocked on Luke authorization rather than a normal worker repair.

## Allowed Scope
- Gmail Sellerboard label discovery after Luke authorizes `admin@drjselect.co.uk`
- admin inbox source proof
- Sellerboard attachment intake proof
- local manager intake folder
- Sellerboard bridge source selection
- MOT checks
- tests

## Approved Local Cleanup Rule
Luke approved the narrow cleanup rule:
- keep the latest 2 local Sellerboard OrderList CSVs
- delete only older local Sellerboard OrderList CSV copies in the manager intake folder
- never delete Gmail messages
- never delete non-OrderList files without separate approval
- never delete business outputs

## Forbidden Actions
- no Gmail deletion
- no Gmail account authorization without Luke
- no local file deletion outside the approved Sellerboard OrderList intake cleanup rule
- no B run
- no B restart
- no Google Sheets write
- no local DB alignment
- no price or queue change
- no business data correction
- no ROI/restocking use

## Acceptance Checks
- Codex can see the `admin@drjselect.co.uk` Sellerboard label.
- The first live Sellerboard email attachment is discovered or marked not yet proven.
- The latest OrderList CSV is the selected source for bridge comparison.
- Required columns are checked.
- Cleanup candidates are listed.
- Only older local Sellerboard OrderList copies are allowed to be deleted.
- Gmail messages are never deleted.
- B MOT creates a bounded work item if the attachment is missing or malformed.
- B MOT creates a Luke-decision item if the admin inbox source is not authorized.

## Retest Rule
Retest with the B independent MOT and confirm:
- `b_sellerboard_email_admin_inbox_access` clears
- `b_sellerboard_email_attachment_arrived` clears
- `b_sellerboard_email_attachment_format` clears
- `b_sellerboard_email_attachment_freshness` is ok or only a known timing warning

## Stop Condition
Stop and return to Luke before Gmail account authorization, deleting any Gmail message, deleting local files, running B, restarting B, writing Sheets, aligning local DB data, or changing live ROI/restocking inputs.
