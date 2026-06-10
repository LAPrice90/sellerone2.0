# Runbook

## Purpose
- explain how the B/E/F sales feedback loop should work once this plan is implemented

## Intended flow
1. B updates operational order truth.
2. E builds finalized and provisional daily sales truth.
3. foundation builder checks freshness and bridge coverage.
4. automatic actuals builder fills F learning actuals.
5. learning pack rebuilds.
6. example pack rebuilds.
7. user reviews only example logic.

## Operator role
- review decision examples
- review unresolved or ambiguous bridge cases only when surfaced
- do not type actual sales figures into normal workflow

## Health checks to respect
- if `order_master -> order_ledger_fx` lag breaches threshold:
  - block feedback sign-off
- if bridge unresolved share breaches threshold:
  - block closed-loop claim
- if provisional rows are being treated as finalized:
  - fail the run

## Recovery rule
- if actuals automation breaks, fall back to:
  - keeping the existing learning outputs unchanged
  - surfacing the health failure
  - using the manual template only as an explicit temporary fallback

## Not allowed
- no silent override of stale truth
- no manual copying between systems as the normal operating model
- no user dependency for routine actuals capture
