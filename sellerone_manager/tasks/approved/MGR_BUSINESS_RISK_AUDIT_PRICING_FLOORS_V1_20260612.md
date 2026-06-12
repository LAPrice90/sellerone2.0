# Business Risk Audit - Pricing Floors V1

Job ref: `BUSINESS-RISK-AUDIT-PRICING-FLOORS-V1`

## Purpose

Find other SKUs that may have the same class of risk as `A2-T2AC-TW3L`.

## Business Reason

Luke should not have to stumble across pricing failures manually. The system must actively find SKUs where fresh stock cost, floor calculation, and repricer action do not line up.

## Scope

Read-only audit only.

Check current local evidence for:

- fresh receipt tokens available
- H selecting fallback tokens instead
- `token_selection_conflict`
- blank or missing floor
- no repricer write after cost change
- observed/live price below safe floor or break-even where local evidence exists
- MOT warnings that did not become active board work

## Required Output

Write:

`CONTROL/BUSINESS_RISK_AUDIT_PRICING_FLOORS_V1_RESULT_20260612.md`

The result must be plain English and include:

- red risk SKUs
- amber risk SKUs
- clear SKUs
- what each risk means for Luke
- next repair packet needed

## Forbidden Actions

Do not:

- change prices
- edit token ledgers
- write Google Sheets
- edit queues
- edit Product DB or local DB facts
- restart runtime
- modify Task Scheduler
- call Amazon
- delete outputs

