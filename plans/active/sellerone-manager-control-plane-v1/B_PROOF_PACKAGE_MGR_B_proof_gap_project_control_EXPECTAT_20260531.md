# B Proof Package - Manager Coverage And Warning Classification - 2026-05-31

## Manager Task
- Source packet: MGR_B_proof_gap_project_control_EXPECTAT
- Source proof: project_control/EXPECTATIONS/B_cycle_expectations.md
- Source MOT: out/systems/M/hourly_mot_B.csv
- This package is manager proof coverage and classification only.
- No B worker repair was performed in this packaging step.
- No B run, worker restart, Sheet write, token correction, data correction, local DB alignment, output deletion, ROI use, price change, or queue edit was performed.

## Current B State
Latest B manager evidence shows:
- B FAIL count: 0
- B WARN count: 4
- Luke action needed: no

Plain English:
- B order collection is running and fresh.
- B worker ownership and supervisor ownership are readable.
- B maintenance handoff markers are clear.
- Sellerboard outside comparison is working for missing shipped orders.
- B is maintenance-ready.
- B order truth is not complete yet because refund, fee, shipping, and ROI proof are not fully API-backed.

## Covered Proof
The manager has usable outside proof for:
- daytime loop runner
- order collection
- backdate order recovery
- per-marketplace future order cursors
- recovery quarantine and duplicate guard
- Sellerboard daily email intake
- token ledger allocation
- order master build
- P and L daily build
- stock and parking refresh
- maintenance pause/resume
- lock and heartbeat safety

## Warning Classification
| Area | Current state | Meaning |
|---|---|---|
| Sellerboard outside comparison | warning | Order reconciliation is clean, but marketplace coverage remains a watch item. |
| Refund, fee, shipping, ROI bridge | warning | Sellerboard bridge has refund/fee/ROI gaps. These must stay labelled and must not feed live ROI/restocking as final truth. |
| End-of-cycle health gate | not verified | Old B checklist is a clue only. It is not the manager's proof of B readiness. |
| B Management readiness gate | warning | B is maintainable, but visible order-truth gaps remain. |
| B order truth completion gate | warning | Full order truth is not complete until refund, shipping, fee, and ROI proof are API-backed or clearly labelled. |

## What Should Not Become A Repair Job
- Do not repair `b_management_ready_for_maintenance` directly. It is a summary light.
- Do not repair `b_order_truth_completion` directly. It is a summary light.
- Do not use Sellerboard estimates as final ROI/restocking truth.
- Do not treat old B checklist rows as final manager proof.

## Future B Work
Future B work should be split into bounded lanes:
- Refund proof: API-backed refund evidence or explicit not-yet-proven label.
- Fee proof: commission, FBA fee, and shipping fee proof from API or explicit bridge-estimate label.
- ROI proof: ROI rows must show whether each value is API-proved, Sellerboard bridge estimate, or not yet proven.
- Marketplace coverage watch: keep per-marketplace cursor and Sellerboard comparison proof visible.

## Protected Boundaries
Stop and ask Luke before any future task would:
- run or restart B outside an approved proof window
- write Google Sheets
- correct token/data values
- merge recovered orders into live data
- align local DB facts
- delete outputs
- use Sellerboard values in ROI/restocking as final truth
- change prices or queues

## Retest Command
The read-only B manager retest command is:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

Success for this package means:
- B remains at 0 FAIL
- B warnings stay classified as bridge/proof gaps
- no summary row becomes a fake direct repair job
- future work starts from a bounded refund/fee/shipping/ROI proof packet

## Stop Condition
Stop this package after B proof coverage, warning meaning, protected boundaries, and future proof lanes are recorded.
