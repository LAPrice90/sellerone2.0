# B Cycle Expectations

## Purpose
The B cycle is the daytime operational loop for orders, token accounting, and sales-side operational outputs. It keeps live trading and ledger views current during the day.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Daytime loop runner | B cycle runs continuously with boundary-safe restart behavior | In Progress | Supervisor and cycle loop are implemented |
| Order collection | Orders and order items are collected on cadence | In Progress | Implemented in B001/B002 path |
| Backdate order recovery | Missing marketplace orders can be recovered from November 2025 into quarantine proof before live use | In Progress | Manager proof exists; API recovery execution is not yet proven |
| Per-marketplace future order coverage | Each Amazon marketplace has its own daily cursor proof so UK activity cannot hide quieter markets | In Progress | Current MOT evidence on 2026-05-30 shows 12 stale per-marketplace cursor proofs. A fresh shared order marker must not clear this by itself. |
| Recovery quarantine and duplicate guard | Recovered orders stay quarantined with duplicate and live-merge guards before ROI or restocking use | In Progress | No live merge without Luke approval |
| Sellerboard outside comparison | Sellerboard remains an outside check for orders, SKU mapping, statuses, refunds, fees, and shipping gaps | In Progress | Sellerboard is a bridge estimate until API proof exists |
| Sellerboard daily email intake | Sellerboard email attachments are inspected daily and storage cleanup is guarded | In Progress | B now uses the local Gmail OAuth proof pattern from FPM016. Local OAuth presence is only a clue; B is manager-proven only after read-only proof sees the Sellerboard label, message, and OrderList attachment metadata. Deletion remains local-intake-only and guarded. |
| Refund fee shipping ROI bridge | Refund, shipping, commission, FBA fee, and ROI gaps are labelled as API proved, Sellerboard bridge estimate, or not yet proven | In Progress | Bridge values must not silently feed live ROI |
| Token ledger allocation | Token ledger and allocation outputs are built | In Progress | Implemented in B007 and related token steps |
| Stock receipt and token sync proof | B independently checks that stock receipt intake, token allocations, missing-token proof, and Order Master agree | In Progress | This is manager proof only. Sheet receipt changes, token creation, and stock corrections remain protected actions. |
| Order master build | Order master is rebuilt from current data | In Progress | Implemented in B004 |
| P and L daily build | Daily P and L output is refreshed | In Progress | D001 is called only after the B health gate allows the publish/P and L section. Current MOT evidence on 2026-05-30 shows P and L is blocked by the B health gate, not by a standalone D001 proof bug. |
| Stock and parking refresh | Stock and parking snapshots are refreshed | In Progress | Implemented in B901 internal refresh |
| End-of-cycle health gate | B profile health check runs each cycle | In Progress | A015 profile B path is implemented |
| Maintenance pause and resume | B supports A maintenance boundary handoff | In Progress | `maintenance.requested/ready/active` support exists |
| Lock and heartbeat safety | B lock ownership and heartbeat updates prevent overlap | In Progress | Lock and heartbeat logic are implemented |
| B Management readiness gate | Independent MOT gives one plain-English ready/not-ready sign-off for B maintenance | In Progress | Was ready as of 2026-05-27, but current MOT evidence on 2026-05-30 blocks readiness while per-marketplace cursor proof is stale and P and L is blocked by the B health gate. |
| B order truth completion gate | Independent MOT separates manager readiness from full order truth completion | In Progress | Not complete yet: refund, shipping, fee, and ROI truth still needs API-backed proof or clear labels before it can feed ROI/restocking |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed B cycles:
- Fails: nonzero cycle exits, hard step failures, or boundary safety failures.
- Warnings: nonfatal collector warnings, degraded cycle outcomes, or health warn conditions.
- Clean runs: completed cycle with expected core steps, safe finalize, and no fail conditions.

Suggested scoring baseline:
- Start at 100.
- Subtract 20 if any fail exists in window.
- Subtract 5 per warned run, up to 30.
- Subtract 10 if maintenance boundary behavior is inconsistent.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- B loop produces order, token, and order master outputs reliably through the day.
- End-of-cycle health gating is active and evidence-backed.
- Stable:
- No fail in last 10 cycles.
- At least 8 of last 10 cycles are clean.
- Maintenance handoff behavior is consistent.
- Ready for expansion:
- Stable operation maintained across 2 review windows.
- Warning classes are predictable and actively controlled.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Additional token analytics and operator drill-down reports.
- Throughput optimizations and lower-latency cycle timing.
- Convenience-only output formatting improvements.
- Non-critical shadow-comparison enhancements.

## SECTION 5 - Planning Tolerance Gate
- This expectations file defines reliability quality targets. It is not an automatic planning-stop rule by itself.
- Planning and optimisation work may proceed when B scoped hard-block conditions are clear.
- Hard-block examples for B planning:
- active FAIL in B scoped gate
- required B runtime path not operational
- required B publish/output path down when required
- core B outputs stale beyond cadence
- duplicate ownership, crash loop, or unresolved scheduler ghost affecting B
- Soft-block examples for B planning:
- accepted non-blocking WARN (for example classified nonfatal collector status)
- "To Baseline" reliability label while evidence window matures
- stale aggregate labels when current B live evidence is newer
- Soft-blocks must be reported and tracked, but do not by themselves stop planning.

## SECTION 6 - Completion Gates
- `B Management ready for maintenance` means the manager can safely watch B, create bounded worker jobs, and prove retests without Luke managing technical steps.
- `B order truth complete` means all order coverage, marketplace recovery, Sellerboard comparison, refund, shipping, fee, and ROI support is API-proven or clearly labelled.
- Old B checklist FAIL/WARN counts are not completion proof. They remain clues only.
- Sellerboard bridge values must stay separate from live ROI/restocking until Luke approves direct use.
