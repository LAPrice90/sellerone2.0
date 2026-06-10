Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the B cycle manager takeover job.

Plain-English mission:
B is the order cycle. The main manager currently says B is the active blocker. Your job is to turn the B problem from chat noise into clean manager proof: either fix safe manager/MOT proof gaps, or produce bounded repair packets where a live/protected action would be needed.

Do not drift:
- Do not turn this into a general B repair chat.
- Do not use old FAIL/WARN counts as final proof.
- Do not make Luke manage task IDs, logs, or technical sequencing.
- Start from the approved manager packet and the independent MOT evidence.

Read first:
- `C:\Users\Luke\Desktop\SellerOne 2.0\AGENTS.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\B_cycle_expectations.md`

Current manager state:
- A is calm and proved.
- B is blocked and is the main active blocker.
- The active approved packet is `MGR_B_repair_out_systems_M_hourly_mot`.
- Current B MOT active failures include:
  - `b_future_marketplace_order_cursors`
  - `b_management_ready_for_maintenance`
  - `b_order_truth_completion`
  - `b_pnl_daily`
- Luke does not need to approve safe code/proof work inside approved non-Luke packets.

Hard boundaries:
- Do not run B live.
- Do not restart B.
- Do not clear or edit locks/markers to make proof look good.
- Do not write Google Sheets.
- Do not change prices or queues.
- Do not align or rewrite local DB facts.
- Do not delete outputs.
- Do not feed Sellerboard bridge values into live ROI/restocking.
- Stop only if a protected action is truly needed.

Ownership:
You own B manager/MOT proof work only. Other agents may work on E/H/F/O at the same time. Do not revert or overwrite unrelated edits. If you need to touch common manager files, keep the edit narrowly B-scoped and list it clearly.

Expected work:
1. Refresh/claim the relevant manager packet if needed.
2. Inspect B MOT proof logic and B expectation mapping.
3. Make safe code/proof fixes only if the root cause is code/proof mapping, not live data correction.
4. Retest with read-only B MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

5. If fixed, update task state to `fixed_needs_retest` or `proved` only through the manager path.
6. If not fixable without protected action, create or update a bounded B repair packet with allowed files, forbidden actions, proof path, rollback path, and stop condition.

Final reply shape:
- `Decision needed: yes/no`
- What B now proves in plain English
- What changed, if anything
- What remains blocked or parked
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

