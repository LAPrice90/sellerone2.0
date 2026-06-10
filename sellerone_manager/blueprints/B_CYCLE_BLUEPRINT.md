# B Manager Blueprint

## Summary
B is the daytime loop that keeps orders, token accounting, order master, P and L, stock/parking, and B health proof current.

The old B checklist currently does not show an obvious active alert, but that is only a clue. It is not enough manager proof.

Full B manager setup is **not yet proven** because the independent MOT script is still A-only. B needs its own outside checks added to the MOT: fresh outputs, row counts, fresh heartbeat, single owner, safe lock state, maintenance handoff evidence, and clean proof files.

## Manager Blueprint
1. What B is meant to do:
- Collect daytime order and item facts.
- Allocate token cost truth cleanly.
- Rebuild the order master and daily P and L support.
- Refresh stock/parking views.
- Run the B health gate.
- Maintain safe lock, heartbeat, and maintenance handoff behavior.

2. What proof shows it worked:
- Latest B run finished and B gate passed.
- The old B health checklist is only one clue, not the manager's source of truth.
- Orders, order master, token ledger, and schema checks are clean.
- Live B worker and supervisor heartbeats are fresh.
- Manager proof becomes complete only after B MOT and lock/heartbeat mapping are added.

3. What can fail:
- Orders go stale or order items are missing.
- Order master drops rows, has blanks, or lags orders.
- Token allocation becomes unsafe, stale, or incomplete.
- B gate reports fail/warn, which is treated as a clue for MOT classification.
- B lock, supervisor lock, heartbeat, or maintenance marker becomes stale or contradictory.
- Any attempted Sheets write, token correction, overlap run, restart, or scope widening crosses protection.

4. What the manager should check automatically:
- B must be added to the independent MOT script. This is the main job.
- Latest B manifest final state, run age, and gate result.
- Old B checklist fail/warn counts as a clue only.
- Core output freshness and row counts.
- Token safety checks and schema checks.
- B worker lock, supervisor lock, heartbeat freshness, duplicate ownership, and maintenance marker state.
- MOT worklist and retest queue for bounded B repair packets.

5. What Codex can fix without asking Luke:
- Add the B blueprint document.
- Add B support to the independent MOT without running B.
- Map B lock/heartbeat proof so the current missing expectation can become covered.
- Create bounded B worker task packets when MOT finds a repairable issue.
- Repair only manager-side checks or approved packet-scoped code that avoids protected actions.

6. What must stop and come back to Luke:
- Prices, queues, Google Sheets, scheduler ownership, local DB alignment, output deletion, worker restart, live B run without approval, or scope widening.
- Clearing locks or maintenance markers.
- Token/data correction instead of root-cause repair.
- Any evidence contradiction where the manager cannot tell if B is safe.

## Key Changes
- Add `B_CYCLE_BLUEPRINT.md` beside the existing A blueprint, written in plain English.
- Extend `hourly_mot.py` so `--hourly-mot --mot-flow B` performs read-only B proof checks.
- Extend `multi_flow.py` so "Lock and heartbeat safety" is covered only when B ownership proof is fresh and non-duplicated.
- Keep all changes manager-only unless a separate approved worker packet is created.

## Test Plan
- Unit test B MOT fresh evidence: expected status ok.
- Unit test stale/missing B output: expected MOT work item.
- Unit test stale/dead B lock or supervisor heartbeat: expected fail and bounded repair packet.
- Unit test clean retest: fixed item becomes proved.
- Unit test B lock/heartbeat mapping: B expectation count becomes fully covered.
- Run manager refresh only; do not run B.

## Assumptions
- This setup stays B-only.
- Current H/F/O issues do not block B blueprint setup unless they directly affect B ownership proof.
- B live runtime remains untouched during manager setup.
