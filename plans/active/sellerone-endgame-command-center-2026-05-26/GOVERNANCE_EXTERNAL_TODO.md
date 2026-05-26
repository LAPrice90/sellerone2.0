# Governance And External Todo

Created: 2026-05-26
Owner area: shared governance, storage, scheduler, external integrations

## Source Plans To Read First

- `project_control/TASK_QUEUE.md`
- `project_control/DUE_CHECK_REGISTER.csv`
- `project_control/STORAGE*` files and `project_control/storage_*` folders
- `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md`
- `project_control/OUTPUT_SCHEMA_CHECKS.md`
- `project_control/SCRIPT_INVENTORY.csv`

## Current Evidence

- `out/housekeeping/storage_health.latest.csv` has `unclassified_scan_items` FAIL with value 281.
- `project_control/DUE_CHECK_REGISTER.csv` contains overdue checks for H, F, A, and O.
- Controlled restart recovery remains an open task in `project_control/TASK_QUEUE.md`.
- External integration inventory and no-write smoke test plan remain open tasks.

## Plain-English Finish Line

Governance is endgame-ready when the system tells the truth, stores outputs in known places, and does not depend on memory from old chats.

## Phase 0 - Clean Due-Check Backlog

- [ ] Review overdue due checks and classify each as `fix now`, `monitor in MOT only`, `stale evidence only`, or `needs user decision`.
- [ ] Do not use chat as the only follow-up memory.
- [ ] Ensure every future wait condition goes into `DUE_CHECK_REGISTER.csv` or an active `CODING_PLAN.md`.

Success condition:
- No overdue due check is ambiguous.

## Phase 1 - Storage Governance

- [ ] Investigate `unclassified_scan_items` value 281.
- [ ] Classify new output families or add cleanup rules where appropriate.
- [ ] Do not delete live/current data.
- [ ] Ensure any cleanup action has rollback and proof.

Success condition:
- Storage health no longer has unclassified active output families, or every remaining family is explicitly allowed.

## Phase 2 - Scheduler And Restart Ownership

- [ ] Review controlled restart failure from 2026-05-06.
- [ ] Confirm scheduler tasks still expected: AMZ Orders, AMZ H Cycle, AMZ Controlled Restart, AMZ Price List Manager.
- [ ] Export or document scheduler XML where still active.
- [ ] Fix self-blocking restart ownership only after exact owner state is known.

Success condition:
- Restart either reboots safely inside the window or records one clear safe skip reason.

## Phase 3 - External Integration Inventory

- [ ] Create read-only inventory for Amazon SP-API, Google Sheets, BBP/web scrape, Gmail, and scheduler tasks.
- [ ] Create no-write smoke test plan.
- [ ] Do not execute write-capable Sheet, listing, or Product DB calls without explicit approval.

Success condition:
- Every external integration has a read-only check and a clear write boundary.

## Stop Conditions

Stop before changing anything if:

- cleanup might delete live/current data
- external writes would occur
- scheduler ownership is ambiguous
- due-check status would be cleared without proof

