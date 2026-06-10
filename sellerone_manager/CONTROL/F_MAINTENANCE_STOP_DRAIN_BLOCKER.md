# F Maintenance Stop Drain Blocker

Created: 2026-06-09 14:53 UK
Role: Operations
Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

## Status

F is half-alive, not safely stopped.

The F-only maintenance request is active, and the supervisor now reports the manager side as paused:

- `state=paused`
- `reason=f_only_request`

However, the scanner child is still present:

- child PID: `14740`
- supplier: `td_synnex`
- child status wording: `manager_mode=Catching Up`
- drain marker: `F_restart_drain.ready` not present
- latest supervisor scanner progress age: over `900` seconds
- last real scanner progress recorded: `2026-06-09T13:16:48Z`

## Blocker

The soft maintenance drain did not reach a clean drain-ready boundary.

Plain English: F has accepted the stop request enough to pause the manager, but the old TD Synnex scanner child is still hanging around. That means F is not truly stopped and must not be described as healthy, logged in, or catching up.

## What Was Attempted

Operations placed the approved F-only maintenance request:

- path: `out/systems/F/price_list_manager/live/f061_visible_login.requested`
- `action=reload`
- `exit_after_drain=1`
- `normal_business_scanning_allowed=0`

Operations then waited for the expected soft drain marker:

- expected marker: `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- result: marker not present

## Why Stronger Stop Is Allowed

Approved authority:

- `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md`
- `CONTROL/SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md` ADR-0023

The softer method has failed:

- no drain-ready marker appeared
- no manager PID remains to progress the normal drain loop
- stale child PID `14740` remains present

This record proves the stronger stop is not blind. The target is named, the reason is named, and the action is limited to the F price-list scanner child/owner path.

## Approved Next Stop Step

Operations may stop the stale F scanner child process tree for PID `14740` only.

Allowed:

- targeted stop of the stale F scanner child process tree
- no second F owner
- no normal business scanning restart
- no Seller Central login attempt

Still forbidden:

- Amazon security bypass
- repeated SMS/phone/code attempts
- separate Chrome workaround
- browser/profile/cookie manipulation
- output deletion
- price changes
- Google Sheets writes
- database alignment
- purchase, receiving, or send-to-Amazon
- widening into other flows

## Next Proof Condition

The next Seller Central login proof attempt is allowed only after:

- the stale F child is stopped,
- repair work is ready,
- one F owner route is confirmed,
- the bounded proof window exists,
- and proof can show Dashboard Yes/No or clean logged-out parking/hold behavior that moves past the TD Synnex stuck point.

## Stop Attempt Result - 2026-06-09 14:52 UK

Outcome: blocker remains.

Attempted action:

- targeted stop of stale F scanner child process tree for PID `14740`
- command type: Windows process-tree termination for the named F child only

What failed:

- Windows returned `Access is denied` for PID `14740`.
- Windows also denied termination of remaining scanner-owned browser/driver descendants including `chrome.exe` and `chromedriver.exe` processes.
- Some descendant processes were terminated, but the named F child and key browser/driver descendants remain present.

Current still-present processes observed after the attempt:

- `14740` - `python.exe`, parent `16664`
- `29276` - `chrome.exe`, parent `14740`
- `27424` - `chromedriver.exe`, parent `14740`
- `18920` - `chromedriver.exe`, parent `14740`

Current supervisor signal:

- `state=paused`
- `reason=f_only_request,global_maintenance_request`
- `child_pids=14740`
- scanner progress age remains over `900` seconds
- drain marker remains not present

Additional constraint:

- global maintenance request is currently A-owned: `requested_by=A`, `reason=A_cycle_run`

Safest proposed fix:

- keep F maintenance request active,
- do not start a second F owner,
- do not restart normal F scanning,
- wait for the active F Worker repair/status result,
- if the stale child still cannot be stopped, Luke or Rep must approve an elevated Windows/admin-level F-only stop or a PC-level recovery window.
