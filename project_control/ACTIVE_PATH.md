# SellerOne Active Path

## Purpose
This file is the live command board for current work.

Use it for:
- current active project ticket
- background gates that still need proof
- queued project tickets ready for a new chat

Do not use this file for:
- long explanations
- full blueprints
- historical notes

Reference documents stay in `project_control/` and `out/process_guides/`.
This file is only for the current path.

## Current Business Goal
Rebuild sales safely without overloading an unproven system.

## Current Position
- Core live backbone exists: A, B, E, H are live.
- H fixes are in place, but H is not yet fully cleared.
- O exists in isolated build form and needs later hardening/adoption.
- Feeder has now started with isolated intake bridge work.
- Old proven price-list scanner logic exists in `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1` and should be reused rather than rebuilt from scratch.
- Shure Cosmetics supplier pull and conversion are already in place, but the first supplier pipeline still needs hardening and closure.

## Background Gate
### H1 - Repricer Reliability Clearance
Status: Observation
Purpose: Let H finish proving stability after fixes already applied.
Clear only when:
- total clean runs reaches 10
- scoped H FAIL = 0
- no unresolved ownership/finalization mismatch
- publish/finalize truth remains clean
Rule:
- H is not the main active phase unless it breaks again.
- If H fails again, H becomes the active ticket immediately.

## Active Ticket
### F1B - Shure Supplier Pipeline Hardening And Universal Layout Lock
Status: Ready
Purpose:
- Turn the first live supplier pipeline into a trustworthy reference implementation.
- Lock the standard supplier-to-universal intake format that future suppliers must follow.

What this ticket must achieve:
- inspect the current Shure Cosmetics pull, canonical conversion, health output, and run state
- explain the held rows clearly and classify them into expected rejects vs converter/data issues
- fix any converter or state-handling gaps needed to make Shure a clean reference supplier
- lock the universal supplier price-list layout that all future converters must output
- prove that future suppliers can plug into the same pattern without editing the manager design
- prove the slice with isolated tests and isolated run evidence

Success gate:
- universal supplier layout is defined clearly
- supplier-specific converter pattern exists
- Shure pipeline state is truthful and no longer ambiguous
- Shure hold reasons are understood and explicit
- converted rows can feed the next Feeder stage truthfully
- isolated tests pass
- isolated proof run succeeds
- final answer clearly states:
- build completed
- live rollout not started
- full Feeder v1 not yet complete

Final status allowed:
- SUCCESS PROVEN
- or BLOCKED with exact next ticket

## Queued Tickets
### F1C - Shared Feeder Manager And Proven Pass-Logic Migration
Status: Queued
Purpose:
- reuse the proven screening logic from the old scanner inside SellerOne's new feeder path

What this ticket must achieve:
- inspect the reusable logic from `Amazon Price List Scanner 2.1`
- migrate the reusable pass/fail checks into SellerOne-friendly shared manager code
- keep Google-specific behavior out of the new implementation
- preserve explicit pass/fail/hold reasons rather than hiding rejected rows

Success gate:
- shared manager exists and reads universal-layout rows
- reused pass-logic outputs exist with explicit statuses/reasons
- non-passing rows are explicit
- isolated tests and isolated run proof pass

### F1C.1 - Second Supplier Plug-In Proof
Status: Queued
Purpose:
- prove that the converter framework works for a second supplier without changing the shared design

What this ticket must achieve:
- add one more supplier converter using the locked universal layout
- prove that the second supplier can flow through the same supplier-to-universal pattern
- keep manager design unchanged

Success gate:
- second supplier converter exists
- second supplier universal output is produced
- no shared-manager redesign is needed for the second supplier
- isolated tests and isolated run proof pass

### F1D - Feeder Candidate Classification, Recommendation, And Approval Queue
Status: Queued
Purpose:
- turn shared-manager output into decision-ready candidates and first approval workflow

What this ticket must achieve:
- assign first-pass candidate statuses with explicit reason codes
- apply initial viability, demand, profit, and test-buy recommendation outputs
- support approve/reject/watch/manual-review style states
- record decisions durably
- keep approved rows ready for later PO handoff work

Success gate:
- approval queue exists
- decision lineage exists
- classification and recommendation outputs exist
- isolated tests and isolated run proof pass

### F1E - Feeder PO-Ready Handoff
Status: Queued
Purpose:
- produce the first truthful handoff from approved feeder candidates into downstream buying flow

What this ticket must achieve:
- produce PO-ready handoff rows for approved candidates only
- define token-safe prerequisites before downstream execution
- keep non-ready rows explicit with reasons

Success gate:
- approved rows can produce PO-ready handoff package
- non-ready rows remain explicit
- isolated tests and isolated run proof pass

### O1 - O Hardening Definition And Proof Gate
Status: Queued
Purpose:
- define what O must survive before it can be trusted as normal operating method

What this ticket must achieve:
- define the likely conflict/error classes after initial build
- define proof standards for reruns, operator events, PO state, receiving state, and handoff state
- define what counts as stable enough for daily adoption

Success gate:
- O hardening checklist exists
- proof gate exists
- failure classes are named explicitly
- daily-adoption standard is clear

## Priority Order
1. Keep watching H in background until cleared or broken.
2. Run F1B as the next active project ticket.
3. Then run F1C.
4. Then run F1C.1.
5. Then run F1D.
6. Then run F1E.
7. Then decide whether O1 or next growth expansion is higher value.

## Operating Rules
- One new chat = one ticket.
- A ticket is only complete when its success gate is proven.
- If a ticket returns blocked, do not improvise. Add the blocker and make the next ticket explicit.
- Do not treat isolated build success as live operational success.
- Do not let background H observation stop foreground progress unless H breaks again.
