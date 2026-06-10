# H Defensive Listing Protection For B06WW79DX5

## Objective
Build a compliant defensive pricing mode for SKU `6V-EEC1-2S9Z` / ASIN `B06WW79DX5`.

## Phase 1 - Code And Preview Proof
- Status: complete
- Allowed files:
  - `config/h_defensive_listing_protection.csv`
  - `scripts/phase1/phase1_defensive_listing.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `sellerone_manager/hourly_mot.py`
  - focused tests under `tests/`
- Forbidden actions:
  - no live H run
  - no live price write
  - no Google Sheets write
  - no queue edit
  - no local DB alignment
  - no output deletion
  - no scheduler ownership change
- Success criteria:
  - config loads only safe opt-in rows - passed
  - stale or missing seller proof returns hold - passed
  - B06 defensive mode overrides the old temp trial for this SKU - passed
  - live writes remain disabled until protected activation - passed
  - proof files are written in isolated tests - passed
  - H MOT exposes defensive mode state - passed

## Phase 1 Verification
- Completed: 2026-06-04
- Tests passed:
  - `python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q`
  - result: 75 passed
- Read-only manager refresh:
  - `python -m sellerone_manager.app --hourly-mot --mot-flow H`
  - result: fail_count=0, defensive listing row ok, preview_rows=1, live_rows=0
  - remaining H warnings are existing manager warnings, not defensive-listing failures.

## Phase 2 - Protected Live Activation
- Status: active_pending_live_proof
- Trigger:
  - Luke approved protected H pricing activation for `6V-EEC1-2S9Z` on 2026-06-04
  - preview proof is clean
- Activation:
  - `config/h_defensive_listing_protection.csv` now has `live_write_enabled=1` for `6V-EEC1-2S9Z` only
  - backup saved at `config/backups/h_defensive_listing_protection_before_live_activation_20260604.csv`
- Current proof status:
  - manager MOT sees the feature as live-enabled
  - no B06 defensive action proof row has appeared yet
  - status remains not yet live-proven
- Required action before live proof:
  - set `live_write_enabled=1` only for `6V-EEC1-2S9Z`
  - use the normal guarded H owner path
  - preserve SellerOne floor and ceiling checks
- Success criteria:
  - H owned run reaches a terminal marker
  - action log shows any write stayed inside floor and ceiling
  - manager MOT shows defensive mode with no hidden pricing risk
- Timeout rule:
  - if no protected proof window is approved, keep live writes disabled.

## Monitoring Target
- Read-only proof:
  - `out/h_defensive_listing_action_log.csv`
  - `out/h_defensive_listing_campaign_memory.csv`
  - `out/h_defensive_listing_daily.csv`
  - `out/systems/M/hourly_mot_H.csv`
- Poll cadence after live activation:
  - first check at +5 minutes
  - second check at +10 minutes
  - then every +15 minutes
  - stop at +60 minutes
- Park condition:
  - if H does not produce fresh proof within the window, mark parked pending next protected H proof window.

## Phase 3 - Simplify Defensive Scope
- Status: complete_pending_live_reload_proof
- Completed: 2026-06-04
- Reason:
  - Luke clarified that Defensive Listing Protection should not become a separate recovery repricer.
  - If the rival leaves, defensive mode must return control to normal H immediately.
- Code behavior:
  - rival below us: defensive mode may 1p undercut inside floor/ceiling
  - rival absent: defensive mode does not override H
  - rival equal/above us: defensive mode does not override H
  - stale proof: defensive mode holds and does not write
- Tests passed:
  - `python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q`
  - result: 77 passed
- Current live proof status:
  - read-only H MOT shows latest completed H run failed before a clean defensive proof row existed
  - newer H run `20260604T104846Z` is running
  - `out/h_defensive_listing_action_log.csv` is still missing, so B06 live behavior is not yet proven
  - because the newer H run was already running before this simplification, final proof requires the next H Python load/run boundary or a manager-approved H proof window.

## Phase 4 - Remove Accidental Daily Write Cap
- Status: fixed_pending_live_reload_proof
- Completed: 2026-06-06
- Reason:
  - Luke confirmed the B06 defensive listing strategy must not have a max writes per day rule.
  - Live proof showed H stopped attempting B06 undercut after two accepted writes while the rival stayed below us.
- Code behavior:
  - rival below us: defensive mode may keep attempting the 1p undercut inside floor and ceiling
  - rival absent/equal/above: defensive mode still stands down to normal H
  - stale proof: defensive mode still holds and does not write
  - no daily write cap blocks defensive pressure
- Config:
  - `config/h_defensive_listing_protection.csv` no longer has `max_writes_per_day`
- Tests passed:
  - `python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q`
  - result: 91 passed
- Read-only manager refresh:
  - `python -m sellerone_manager.app --hourly-mot --mot-flow H`
  - result: fail_count=0, defensive listing row ok
- Live proof status:
  - not yet proven live after the code/config change
  - next verifier is the next normal H-owned run that loads this code
  - success means a fresh B06 proof row no longer uses `daily_write_limit` when the rival is below us
- Latest read-only check:
  - checked at 2026-06-06 15:41 UK time
  - code/config cap removal landed at about 2026-06-06 15:33 UK time
  - latest visible B06 proof row was from 2026-06-06 15:16 UK time and still showed the old `daily_write_limit` behavior
  - next check must inspect the first fresh B06 row after 2026-06-06 15:33 UK time

## Phase 5 - Stop Normal H Raising Out Of Defensive Position
- Status: fixed_pending_live_reload_proof
- Added: 2026-06-06
- Root cause found from read-only proof:
  - B06 defensive mode correctly wrote 6.97 when the rival was 6.98.
  - Once our observed price was 6.97, defensive mode treated the rival as not below us and handed control back to normal H.
  - Normal H then used its raise/profit-recovery path and later proof showed our observed price back at 7.17.
  - The competitor did not need to move for this to happen.
- Required repair:
  - while a B06 defensive rival is present, defensive mode must keep ownership of the defensive target instead of handing control back to normal H just because we are already 1p under.
  - normal H may resume only when the rival is absent for the configured absence window, proof is stale/unsafe, or the defensive mode is disabled.
- Forbidden:
  - do not run H, restart workers, manually change Amazon price, edit queues, write Sheets, align DB facts, delete outputs, or publish as part of this repair.
- Proof target:
  - focused unit test proves rival present at 6.98 and current 6.97 stays in defensive hold at 6.97, with no normal H raise permission.
  - H MOT proof must show no defensive contradiction for B06.
- Code repair:
  - `scripts/phase1/phase1_defensive_listing.py` now keeps defensive ownership while the rival is present in the pressure window.
  - equal rival: defensive mode can write the 1p undercut.
  - already 1p under: defensive mode holds position and does not hand back to normal H.
  - rival above: defensive mode holds current position and does not let normal H raise us during the pressure window.
  - `sellerone_manager/hourly_mot.py` now fails B06 proof that leaks back to normal H or daily write cap while a rival is present.
- Tests passed:
  - `python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q`
  - result: 93 passed
  - `python -m py_compile scripts/phase1/phase1_defensive_listing.py scripts/phase1/phase1_main_loop.py sellerone_manager/hourly_mot.py`
  - result: passed
- Live proof status:
  - live H reload proof passed on run `20260606T145124Z`
  - H wrote B06 target 6.97 while the rival was 6.98
  - run finalized successfully with publish status ok
  - read-only H MOT retest passed with fail_count=0 and `h_defensive_listing_protection_mode` ok
  - Amazon visible reflection is still pending because the write proof is `SPAPI_ACCEPTED` and needs the next observation to show our current price at 6.97
- Next propagation check:
  - due after 2026-06-06T15:30:00Z
  - inspect `out/h_defensive_listing_action_log.csv`
  - success means the next B06 row after `20260606T145124Z` shows current price 6.97 with `pressure_hold` or no further write needed
  - if it still shows current price 7.17, package a bounded H write-verification/application follow-up; do not manually change price outside H
- Propagation check result:
  - passed at 2026-06-06T15:40:00Z heartbeat check
  - fresh B06 row `20260606T151542Z` showed current price 6.97, rival 6.98, target 6.97
  - phase was `pressure_hold`, write status was `NO_WRITE_REQUIRED`
  - this proves Amazon-visible price reflection and defensive single-strategy hold for B06
