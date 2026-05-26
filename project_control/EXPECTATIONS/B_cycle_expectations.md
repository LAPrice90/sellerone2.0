# B Cycle Expectations

## Purpose
The B cycle is the daytime operational loop for orders, token accounting, and sales-side operational outputs. It keeps live trading and ledger views current during the day.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Daytime loop runner | B cycle runs continuously with boundary-safe restart behavior | In Progress | Supervisor and cycle loop are implemented |
| Order collection | Orders and order items are collected on cadence | In Progress | Implemented in B001/B002 path |
| Token ledger allocation | Token ledger and allocation outputs are built | In Progress | Implemented in B007 and related token steps |
| Order master build | Order master is rebuilt from current data | In Progress | Implemented in B004 |
| P and L daily build | Daily P and L output is refreshed | In Progress | D001 is called in B cycle flow |
| Stock and parking refresh | Stock and parking snapshots are refreshed | In Progress | Implemented in B901 internal refresh |
| End-of-cycle health gate | B profile health check runs each cycle | In Progress | A015 profile B path is implemented |
| Maintenance pause and resume | B supports A maintenance boundary handoff | In Progress | `maintenance.requested/ready/active` support exists |
| Lock and heartbeat safety | B lock ownership and heartbeat updates prevent overlap | In Progress | Lock and heartbeat logic are implemented |

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
