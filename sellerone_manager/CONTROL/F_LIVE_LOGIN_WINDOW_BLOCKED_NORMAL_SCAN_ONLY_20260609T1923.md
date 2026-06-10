# F Live Login Window Blocked - 2026-06-09 19:23 UK

## Status

F is not finished and not parked-and-moving.

## Evidence

- F owner PID: `2972`
- F child PID: `36164`
- F061 state: `Seller Central Proof Required`
- Supplier: `td_synnex`
- Child status timestamp: `2026-06-09T18:23:28Z`
- Login controller report timestamp: `2026-06-09T18:22:22Z`

Controller result:

- Status: `disabled`
- Reason: `normal_scan_only`
- Proof: `blocked`
- Dashboard Yes/No: not visible

## Business Result

F did reach a live Seller Central login window, but the single-login controller did not move into the approved proof path.

Accepted finish condition was not met:

- Dashboard Yes/No was not proved.
- TD Synnex was not proved parked for second-check-after-login.
- The next price file was not proved moving.

## Scheduler Restore

`AMZ Pricing Summary Hourly` was restored after the blocked proof window.

Proof:

- Task state: Enabled
- Status: Ready
- Next run time: `2026-06-09 19:52`
- Daily `AMZ Pricing Summary`: Enabled and Ready for `2026-06-10 06:00`

## Safest Proposed Fix

Do not attempt another live proof with the same owner/child state.

Next safe route is an F-only controller/handoff repair or reload decision that explains why child PID `36164` is still entering `normal_scan_only` despite the repair-ready proof.

## Boundaries Preserved

No Amazon security bypass, SMS/phone/code retry, price change, Sheet write, database alignment, output deletion, purchase, receiving, send-to-Amazon action, second F owner, blind process kill, or daily A scheduler change occurred.
