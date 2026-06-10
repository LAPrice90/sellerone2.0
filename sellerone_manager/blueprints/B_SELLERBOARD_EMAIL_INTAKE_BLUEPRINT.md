# B Sellerboard Email Intake Blueprint

Created UTC: 2026-05-27T12:30:00Z

## What This Is
B needs a daily outside order check from Sellerboard.

The Sellerboard email label in `admin@drjselect.co.uk` is the expected source for the daily OrderList attachment. The manager must prove Codex can see that admin inbox before treating any daily attachment as live email proof.

## Current Truth
The Gmail connector was checked read-only, but it did not prove access to `admin@drjselect.co.uk` or the `Sellerboard` label.

That means live email arrival is not yet proven. A local CSV can help test the parser, but it is not enough to prove the daily email intake.

## Manager Expectation
The manager should prove:
- Codex can see the `admin@drjselect.co.uk` inbox
- Codex can see the `Sellerboard` label and latest message
- a Sellerboard daily email attachment arrived
- the attachment is a Sellerboard OrderList CSV
- the attachment has the expected columns
- the latest attachment is fresh enough for the daily B comparison
- only a small number of useful attachments are retained locally
- cleanup candidates are listed
- deletion does not happen without Luke approval

## MOT Proof Check
The B MOT should check:
- admin inbox source access proof
- Sellerboard attachment arrived in the manager intake folder
- Sellerboard attachment format matches the bridge parser
- Sellerboard attachment freshness
- cleanup candidate count and bytes

The MOT may create bounded worker tasks for parser and local intake issues.

If admin inbox access is not proved, the MOT must mark that as a Luke decision, not as a normal worker repair.

The MOT must not delete Gmail messages, delete local files, run B, write Sheets, change local DB facts, or repair business data.

## Cleanup Rule
Approved safe rule:
- keep the latest 2 Sellerboard OrderList CSV files locally
- delete only older local Sellerboard OrderList CSV copies beyond those latest 2 files
- never delete Gmail messages
- never delete non-OrderList files unless Luke separately approves
- never delete business outputs or files outside the Sellerboard intake folder

Luke approved this suggested rule on 2026-05-27 with: "whatever you suggest".

## Bounded Worker Task
Allowed:
- inspect the Gmail Sellerboard label after Luke has connected or re-authorized `admin@drjselect.co.uk`
- save the daily OrderList CSV into the intake folder
- write an intake manifest, attachment summary, and cleanup candidate list
- update the Sellerboard bridge to use the latest intake attachment
- add MOT checks and tests

Forbidden:
- no Gmail account authorization without Luke
- no Gmail deletion until Luke approves
- no local output deletion until Luke approves
- no B run or restart
- no Google Sheets write
- no local DB alignment
- no price or queue change
- no business data correction

## Retest Rule
The email intake is proved only when:
- Codex can see the `admin@drjselect.co.uk` Sellerboard label
- the first live Sellerboard email is visible from that inbox
- the attachment is saved to the intake area
- the B MOT sees a fresh attachment
- the bridge parser can read it
- older local OrderList cleanup is either not needed or applied under the approved policy

## Plain English Summary
This is the postman check.

The manager checks that the Sellerboard daily parcel arrived, opens only the useful CSV, checks the shape, and lists old parcels for cleanup. Throwing anything away needs its own approval.
