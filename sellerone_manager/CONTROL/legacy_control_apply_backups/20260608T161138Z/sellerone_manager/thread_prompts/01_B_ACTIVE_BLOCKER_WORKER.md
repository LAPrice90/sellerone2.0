Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the B cycle active blocker job.

Plain-English mission:
B is the order-truth cycle. It should prove Amazon orders, marketplace coverage, order master, token/stock handoff, P and L, and safe maintenance handoff from the outside. B is the current active blocker. Your job is to reduce B from several confusing failures into clear root-cause packages, and make safe B-scoped fixes only where the manager-approved packet allows it.

Do not drift:
- Do not work on A, E, H, F, or O.
- Do not use Sellerboard estimates as live ROI/restocking truth.
- Do not run B live unless a manager-approved B proof window already exists.

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
- B is the active blocker.
- B current failures include:
  - stale P and L daily proof
  - stale future marketplace cursor proof
  - B management readiness not complete
  - B order truth completion not complete
- B warnings include marketplace coverage, Sellerboard bridge freshness, refund/fee/ROI bridge, and Sellerboard email freshness.

Preferred approved packets:
- `MOT_B_B_PNL_DAILY`
- `MOT_B_B_FUTURE_MARKETPLACE_ORDER_CURSORS`
- `MOT_B_B_MANAGEMENT_READY_FOR_MAINTENANCE`
- `MOT_B_B_ORDER_TRUTH_COMPLETION`
- `MGR_B_repair_out_systems_M_hourly_mot`

Hard boundaries:
- Do not run B live unless the approved packet explicitly allows a B proof window.
- Do not restart B.
- Do not edit locks or maintenance markers.
- Do not write Google Sheets.
- Do not change prices or queues.
- Do not align or rewrite local DB facts to hide a mismatch.
- Do not delete outputs.
- Do not use Sellerboard values in live ROI/restocking.
- Stop if proof requires a business decision or live-cycle approval.

Ownership:
You own B manager proof and B-safe repair packaging only. Other agents may work on E/H/F/O at the same time. Do not revert unrelated edits. If you touch common manager files, keep the edit narrowly B-scoped and list it clearly.

Expected output:
1. Inspect the B approved task packet and B MOT rows.
2. Separate true B data/runtime gaps from stale or proof-mapping gaps.
3. Make safe B-scoped code/proof fixes only if allowed by the packet.
4. Retest with read-only B MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

5. If live B proof is required, record it as a bounded B proof window instead of asking Luke in chat.

Final reply shape:
- Decision needed: yes/no
- What B now proves in plain English
- What changed, if anything
- What remains blocked, warning, or not proved
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say "no further action needed now"

