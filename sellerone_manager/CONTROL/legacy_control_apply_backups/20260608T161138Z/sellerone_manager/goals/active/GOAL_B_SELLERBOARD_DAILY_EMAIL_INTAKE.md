# GOAL B Sellerboard Daily Email Intake

Status: active

## Goal
Make the Sellerboard daily email attachment part of B manager proof so missed orders are caught by an outside source.

## Success Criteria
- The Sellerboard email attachment is checked daily.
- Codex can see the `admin@drjselect.co.uk` Sellerboard label before the intake is treated as live-email proof.
- The latest attachment is saved into the manager intake area.
- The attachment format is verified before the bridge uses it.
- Storage cleanup candidates are reported.
- Deletion is guarded and requires Luke approval.
- B MOT reports the intake state.

## Manager Boundary
This is B-only and manager-proof only.

Codex may create reports, MOT checks, task packets, and parser support.

Codex must stop before Gmail account authorization, deleting email, deleting local files, running B, restarting B, writing Sheets, aligning local DB data, changing prices or queues, or feeding bridge data into live ROI.
