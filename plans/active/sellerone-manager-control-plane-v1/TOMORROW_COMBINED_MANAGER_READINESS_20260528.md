# Tomorrow Combined Manager Readiness - 2026-05-28

## Plain-English Rule
Tomorrow mode is Quiet Autonomy.

The manager may keep checking, package safe work, and run read-only proof checks. In Quiet Autonomy, H/O pause-based proof is parked unless the H maintenance controller install proof already exists.

This is not approval for business decisions.

## Main Desk
- Main front door: `sellerone_manager/current_state.json`
- Main MOT board: `out/systems/M/mot/mot_rollup_latest.md`
- Main worklist: `out/systems/M/mot/mot_worklist.csv`
- Approved task packets: `out/systems/M/approved_task_packets.csv`
- Due check: `project_control/DUE_CHECK_REGISTER.csv` row `COMBINED_MANAGER_TOMORROW_READY_20260528`

## Flow Expectations
- A: wait for the normal morning proof. If handoff proof still fails, create a bounded A repair packet instead of running random A scripts.
- B: keep Sellerboard/AED truth visible as warning or repair packets until the source is proved. Do not merge bridge values into live ROI without business approval.
- E: keep as code-proven with coverage warnings unless a business decision depends on the missing proof.
- H: high-risk. Any pause/proof window must prove terminal state and scheduler restoration.
- F: feed the F price-list manager evidence into the combined board. Do not edit the F061 queue or approve unresolved Entertainment Trading rows.
- O: treat as mid-build. Missing future features are `not_started` or `not_verified`, not runtime failures.

## Allowed Without Luke Tomorrow
- Manager MOT refreshes.
- Safe code repairs inside approved task packets.
- Boundary-safe proof runs.
- Controlled technical pause/resume when the approved proof packet requires it.

## Still Blocked
- Price changes.
- Queue edits.
- Google Sheets writes.
- Product DB or local DB alignment.
- Output deletion.
- Publishing.
- Purchase commitment, receiving, or send-to-Amazon.
- Approving uncertain F or O business rows.
- Hiding bad data downstream.

## Success Condition
By the 2026-05-28 morning readiness check, the manager board should show every live issue as one of:
- proved
- warning
- not_checked
- not_started
- not_verified
- active approved task packet
- parked real Luke decision

If any flow claims complete without proof, if any scheduler is paused without restoration proof, or if any business decision is made automatically, tomorrow mode has failed and the manager must stop that lane.
