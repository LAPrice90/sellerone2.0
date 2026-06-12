# Business Risk Audit - Pricing Floors V1 Result - 2026-06-12

Job ref: `BUSINESS-RISK-AUDIT-PRICING-FLOORS-V1`

## Plain-English Verdict

Luke was right to worry that `A2-T2AC-TW3L` might not be the only issue.

This audit found:

- 4 red pricing/floor risk SKUs
- 18 amber pricing/floor watch SKUs

Red does not automatically mean Amazon has already sold below the true floor. It means the local system cannot currently prove the floor path is clean enough to trust.

## Red Risk SKUs

| SKU | What is wrong | Business meaning |
|---|---|---|
| `A2-T2AC-TW3L` | Fresh receipt tokens exist at `4.89`, but H still selects fallback cost `4.51`; floor is blocked; runtime shows `READ_ONLY_NO_WRITE`. | Active price-risk case. This is the one Luke spotted manually. |
| `CN-NR50-TSFE` | Fresh receipt tokens exist at `8.61`, but H still selects fallback cost `8.58`; candidate price is missing; runtime shows `READ_ONLY_NO_WRITE`. | Cost is close, but the clean floor path is still not proved. |
| `LV-425G-BY4X` | Fresh receipt tokens exist at `16.38`, but H still carries token conflict and runtime shows `READ_ONLY_NO_WRITE`. | Fresh token exists, but the system still cannot prove clean floor output. |
| `6V-EEC1-2S9Z` | Token-selection conflict is present; floor conflict remains visible. | Needs review. It may not be the same money-risk shape as A2, but it is still not a clean floor path. |

## Amber Watch SKUs

These are not proven money-loss cases, but they should not be ignored.

Most amber rows are missing candidate-price input or are sitting in no-write states.

Amber SKUs:

- `0G-JB6S-PN34`
- `2T-07RT-8IMX`
- `49-4UKW-G81R`
- `4F-HT42-FD26`
- `5Z-6Z0P-9TQQ`
- `6Q-9G2A-IKVV`
- `7L-OT45-7LYB`
- `D0-C7C0-H6LN`
- `GH-XAAE-HRU7`
- `GJ-2OZK-0GCA`
- `H6-E7MP-EBPD`
- `HL-03ZR-QPHH`
- `JE-D4LO-O2JD`
- `LR-7GM6-1RCH`
- `OV-LVEL-DQL6`
- `SZ-UL4K-SE7W`
- `XH-0LAE-FQO5`
- `YO-EKK2-FRCC`

## MOT Failure Found

MOT did contain warning evidence.

The problem is that the warning did not become a strong business alert.

Examples found:

- B fallback reconciliation warned about `h_blocked_skus=A2-T2AC-TW3L`.
- H floor-source check warned about risky or unknown floor-cost source rows.
- The board still parked Token Pricing Issue as if the guard being active meant the risk was handled.

That is the management failure.

## Required Repairs

### 1. Fix H token selection

Current active repair:

`H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`

This must prove H selects the correct fresh receipt token when one exists, or keeps the SKU visibly blocked with a clear reason.

### 2. Expand repair beyond A2

After A2 is fixed, apply the same proof to:

- `CN-NR50-TSFE`
- `LV-425G-BY4X`
- `6V-EEC1-2S9Z`

### 3. Fix MOT-to-board escalation

Current packet:

`MOT-TO-BOARD-ESCALATION-REPAIR-V1`

This must make money-risk warnings become active board risks automatically.

### 4. Add a daily pricing risk check

The system needs a daily check that asks:

- which SKUs have new receipt tokens?
- which SKUs still select fallback tokens?
- which SKUs have missing clean floors?
- which SKUs had no repricer write?
- which warnings failed to become board actions?

## What Was Not Done

No price was changed.

No token ledger was edited.

No Google Sheet was written.

No queue, database, Task Scheduler, Amazon, runtime, or output file was changed.

## Business Position

The pricing/floor area is not safe enough to be treated as autonomous yet.

The guard is useful, but it is only half the job. A blocked unsafe write must become a loud business task, not a quiet technical warning.

