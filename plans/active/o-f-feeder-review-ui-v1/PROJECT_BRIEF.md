# Project Brief

## Title
- O/F feeder review UI

## Why this exists
- The current feeder review packs are usable, but they are still CSV-first.
- The user wants to review new-product candidates inside the existing operator UI style, not through raw files.
- The review surface needs to feel commercial and practical:
  - clear shortlist
  - simple pass/fail judgement
  - space for written reasoning
  - one button to send reviewed decisions back for analysis

## What this task must achieve
- Design a temporary review page inside the current operator UI style.
- Keep it visually consistent with the restocker.
- Make it simple enough for non-technical batch review.
- Define how reviewed decisions are written back safely.
- Define how those reviewed decisions are turned into analysis outputs.

## What this task must not do
- no implementation code in this ticket
- no Google Sheets changes
- no PO handoff changes
- no direct writes into stale feeder approval files
- no mixing this page into restock decision events

## User outcome
- The user opens one familiar UI.
- The user sees current pass rows and near-miss rows in a commercial review layout.
- The user marks each reviewed row `pass` or `fail`.
- The user writes the reason in a note box.
- The user clicks one button to submit that batch back for analysis.
- The system later compares:
  - what the model liked
  - what the user liked
  - what reasons keep coming up
  - what gaps still exist in the current pass logic

## Design principle
- This page is not for coding-style inspection.
- It is a temporary operator review endpoint for commercial judgement.
- It should feel like:
  - shortlist
  - review queue
  - approval desk
- It should not feel like:
  - raw debug output
  - schema explorer
  - spreadsheet dump
