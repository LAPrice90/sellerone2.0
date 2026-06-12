# H A2-T2AC-TW3L Token Selection Ordering Repair Result - 2026-06-12

Job ref: `H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`

## Plain-English Result

The H token picker has been repaired at the source.

Before this repair, H picked the older fallback token first, then noticed a newer receipt token existed and blocked clean proof. After this repair, when the first available token is an unproved fallback and a newer stock receipt token is available for the same SKU, H chooses the receipt token first.

No Amazon price, token ledger row, Google Sheet, queue, Product DB, local DB, scheduler, runtime, or output file was changed by this repair.

## Old Behavior Proved

Read-only current H evidence still shows the old fallback-first behavior:

- Latest inspected H trace rows for `A2-T2AC-TW3L` selected fallback token `ADJ-A2-T2AC-TW3L-FBA15LKBY55D-0141`.
- Selected fallback cost was `4.510`.
- H trace referenced newer receipt token `SR-20260605-ROW0092-0001`.
- H trace showed `token_selection_conflict=1`.
- Current runtime floor snapshot for the SKU is read-only/no-write evidence, not a clean live repricer write.

This old evidence is intentionally not hidden or edited. It remains historical proof of the blocked state until a future approved H proof refresh produces new output.

## New Behavior Proved

Using the live token ledger as read-only input, the repaired H selector now resolves `A2-T2AC-TW3L` to:

- selected token: `SR-20260605-ROW0092-0001`
- selected token source: `stock_receipt`
- selected cost: `4.89`
- proof state: `clean`
- superseded fallback note: `h_selection_superseded_unproved_fallback=ADJ-A2-T2AC-TW3L-FBA15LKBY55D-0141`
- token selection conflict: `False`
- blocking reason codes: none
- calculated local floor from isolated selector proof: `11.35`

This is code/test proof only. It does not approve or force a repricer write.

## Floor Safety

The floor remains blocked whenever proof is not clean.

The repair does not remove the existing guard. `token_selection_conflict` remains a blocking reason code, and MOT now treats `token_selection_conflict` plus missing clean floor proof as an active H risk.

That means old or stale evidence cannot be made to look clean by a downstream report. If H still shows conflict plus no clean floor, the manager layer keeps it visible as work to fix.

## MOT And Manager Visibility

`hourly_mot.py` now detects:

- latest H trace has `token_selection_conflict`
- and the matching floor proof is missing or blocked

When both are true, `h_token_floor_source_guard` returns `fail` with:

- `token_selection_conflict_no_clean_floor_rows=<count>`
- affected SKU sample
- root cause text saying this is an active pricing risk, not parked fallback-cost cleanup

The focused MOT test also proves the worklist item stays active with status `new` and job ref `H-TOKEN-FLOOR-SOURCE-GUARD`, rather than being parked.

## Files Changed

- `scripts/h/h_floor_truth.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_h_floor_truth.py`
- `tests/manager/test_h_hourly_mot.py`

Rollback path: revert the above four code/test files to the previous git state. No business data rollback is needed because no business data was written.

## Tests Passed

Command run from repo root:

```powershell
python -m pytest .\tests\test_h_floor_truth.py .\tests\manager\test_h_hourly_mot.py -q
```

Result:

```text
40 passed in 4.72s
```

## Status

Code fix applied and isolated verification passed.

Live loop verification is not claimed, because this packet forbids runtime restart or business runtime execution. A future approved H proof refresh is needed before current output files can show the new selected receipt token in live H traces.

Next move: `wait until a future approved H proof refresh runs and check out/h_floor_truth_trace.csv plus out/phase1_runtime_floor_snapshot_latest.csv`
